"""
RuleEngineClassifier — keyword-based rule evaluation engine.

Evaluates classification rules ordered by priority against parsed email fields.
First matching rule determines the category. No match → Nulo with confidence 0.0.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ClassificationRule
from src.email_processor.parser import EmailParsed
from src.email_processor.classifier.interfaces import ClassificationResult

logger = logging.getLogger(__name__)

# Fields on EmailParsed that can be matched against
MATCHABLE_FIELDS = ["subject", "sender_email", "sender_name", "body_plain"]


class RuleEngineClassifier:
    """Classifies emails by evaluating keyword-based rules in priority order.

    Can be initialized with an optional pre-loaded list of rules for testing
    (no DB required). When `rules` is None, rules are loaded from the database
    via the provided session.

    The classifier performs case-insensitive substring matching of each keyword
    against the specified match_fields on the EmailParsed object.
    """

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        rules: Optional[list[ClassificationRule]] = None,
    ):
        """Initialize the classifier.

        Args:
            session: AsyncSession for loading rules from DB (required if rules is None).
            rules: Pre-loaded list of ClassificationRule instances (for testing).
                   If provided, session is not used for loading rules.
        """
        self._session = session
        self._rules = rules

    async def classify(self, email: EmailParsed) -> ClassificationResult:
        """Evaluate rules in priority order and return the first match.

        Args:
            email: The parsed email to classify.

        Returns:
            ClassificationResult with:
                - category: matched rule's category, or 'nulo' if no match.
                - confidence: matched rule's confidence, or 0.0 if no match.
                - method: 'rule_engine'.
                - details: dict with matched_rule_id, matched_keyword, matched_field,
                  or None if no match.
        """
        rules = await self._get_rules()

        for rule in rules:
            if not rule.keywords:
                continue

            match = self._evaluate_rule(rule, email)
            if match:
                logger.debug(
                    "Rule %s matched: category=%s, keyword='%s', field='%s'",
                    rule.id, rule.category, match["keyword"], match["field"],
                )
                return ClassificationResult(
                    category=rule.category,
                    confidence=rule.confidence,
                    method="rule_engine",
                    details={
                        "matched_rule_id": rule.id,
                        "matched_keyword": match["keyword"],
                        "matched_field": match["field"],
                        "rule_category": rule.category,
                        "rule_priority": rule.priority,
                    },
                )

        return ClassificationResult(
            category="nulo",
            confidence=0.0,
            method="rule_engine",
            details=None,
        )

    async def _get_rules(self) -> list[ClassificationRule]:
        """Return the list of rules, loading from DB if not pre-loaded.

        Returns:
            List of ClassificationRule instances sorted by priority ASC.
        """
        if self._rules is not None:
            # Pre-loaded rules (testing mode or cached)
            return sorted(self._rules, key=lambda r: r.priority)

        if self._session is None:
            logger.warning("No session and no rules provided — returning empty list")
            return []

        result = await self._session.execute(
            select(ClassificationRule)
            .where(ClassificationRule.active.is_(True))
            .order_by(ClassificationRule.priority)
        )
        return list(result.scalars().all())

    def _evaluate_rule(
        self, rule: ClassificationRule, email: EmailParsed
    ) -> Optional[dict]:
        """Check if any keyword in the rule matches the email's relevant fields.

        Args:
            rule: The rule to evaluate.
            email: The parsed email.

        Returns:
            Dict with 'keyword' and 'field' of the first match, or None if no match.
        """
        fields_to_check = rule.match_fields if rule.match_fields else MATCHABLE_FIELDS

        for field in fields_to_check:
            field_value = self._get_field_value(email, field)
            if not field_value:
                continue

            field_lower = field_value.lower()

            for keyword in rule.keywords:
                if keyword.lower() in field_lower:
                    return {"keyword": keyword, "field": field}

        return None

    def _get_field_value(self, email: EmailParsed, field: str) -> Optional[str]:
        """Safely extract a field value from EmailParsed.

        Args:
            email: The parsed email.
            field: The field name to extract.

        Returns:
            The field value as a string, or None if the field doesn't exist.
        """
        return getattr(email, field, None)
