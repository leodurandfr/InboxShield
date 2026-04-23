"""LLM service: factory, classification, JSON parsing, and retry logic."""

import json
import logging
import re
import time

from app.llm.base import BaseLLMProvider, ClassificationResult, RuleInterpretation
from app.llm.ollama import OllamaProvider
from app.llm.prompts import build_classification_prompt, build_rule_interpretation_prompt

logger = logging.getLogger(__name__)

# Valid categories for validation
VALID_CATEGORIES = {
    "important",
    "work",
    "personal",
    "newsletter",
    "promotion",
    "notification",
    "spam",
    "phishing",
    "transactional",
}

# JSON schemas for structured outputs (Ollama format parameter)
CLASSIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": list(VALID_CATEGORIES),
        },
        "confidence": {"type": "number"},
        "explanation": {"type": "string"},
        "is_spam": {"type": "boolean"},
        "is_phishing": {"type": "boolean"},
        "phishing_reasons": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "category",
        "confidence",
        "explanation",
        "is_spam",
        "is_phishing",
        "phishing_reasons",
    ],
}

RULE_INTERPRETATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["matches", "reason"],
}


# ---------------------------------------------------------------------------
# JSON parsing (tolerant)
# ---------------------------------------------------------------------------


def parse_classification_json(raw: str) -> dict | None:
    """Parse LLM response into classification dict. Tolerant of imperfect JSON.

    Strategy:
    1. Direct JSON parse
    2. Extract first {...} block
    3. Regex individual fields
    """
    # Strategy 1: direct parse
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict) and "category" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Strategy 2: find first JSON block
    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and "category" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Strategy 2b: find nested JSON block (phishing_reasons contains a list)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and "category" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Strategy 3: regex extraction
    category_match = re.search(r'"category"\s*:\s*"([^"]+)"', raw)
    confidence_match = re.search(r'"confidence"\s*:\s*([\d.]+)', raw)
    explanation_match = re.search(r'"explanation"\s*:\s*"([^"]*)"', raw)

    if category_match:
        return {
            "category": category_match.group(1),
            "confidence": float(confidence_match.group(1)) if confidence_match else 0.5,
            "explanation": explanation_match.group(1) if explanation_match else "",
            "is_spam": '"is_spam": true' in raw.lower() or '"is_spam":true' in raw.lower(),
            "is_phishing": '"is_phishing": true' in raw.lower()
            or '"is_phishing":true' in raw.lower(),
            "phishing_reasons": [],
        }

    return None


def parse_rule_json(raw: str) -> dict | None:
    """Parse LLM response for rule interpretation."""
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict) and "matches" in data:
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and "matches" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Regex fallback
    matches_match = re.search(r'"matches"\s*:\s*(true|false)', raw, re.IGNORECASE)
    if matches_match:
        return {
            "matches": matches_match.group(1).lower() == "true",
            "reason": "",
        }

    return None


