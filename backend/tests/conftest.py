"""Shared fixtures and factories for backend tests."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import attributes

from app.llm.base import BaseLLMProvider
from app.models.classification import Classification
from app.models.email import Email
from app.models.rule import Rule

# ---------------------------------------------------------------------------
# Test encryption key (deterministic, for tests only)
# ---------------------------------------------------------------------------

TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _patch_encryption_key(monkeypatch):
    """Ensure encryption tests use a known key instead of the app config."""
    monkeypatch.setattr("app.services.encryption.settings.encryption_key", TEST_ENCRYPTION_KEY)


# ---------------------------------------------------------------------------
# Mock database session
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """AsyncSession mock — configure .execute().scalars().all() per test."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Mock LLM provider
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm():
    """Mock BaseLLMProvider that returns configurable JSON."""
    llm = AsyncMock(spec=BaseLLMProvider)
    llm.provider_name = "test"
    llm.get_model_name.return_value = "test-model"
    llm.is_available.return_value = True
    llm.generate.return_value = (
        '{"category": "newsletter", "confidence": 0.9, "explanation": "test"}'
    )
    return llm


# ---------------------------------------------------------------------------
# Model factories (no DB required)
# ---------------------------------------------------------------------------


def _make_model(cls, **kwargs):
    """Create a SQLAlchemy model instance without a session (for unit tests).

    Uses `instance_state` init to properly set up ORM instrumentation,
    then sets attributes normally.
    """
    obj = cls.__new__(cls)
    # Initialize SQLAlchemy's internal state so attribute access works
    attributes.instance_state(obj)._commit_all(attributes.instance_dict(obj))
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


def make_email(**overrides) -> Email:
    """Create an Email instance with sensible defaults (not persisted)."""
    defaults = {
        "id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "uid": 1,
        "from_address": "sender@example.com",
        "from_name": "Test Sender",
        "to_addresses": ["recipient@example.com"],
        "cc_addresses": [],
        "subject": "Test Subject",
        "body_excerpt": "Hello, this is a test email.",
        "body_html_excerpt": None,
        "has_attachments": False,
        "attachment_names": [],
        "date": datetime.now(UTC),
        "folder": "INBOX",
        "is_read": False,
        "is_flagged": False,
        "processing_status": "pending",
    }
    defaults.update(overrides)
    return _make_model(Email, **defaults)


def make_classification(**overrides) -> Classification:
    """Create a Classification instance with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "email_id": uuid.uuid4(),
        "category": "newsletter",
        "confidence": 0.85,
        "explanation": "Test classification",
        "is_spam": False,
        "is_phishing": False,
        "phishing_reasons": [],
        "status": "auto",
        "classified_by": "llm",
    }
    defaults.update(overrides)
    return _make_model(Classification, **defaults)


def make_rule(**overrides) -> Rule:
    """Create a Rule instance with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "name": "Test Rule",
        "type": "structured",
        "priority": 0,
        "is_active": True,
        "conditions": None,
        "natural_text": None,
        "category": "spam",
        "actions": [{"type": "move", "folder": "Junk"}],
        "match_count": 0,
        "last_matched_at": None,
    }
    defaults.update(overrides)
    return _make_model(Rule, **defaults)
