"""Rule engine: evaluate structured and natural language rules against emails."""

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import BaseLLMProvider
from app.models.classification import Classification
from app.models.email import Email
from app.models.rule import Rule
from app.services.llm_service import interpret_rule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured rule evaluation (no LLM)
# ---------------------------------------------------------------------------


def _get_field_value(email: Email, classification: Classification | None, field: str) -> str | bool | None:
    """Get the value of a filterable field from email/classification."""
    field_map = {
        "from_address": email.from_address,
        "from_name": email.from_name or "",
        "to_addresses": ",".join(email.to_addresses or []),
        "subject": email.subject or "",
        "body_excerpt": email.body_excerpt or "",
        "has_attachments": email.has_attachments,
    }

    if classification:
        field_map.update({
            "category": classification.category,
            "is_spam": classification.is_spam,
            "is_phishing": classification.is_phishing,
        })

    return field_map.get(field)


def _evaluate_condition(condition: dict, email: Email, classification: Classification | None) -> bool:
    """Evaluate a single condition: {field, op, value}."""
    field = condition.get("field", "")
    op = condition.get("op", "")
    expected = condition.get("value")

    actual = _get_field_value(email, classification, field)

    if actual is None:
        return False

    # Boolean fields
    if isinstance(actual, bool):
        return actual == bool(expected)

    # String operations
    actual_str = str(actual).lower()
    expected_str = str(expected).lower() if expected is not None else ""

    if op == "equals":
        return actual_str == expected_str
    elif op == "not_equals":
        return actual_str != expected_str
    elif op == "contains":
        return expected_str in actual_str
    elif op == "not_contains":
        return expected_str not in actual_str
    elif op == "starts_with":
        return actual_str.startswith(expected_str)
    elif op == "ends_with":
        return actual_str.endswith(expected_str)
    elif op == "regex":
        try:
            return bool(re.search(str(expected), str(actual), re.IGNORECASE))
        except re.error:
            logger.warning("Invalid regex in rule condition: %s", expected)
            return False
    elif op == "in_list":
        if isinstance(expected, list):
            return actual_str in [str(v).lower() for v in expected]
        return False
    else:
        logger.warning("Unknown operator: %s", op)
        return False


def _evaluate_group(group: dict, email: Email, classification: Classification | None) -> bool:
    """Evaluate a group of conditions with AND/OR operator. Supports nesting."""
    operator = group.get("operator", "AND").upper()
    rules = group.get("rules", [])

    results = []
    for rule in rules:
        if "operator" in rule and "rules" in rule:
            # Nested group
            results.append(_evaluate_group(rule, email, classification))
        else:
            # Leaf condition
            results.append(_evaluate_condition(rule, email, classification))

    if operator == "AND":
        return all(results) if results else False
    elif operator == "OR":
        return any(results) if results else False
    else:
        logger.warning("Unknown group operator: %s", operator)
        return False


def evaluate_structured_rule(
    rule: Rule, email: Email, classification: Classification | None = None
) -> bool:
    """Evaluate a structured rule against an email. No LLM call."""
    if not rule.conditions:
        return False
    return _evaluate_group(rule.conditions, email, classification)


def get_matched_conditions_description(
    rule: Rule, email: Email, classification: Classification | None = None
) -> list[str]:
    """Get human-readable descriptions of matched conditions (for testing/preview)."""
    if not rule.conditions:
        return []

    descriptions = []
    rules = rule.conditions.get("rules", [])

    for condition in rules:
        if "field" in condition and "op" in condition:
            field = condition["field"]
            op = condition["op"]
            value = condition.get("value", "")
            if _evaluate_condition(condition, email, classification):
                descriptions.append(f"{field} {op} \"{value}\"")

    return descriptions


# ---------------------------------------------------------------------------
# Main evaluation: iterate rules by priority
# ---------------------------------------------------------------------------


async def evaluate_rules(
    db: AsyncSession,
    email: Email,
    classification: Classification | None,
    account_id: uuid.UUID,
    llm: BaseLLMProvider | None = None,
) -> tuple[Rule | None, list[dict]]:
    """Evaluate all active rules against an email.

    Returns (matched_rule, actions) or (None, []) if no rule matches.
    Rules are evaluated by priority DESC. Stop on first match.
    """
    stmt = (
        select(Rule)
        .where(
            Rule.is_active == True,  # noqa: E712
            (Rule.account_id == account_id) | (Rule.account_id == None),  # noqa: E711
        )
        .order_by(Rule.priority.desc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    for rule in rules:
        matched = False

        if rule.type == "structured":
            matched = evaluate_structured_rule(rule, email, classification)

        elif rule.type == "natural" and llm is not None and rule.natural_text:
            # Phase 2: natural language rules require LLM
            interpretation = await interpret_rule(
                llm,
                rule_text=rule.natural_text,
                from_name=email.from_name or "",
                from_address=email.from_address,
                subject=email.subject or "",
                category=classification.category if classification else "",
                date=str(email.date),
                body_excerpt=email.body_excerpt or "",
            )
            matched = interpretation.matches

        if matched:
            # Update match stats
            rule.match_count += 1
            from datetime import datetime, timezone
            rule.last_matched_at = datetime.now(timezone.utc)

            logger.info("Rule '%s' matched email %s", rule.name, email.id)
            return rule, rule.actions

    return None, []


# ---------------------------------------------------------------------------
# Default actions based on category (account_settings.default_category_action)
# ---------------------------------------------------------------------------


def get_default_actions(category: str, category_action_map: dict) -> list[dict]:
    """Get default actions for a category from account_settings.default_category_action.

    Example category_action_map:
    {
        "newsletter": {"action": "move", "folder": "Newsletters"},
        "spam": {"action": "move", "folder": "Junk"},
        "phishing": {"action": "move", "folder": "InboxShield/Quarantine"},
    }
    """
    action_config = category_action_map.get(category)
    if not action_config:
        return []

    action_type = action_config.get("action", "move")
    actions = [{"type": action_type}]

    if action_type == "move" and "folder" in action_config:
        actions[0]["folder"] = action_config["folder"]

    return actions
