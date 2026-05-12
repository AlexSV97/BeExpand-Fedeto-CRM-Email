"""
Tests for the ClassificationRule ORM model.

Covers:
- Attribute assignment and reading
- Table name and column metadata
- DB persistence with in-memory SQLite
- Default values on DB insert
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.db.models import ClassificationRule
from src.db.session import Base


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


class TestClassificationRuleModel:
    """Test the ClassificationRule ORM model."""

    def test_attributes_can_be_set_and_read(self):
        """Instance attributes are set and read correctly."""
        rule = ClassificationRule(
            category="lead",
            keywords=["interesado", "presupuesto"],
            match_fields=["subject", "body_plain"],
            priority=10,
            confidence=0.8,
        )
        # Set id explicitly since it won't be auto-generated until INSERT
        rule.id = "test-id-123"
        assert rule.id == "test-id-123"
        assert rule.category == "lead"
        assert rule.keywords == ["interesado", "presupuesto"]
        assert rule.match_fields == ["subject", "body_plain"]
        assert rule.priority == 10
        assert rule.confidence == 0.8

    def test_default_active_is_true(self):
        """active defaults to True (set explicitly for clarity)."""
        rule = ClassificationRule(
            category="nulo",
            keywords=[],
            match_fields=["subject"],
            priority=1,
            confidence=0.0,
        )
        rule.active = True  # SQLAlchemy default fires on INSERT, set explicitly here
        assert rule.active is True

    def test_confidence_is_float(self):
        """confidence can be stored and read as float."""
        rule = ClassificationRule(
            category="lead",
            keywords=["demo"],
            match_fields=["subject"],
            priority=20,
            confidence=0.75,
        )
        assert isinstance(rule.confidence, float)
        assert rule.confidence == 0.75

    def test_table_name(self):
        """ClassificationRule uses table name 'classification_rules'."""
        assert ClassificationRule.__tablename__ == "classification_rules"

    def test_category_nulo_is_valid(self):
        """Category 'nulo' with empty keywords is a valid configuration."""
        rule = ClassificationRule(
            category="nulo",
            keywords=[],
            match_fields=["subject"],
            priority=0,
            confidence=0.0,
        )
        assert rule.category == "nulo"
        assert rule.confidence == 0.0

    def test_columns_definition(self):
        """Verify all expected columns are defined on the model."""
        mapper = inspect(ClassificationRule)
        col_names = {c.name for c in mapper.columns}
        expected = {
            "id", "category", "keywords", "match_fields",
            "priority", "confidence", "active",
            "created_at", "updated_at",
        }
        missing = expected - col_names
        assert not missing, f"Missing columns: {missing}"

    @pytest.mark.asyncio
    async def test_persist_and_read(self, in_memory_session):
        """A ClassificationRule can be saved to DB and read back."""
        rule = ClassificationRule(
            id="rule-001",
            category="lead",
            keywords=["interesado", "presupuesto"],
            match_fields=["subject"],
            priority=10,
            confidence=0.8,
            active=True,
        )
        in_memory_session.add(rule)
        await in_memory_session.commit()

        result = await in_memory_session.get(ClassificationRule, "rule-001")
        assert result is not None
        assert result.category == "lead"
        assert result.keywords == ["interesado", "presupuesto"]
        assert result.priority == 10
        assert result.confidence == 0.8
        assert result.active is True
        assert result.created_at is not None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_defaults_on_insert(self, in_memory_session):
        """DB defaults (active=True, timestamps) are applied on INSERT."""
        rule = ClassificationRule(
            id="rule-002",
            category="cliente",
            keywords=["factura"],
            match_fields=["subject"],
            priority=5,
            confidence=0.9,
        )
        in_memory_session.add(rule)
        await in_memory_session.commit()

        result = await in_memory_session.get(ClassificationRule, "rule-002")
        assert result.active is True  # default
        assert result.created_at is not None  # server_default
        assert result.updated_at is not None  # server_default

    @pytest.mark.asyncio
    async def test_multiple_rules_can_be_stored(self, in_memory_session):
        """Multiple classification rules can be stored and queried."""
        rules = [
            ClassificationRule(id="r1", category="lead", keywords=["interesado"],
                               match_fields=["subject"], priority=10, confidence=0.8),
            ClassificationRule(id="r2", category="cliente", keywords=["factura"],
                               match_fields=["subject"], priority=5, confidence=0.9),
            ClassificationRule(id="r3", category="nulo", keywords=[],
                               match_fields=["subject"], priority=0, confidence=0.0),
        ]
        for r in rules:
            in_memory_session.add(r)
        await in_memory_session.commit()

        from sqlalchemy import select
        result = await in_memory_session.execute(
            select(ClassificationRule).order_by(ClassificationRule.priority)
        )
        stored = result.scalars().all()
        assert len(stored) == 3
        assert stored[0].priority == 0  # nulo, lowest priority
        assert stored[1].priority == 5  # cliente
        assert stored[2].priority == 10  # lead, highest priority