def _validate_category(category: str) -> str:
    """Validate and normalize category. Return closest match or 'notification' as fallback."""
    cat = category.lower().strip()
    if cat in VALID_CATEGORIES:
        return cat

    # Try partial matching
    for valid in VALID_CATEGORIES:
        if valid.startswith(cat) or cat.startswith(valid):
            return valid

    logger.warning("Unknown category '%s', defaulting to 'notification'", category)
    return "notification"


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def create_provider(
    provider: str,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.1,
) -> BaseLLMProvider:
    """Create an LLM provider instance based on settings."""
    if provider == "ollama":
        from app.config import settings as app_settings

        # Priority: explicit base_url > app config > default
        ollama_url = base_url or app_settings.ollama_base_url or "http://localhost:11434"
        return OllamaProvider(
            base_url=ollama_url,
            model=model,
        )

    if provider == "anthropic":
        from app.llm.anthropic import AnthropicProvider

        if not api_key:
            raise ValueError("Anthropic API key is required")
        return AnthropicProvider(
            api_key=api_key,
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
        )

    if provider == "openai":
        from app.llm.openai import OpenAIProvider

        if not api_key:
            raise ValueError("OpenAI API key is required")
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o-mini",
            base_url=base_url,
            temperature=temperature,
        )

    if provider == "mistral":
        from app.llm.mistral import MistralProvider

        if not api_key:
            raise ValueError("Mistral API key is required")
        return MistralProvider(
            api_key=api_key,
            model=model or "mistral-small-latest",
            temperature=temperature,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


# ---------------------------------------------------------------------------
# High-level classification
# ---------------------------------------------------------------------------


async def classify_email(
    llm: BaseLLMProvider,
    from_name: str,
    from_address: str,
    to_addresses: str,
    subject: str,
    date: str,
    attachments: str,
    body_excerpt: str,
    few_shot_examples: str = "",
    url_analysis: str = "",
    sender_analysis: str = "",
    reply_to: str = "",
) -> ClassificationResult:
    """Classify an email using the LLM. Includes retry on parse failure."""
    system_prompt, user_prompt = build_classification_prompt(
        from_name=from_name,
        from_address=from_address,
        to_addresses=to_addresses,
        subject=subject,
        date=date,
        attachments=attachments,
        body_excerpt=body_excerpt,
        few_shot_examples=few_shot_examples,
        url_analysis=url_analysis,
        sender_analysis=sender_analysis,
        reply_to=reply_to,
    )

    start = time.monotonic()
    raw_response = ""
    parsed = None

    # Use structured outputs for Ollama (guarantees valid JSON)
    response_format = CLASSIFICATION_JSON_SCHEMA if llm.provider_name == "ollama" else None

    # Attempt 1
    try:
        raw_response = await llm.generate(
            system_prompt, user_prompt, response_format=response_format
        )
        parsed = parse_classification_json(raw_response)
    except Exception:
        logger.exception("LLM classify attempt 1 failed")

    # Attempt 2: retry with reinforced prompt (only needed for non-structured providers)
    if parsed is None:
        logger.warning("Classification parse failed, retrying with reinforced prompt")
        reinforced_system = (
            system_prompt + "\n\nIMPORTANT: Réponds UNIQUEMENT en JSON valide. Pas de texte autour."
        )
        try:
            raw_response = await llm.generate(
                reinforced_system, user_prompt, response_format=response_format
            )
            parsed = parse_classification_json(raw_response)
        except Exception:
            logger.exception("LLM classify attempt 2 failed")

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if parsed is None:
        logger.error("Failed to parse classification after 2 attempts. Raw: %s", raw_response[:500])
        return ClassificationResult(
            category="notification",
            confidence=0.0,
            explanation="Failed to parse LLM response",
            provider=llm.provider_name,
            model=llm.get_model_name(),
            processing_time_ms=elapsed_ms,
        )

    category = _validate_category(parsed.get("category", "notification"))
    confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))

    return ClassificationResult(
        category=category,
        confidence=confidence,
        explanation=parsed.get("explanation", ""),
        is_spam=bool(parsed.get("is_spam", False)),
        is_phishing=bool(parsed.get("is_phishing", False)),
        phishing_reasons=parsed.get("phishing_reasons", []) or [],
        provider=llm.provider_name,
        model=llm.get_model_name(),
        tokens_used=0,  # Ollama SDK doesn't expose token count directly
        processing_time_ms=elapsed_ms,
    )


async def interpret_rule(
    llm: BaseLLMProvider,
    rule_text: str,
    from_name: str,
    from_address: str,
    subject: str,
    category: str,
    date: str,
    body_excerpt: str,
) -> RuleInterpretation:
    """Interpret a natural language rule against an email."""
    system_prompt, user_prompt = build_rule_interpretation_prompt(
        rule_text=rule_text,
        from_name=from_name,
        from_address=from_address,
        subject=subject,
        category=category,
        date=date,
        body_excerpt=body_excerpt,
    )

    response_format = RULE_INTERPRETATION_JSON_SCHEMA if llm.provider_name == "ollama" else None

    try:
        raw_response = await llm.generate(
            system_prompt, user_prompt, response_format=response_format
        )
        parsed = parse_rule_json(raw_response)

        if parsed:
            return RuleInterpretation(
                matches=bool(parsed.get("matches", False)),
                reason=parsed.get("reason", ""),
            )
    except Exception:
        logger.exception("LLM rule interpretation failed")

    return RuleInterpretation(matches=False, reason="Failed to interpret rule")
