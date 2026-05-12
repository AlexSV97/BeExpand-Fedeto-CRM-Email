"""
Integration tests for ClassifierService with in-memory SQLite.

Covers:
- Service classifies email and stores ClassificationHistory
- Service sets Email.category on the email record
- Service handles M3_ENABLED=False (skip classification)
- Service uses the injected IClassifier to produce result
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.db.models import ClassificationHistory, ClassificationRule, Email
from src.db.session import Base
from src.email_processor.parser import EmailParsed
from src.email_processor.classifier.interfaces import ClassificationResult, IClassifier
from src.email_processor.classifier.rule_engine import RuleEngineClassifier
from src.email_processor.classifier.service import ClassifierService


@pytest_asyncio.fixture
async def in_memory_session():
    """Provide an async session backed by in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def account(in_memory_session):
    """Create a minimal Account record for FK references."""
    from src.db.models import Account
    acc = Account(
        id="acc-test-1",
        name="Test Account",
        email_host="imap.test.com",
        email_port=993,
        email_user="user@test.com",
        email_pass="pass",
    )
    in_memory_session.add(acc)
    await in_memory_session.commit()
    return acc


@pytest_asyncio.fixture
async def email_record(in_memory_session, account):
    """Create a minimal Email record for classification."""
    from src.db.models import Email as EmailModel
    email = EmailModel(
        id="email-test-1",
        account_id=account.id,
        message_id="msg-001",
        subject="Factura mensual de servicios",
        body_plain="Adjuntamos la factura correspondiente al mes.",
        body_html="",
        sender_email="facturas@suministros.com",
        sender_name="Suministros SA",
        recipients=[{"email": "comercial@beexpand.com", "name": "Comercial", "type": "to"}],
        has_attachments=False,
        category="pendiente",
        received_at=datetime.now(timezone.utc),
        processed_at=None,
    )
    in_memory_session.add(email)
    await in_memory_session.commit()
    return email


@pytest_asyncio.fixture
async def classification_rules(in_memory_session):
    """Seed classification rules in DB for integration tests."""
    rules = [
        ClassificationRule(
            id="rule-int-1", category="proveedor", keywords=["factura"],
            match_fields=["subject"], priority=10, confidence=0.9,
        ),
        ClassificationRule(
            id="rule-int-2", category="lead", keywords=["presupuesto"],
            match_fields=["subject"], priority=20, confidence=0.8,
        ),
    ]
    for r in rules:
        in_memory_session.add(r)
    await in_memory_session.commit()
    return rules


@pytest.mark.asyncio
async def test_classifier_service_stores_classification_history(
    in_memory_session, email_record, classification_rules,
):
    """Service classifies email and creates a ClassificationHistory record."""
    # Build rule engine from pre-loaded rules (no DB re-query needed for this test)
    engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
    service = ClassifierService(
        classifier=engine,
        session=in_memory_session,
        m3_enabled=True,
    )

    email_parsed = EmailParsed(
        message_id=email_record.message_id,
        subject=email_record.subject,
        body_plain=email_record.body_plain or "",
        body_html=email_record.body_html or "",
        sender_email=email_record.sender_email,
        sender_name=email_record.sender_name or "",
        recipients=["comercial@beexpand.com"],
        date=email_record.received_at,
    )

    result = await service.classify(email=email_parsed, email_id=email_record.id)

    assert result.category == "proveedor"
    assert result.confidence == 0.9

    # Verify ClassificationHistory was stored
    stmt = select(ClassificationHistory).where(
        ClassificationHistory.email_id == email_record.id
    )
    hist_result = await in_memory_session.execute(stmt)
    history = hist_result.scalar_one_or_none()
    assert history is not None, "ClassificationHistory should have been created"
    assert history.category == "proveedor"
    assert history.confidence == 0.9
    assert history.method == "rule_engine"
    assert history.details is not None
    assert history.details.get("matched_rule_id") == "rule-int-1"


@pytest.mark.asyncio
async def test_classifier_service_updates_email_category(
    in_memory_session, email_record, classification_rules,
):
    """Service updates the Email record's category field."""
    engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
    service = ClassifierService(
        classifier=engine,
        session=in_memory_session,
        m3_enabled=True,
    )

    email_parsed = EmailParsed(
        message_id=email_record.message_id,
        subject=email_record.subject,
        body_plain=email_record.body_plain or "",
        body_html="",
        sender_email=email_record.sender_email,
        sender_name=email_record.sender_name or "",
        recipients=["comercial@beexpand.com"],
        date=email_record.received_at,
    )

    await service.classify(email=email_parsed, email_id=email_record.id)

    # Verify Email.category was updated
    await in_memory_session.refresh(email_record)
    assert email_record.category == "proveedor"


@pytest.mark.asyncio
async def test_classifier_service_skips_when_m3_disabled(
    in_memory_session, email_record, classification_rules,
):
    """When M3_ENABLED=False, service skips classification entirely."""
    engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
    service = ClassifierService(
        classifier=engine,
        session=in_memory_session,
        m3_enabled=False,
    )

    email_parsed = EmailParsed(
        message_id=email_record.message_id,
        subject=email_record.subject,
        body_plain=email_record.body_plain or "",
        body_html="",
        sender_email=email_record.sender_email,
        sender_name=email_record.sender_name or "",
        recipients=["comercial@beexpand.com"],
        date=email_record.received_at,
    )

    result = await service.classify(email=email_parsed, email_id=email_record.id)

    # Should return a nulo result
    assert result.category == "nulo"
    assert result.confidence == 0.0
    assert result.method == "skipped"

    # Should NOT update Email.category
    await in_memory_session.refresh(email_record)
    assert email_record.category == "pendiente"

    # Should NOT create ClassificationHistory
    stmt = select(ClassificationHistory).where(
        ClassificationHistory.email_id == email_record.id
    )
    hist_result = await in_memory_session.execute(stmt)
    history = hist_result.scalar_one_or_none()
    assert history is None, "No ClassificationHistory should be created when M3 is disabled"


@pytest.mark.asyncio
async def test_classifier_service_with_no_rules_returns_nulo(
    in_memory_session, email_record,
):
    """With no rules loaded, service returns Nulo and stores it."""
    engine = RuleEngineClassifier(session=in_memory_session, rules=[])
    service = ClassifierService(
        classifier=engine,
        session=in_memory_session,
        m3_enabled=True,
    )

    email_parsed = EmailParsed(
        message_id=email_record.message_id,
        subject=email_record.subject,
        body_plain=email_record.body_plain or "",
        body_html="",
        sender_email=email_record.sender_email,
        sender_name=email_record.sender_name or "",
        recipients=["comercial@beexpand.com"],
        date=email_record.received_at,
    )

    result = await service.classify(email=email_parsed, email_id=email_record.id)

    assert result.category == "nulo"
    assert result.confidence == 0.0

    # Even nulo should be stored in ClassificationHistory
    stmt = select(ClassificationHistory).where(
        ClassificationHistory.email_id == email_record.id
    )
    hist_result = await in_memory_session.execute(stmt)
    history = hist_result.scalar_one_or_none()
    assert history is not None, "Nulo classification should still be stored"
    assert history.category == "nulo"
    assert history.confidence == 0.0

    # Email.category should be updated to nulo
    await in_memory_session.refresh(email_record)
    assert email_record.category == "nulo"
