"""Action execution service: run IMAP actions and log them."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.email import Email
from app.services import imap_service
from app.services.encryption import decrypt

logger = logging.getLogger(__name__)


async def execute_actions(
    db: AsyncSession,
    email: Email,
    account_host: str,
    account_port: int,
    account_username: str,
    encrypted_password: str,
    actions: list[dict],
    trigger: str,
    rule_id: uuid.UUID | None = None,
) -> list[dict]:
    """Execute a list of actions on an email and log each one.

    Returns a list of action results: [{"type": ..., "status": ..., "error": ...}]
    """
    password = decrypt(encrypted_password)
    results: list[dict] = []

    for action_def in actions:
        action_type = action_def.get("type", "")
        status = "success"
        error_message = None

        try:
            if action_type == "move":
                folder = action_def.get("folder", "")
                if not folder:
                    raise ValueError("Missing 'folder' in move action")
                current_folder = email.folder or "INBOX"
                imap_service.move_email(
                    account_host,
                    account_port,
                    account_username,
                    password,
                    email.uid,
                    current_folder,
                    folder,
                )
                email.folder = folder

            elif action_type == "archive":
                current_folder = email.folder or "INBOX"
                imap_service.move_email(
                    account_host,
                    account_port,
                    account_username,
                    password,
                    email.uid,
                    current_folder,
                    "Archive",
                )
                email.folder = "Archive"

            elif action_type == "delete":
                current_folder = email.folder or "INBOX"
                # Move to trash instead of permanent delete
                imap_service.move_email(
                    account_host,
                    account_port,
                    account_username,
                    password,
                    email.uid,
                    current_folder,
                    "Trash",
                )
                email.folder = "Trash"

            elif action_type == "flag":
                flag_value = action_def.get("value", "")
                folder = email.folder or "INBOX"
                if flag_value in ("read", "seen"):
                    imap_service.set_flag(
                        account_host,
                        account_port,
                        account_username,
                        password,
                        email.uid,
                        folder,
                        "read",
                        True,
                    )
                    email.is_read = True
                elif flag_value in ("unread", "unseen"):
                    imap_service.set_flag(
                        account_host,
                        account_port,
                        account_username,
                        password,
                        email.uid,
                        folder,
                        "read",
                        False,
                    )
                    email.is_read = False
                elif flag_value in ("important", "flagged"):
                    imap_service.set_flag(
                        account_host,
                        account_port,
                        account_username,
                        password,
                        email.uid,
                        folder,
                        "important",
                        True,
                    )
                    email.is_flagged = True
                else:
                    raise ValueError(f"Unknown flag value: {flag_value}")

            elif action_type == "mark_spam":
                current_folder = email.folder or "INBOX"
                imap_service.move_email(
                    account_host,
                    account_port,
                    account_username,
                    password,
                    email.uid,
                    current_folder,
                    "Spam",
                )
                email.folder = "Spam"

            elif action_type == "block_sender":
                # Blocking is handled at the DB level (sender_service)
                # No IMAP operation needed here
                pass

            else:
                raise ValueError(f"Unknown action type: {action_type}")

        except Exception as e:
            status = "failed"
            error_message = str(e)
            logger.exception("Action '%s' failed for email %s", action_type, email.id)

        # Log the action in DB
        action_record = Action(
            email_id=email.id,
            account_id=email.account_id,
            action_type=action_type,
            action_details=action_def,
            trigger=trigger,
            rule_id=rule_id,
            status=status,
            error_message=error_message,
            is_reversible=action_type in ("move", "archive", "flag", "mark_spam"),
        )
        db.add(action_record)

        results.append(
            {
                "type": action_type,
                "status": status,
                "error": error_message,
                **({"folder": action_def.get("folder")} if action_type == "move" else {}),
            }
        )

    return results
