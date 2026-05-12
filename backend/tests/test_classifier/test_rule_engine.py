"""
Tests for RuleEngineClassifier — pure logic, no DB required.

Covers:
- Keyword match in subject → correct category + confidence
- Keyword match in body_plain
- Keyword match in sender_email
- Keyword match in sender_name
- Higher priority rule wins over lower priority (both match)
- No match → Nulo with confidence 0.0
- Field scoping: rule with match_fields=["sender_name"] ignores subject keywords
- Case-insensitive matching
- Rule with empty keywords list never matches
"""

from datetime import datetime

import pytest

from src.email_processor.parser import EmailParsed
from src.db.models import ClassificationRule
from src.email_processor.classifier.interfaces import ClassificationResult
from src.email_processor.classifier.rule_engine import RuleEngineClassifier


class TestRuleEngineClassifier:
    """Battery of unit tests for the RuleEngineClassifier matching logic."""

    @pytest.mark.asyncio
    async def test_keyword_in_subject_matches_correct_category(self):
        """Rule with keyword in subject returns the correct category and confidence."""
        rules = [
            ClassificationRule(
                id="r1", category="cliente", keywords=["factura"],
                match_fields=["subject"], priority=10, confidence=0.9,
            ),
        ]
        email = EmailParsed(
            subject="Factura mensual",
            body_plain="Cuerpo del email sin keywords",
            sender_email="remitente@test.com",
            sender_name="Remitente Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "cliente"
        assert result.confidence == 0.9
        assert result.method == "rule_engine"
        assert result.details is not None
        assert result.details["matched_keyword"] == "factura"
        assert result.details["matched_field"] == "subject"
        assert result.details["matched_rule_id"] == "r1"

    @pytest.mark.asyncio
    async def test_keyword_in_body_matches(self):
        """Rule with keyword in body_plain returns correct category."""
        rules = [
            ClassificationRule(
                id="r2", category="lead", keywords=["presupuesto"],
                match_fields=["body_plain"], priority=20, confidence=0.8,
            ),
        ]
        email = EmailParsed(
            subject="Re: Consulta",
            body_plain="Estoy interesado en un presupuesto para reformas.",
            sender_email="cliente@test.com",
            sender_name="Cliente Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "lead"
        assert result.confidence == 0.8
        assert result.details["matched_keyword"] == "presupuesto"
        assert result.details["matched_field"] == "body_plain"

    @pytest.mark.asyncio
    async def test_keyword_in_sender_email_matches(self):
        """Rule with keyword in sender_email returns correct category."""
        rules = [
            ClassificationRule(
                id="r3", category="proveedor", keywords=["suministros"],
                match_fields=["sender_email"], priority=5, confidence=0.85,
            ),
        ]
        email = EmailParsed(
            subject="Nueva cotización",
            body_plain="Adjunto cotización para materiales.",
            sender_email="ventas@suministros-sa.com",
            sender_name="Suministros SA",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "proveedor"
        assert result.confidence == 0.85
        assert result.details["matched_keyword"] == "suministros"
        assert result.details["matched_field"] == "sender_email"

    @pytest.mark.asyncio
    async def test_keyword_in_sender_name_matches(self):
        """Rule with keyword in sender_name returns correct category."""
        rules = [
            ClassificationRule(
                id="r4", category="proveedor", keywords=["suministros"],
                match_fields=["sender_name"], priority=5, confidence=0.85,
            ),
        ]
        email = EmailParsed(
            subject="Nuevo pedido",
            body_plain="Queremos hacer un pedido",
            sender_email="ventas@proveedor.com",
            sender_name="Suministros Generales SA",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "proveedor"
        assert result.details["matched_keyword"] == "suministros"
        assert result.details["matched_field"] == "sender_name"

    @pytest.mark.asyncio
    async def test_higher_priority_wins_when_both_match(self):
        """When multiple rules match, the one with lowest priority number wins."""
        rules = [
            ClassificationRule(
                id="r5", category="cliente", keywords=["pedido"],
                match_fields=["subject"], priority=20, confidence=0.9,
            ),
            ClassificationRule(
                id="r6", category="lead", keywords=["pedido"],
                match_fields=["subject"], priority=10, confidence=0.7,
            ),
        ]
        email = EmailParsed(
            subject="Pedido de materiales",
            body_plain="Cuerpo del email",
            sender_email="test@test.com",
            sender_name="Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        # Rule r6 has priority 10 (lower number = higher priority)
        assert result.category == "lead"
        assert result.confidence == 0.7
        assert result.details["matched_rule_id"] == "r6"

    @pytest.mark.asyncio
    async def test_no_match_returns_nulo_with_zero_confidence(self):
        """When no rule matches, return Nulo with confidence 0.0."""
        rules = [
            ClassificationRule(
                id="r7", category="cliente", keywords=["factura"],
                match_fields=["subject"], priority=10, confidence=0.9,
            ),
        ]
        email = EmailParsed(
            subject="Hola, ¿cómo estás?",
            body_plain="Charla informal sin keywords comerciales",
            sender_email="amigo@personal.com",
            sender_name="Amigo",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "nulo"
        assert result.confidence == 0.0
        assert result.method == "rule_engine"

    @pytest.mark.asyncio
    async def test_field_scoping_sender_name_ignores_subject_keywords(self):
        """Rule with match_fields=['sender_name'] does NOT match keyword in subject."""
        rules = [
            ClassificationRule(
                id="r8", category="proveedor", keywords=["factura"],
                match_fields=["sender_name"], priority=10, confidence=0.9,
            ),
        ]
        email = EmailParsed(
            subject="Factura mensual",
            body_plain="Cuerpo normal",
            sender_email="test@test.com",
            sender_name="Juan Pérez",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        # "factura" is in subject, but rule only checks sender_name
        assert result.category == "nulo"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self):
        """Keyword matching is case-insensitive."""
        rules = [
            ClassificationRule(
                id="r9", category="cliente", keywords=["FACTURA"],
                match_fields=["subject"], priority=10, confidence=0.9,
            ),
        ]
        email = EmailParsed(
            subject="factura mensual de servicios",
            body_plain="",
            sender_email="test@test.com",
            sender_name="Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "cliente"

    @pytest.mark.asyncio
    async def test_empty_keywords_list_never_matches(self):
        """A rule with empty keywords list should never match (acts as never-match)."""
        rules = [
            ClassificationRule(
                id="r10", category="cliente", keywords=[],
                match_fields=["subject"], priority=1, confidence=0.9,
            ),
            ClassificationRule(
                id="r11", category="lead", keywords=["interesado"],
                match_fields=["subject"], priority=2, confidence=0.8,
            ),
        ]
        email = EmailParsed(
            subject="Estoy interesado en sus servicios",
            body_plain="",
            sender_email="test@test.com",
            sender_name="Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        # r10 has empty keywords, should not match. r11 should match.
        assert result.category == "lead"
        assert result.details["matched_rule_id"] == "r11"

    @pytest.mark.asyncio
    async def test_no_rules_returns_nulo(self):
        """When there are no rules at all, return Nulo."""
        engine = RuleEngineClassifier(session=None, rules=[])
        email = EmailParsed(
            subject="Cualquier asunto",
            body_plain="Cualquier cuerpo",
            sender_email="test@test.com",
            sender_name="Test",
        )
        result = await engine.classify(email)

        assert result.category == "nulo"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_rules_sorted_by_priority_on_load(self):
        """Rules are evaluated in priority order regardless of input order."""
        rules = [
            ClassificationRule(
                id="r12", category="lead", keywords=["presupuesto"],
                match_fields=["subject"], priority=30, confidence=0.7,
            ),
            ClassificationRule(
                id="r13", category="cliente", keywords=["presupuesto"],
                match_fields=["subject"], priority=10, confidence=0.9,
            ),
            ClassificationRule(
                id="r14", category="proveedor", keywords=["presupuesto"],
                match_fields=["subject"], priority=20, confidence=0.8,
            ),
        ]
        email = EmailParsed(
            subject="Solicitud de presupuesto",
            body_plain="",
            sender_email="test@test.com",
            sender_name="Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        # r13 has priority 10 (lowest) → should match first
        assert result.category == "cliente"
        assert result.details["matched_rule_id"] == "r13"

    @pytest.mark.asyncio
    async def test_match_all_fields_when_match_fields_empty(self):
        """When match_fields is empty, search ALL email text fields."""
        rules = [
            ClassificationRule(
                id="r15", category="lead", keywords=["interesado"],
                match_fields=[], priority=10, confidence=0.8,
            ),
        ]
        email = EmailParsed(
            subject="Re: Consulta general",
            body_plain="Estoy interesado en recibir información.",
            sender_email="lead@test.com",
            sender_name="Lead Test",
        )
        engine = RuleEngineClassifier(session=None, rules=rules)
        result = await engine.classify(email)

        assert result.category == "lead"
