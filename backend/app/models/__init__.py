"""Import all ORM models so they register with Base.metadata for Alembic."""

from app.models.account import Account, AccountSettings
from app.models.action import Action
from app.models.activity_log import ActivityLog
from app.models.classification import Classification, Correction
from app.models.email import Email, EmailThread, EmailUrl
from app.models.newsletter import Newsletter
from app.models.rule import Rule
from app.models.sender_profile import SenderCategoryStats, SenderProfile
from app.models.settings import Settings

__all__ = [
    "Account",
    "AccountSettings",
    "Action",
    "ActivityLog",
    "Classification",
    "Correction",
    "Email",
    "EmailThread",
    "EmailUrl",
    "Newsletter",
    "Rule",
    "SenderCategoryStats",
    "SenderProfile",
    "Settings",
]
