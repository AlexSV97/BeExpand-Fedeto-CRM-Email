"""
ClassifierService — orchestrates the classification pipeline step.

Runs between Filter and DB persistence:
  1. Check M3_ENABLED flag → skip if disabled
  2. Delegate to IClassifier.classify(email)
  3. Store ClassificationHistory record
  4. Update Email.category field
  5. Return the ClassificationResult
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ClassificationHistory, Email
from src.email_processor.parser import EmailParsed
from src.email_processor.classifier.interfaces import ClassificationResult, IClassifier

logger = logging.getLogger(__name__)


class ClassifierService:
    """Orchestrates email classification and persists results.

    The service is the integration point in the email pipeline. It:
    - Checks the M3_ENABLED feature flag
    - Delegates to the configured IClassifier implementation
    - Persists the classification result to the database
    - Updates the Email record's category field
    """

    def __init__(
        self,
        classifier: IClassifier,
        session: AsyncSession,
        m3_enabled: bool = True,
    ):
        """Initialize the service.

        Args:
            classifier: An IClassifier implementation (e.g., RuleEngineClassifier).
            session: SQLAlchemy AsyncSession for DB operations.
            m3_enabled: Feature flag — if False, classification is skipped.
        """
        self._classifier = classifier
        self._session = session
        self._m3_enabled = m3_enabled

    async def classify(
        self,
        email: EmailParsed,
        email_id: str,
    ) -> ClassificationResult:
        """Run classification for a single email and persist results.

        Args:
            email: The parsed email data to classify.
            email_id: The database ID of the Email record to update.

        Returns:
            ClassificationResult from the classifier, or a
            skipped/nulo result if M3_ENABLED is False.
        """
        if not self._m3_enabled:
            logger.info("M3_ENABLED=False — skipping classification for email %s", email_id)
            return ClassificationResult(
                category="nulo",
                confidence=0.0,
                method="skipped",
                details={"reason": "M3_ENABLED is False"},
            )

        # Step 1: Classify
        result = await self._classifier.classify(email)

        # Step 2: Store ClassificationHistory
        history = ClassificationHistory(
            email_id=email_id,
            category=result.category,
            confidence=result.confidence,
            method=result.method,
            details=result.details,
        )
        self._session.add(history)

        # Step 3: Update Email.category
        email_record = await self._session.get(Email, email_id)
        if email_record:
            email_record.category = result.category

        # Step 4: Commit
        await self._session.commit()

        logger.info(
            "Email %s classified as %s (confidence=%.2f, method=%s)",
            email_id, result.category, result.confidence, result.method,
        )

        return result
