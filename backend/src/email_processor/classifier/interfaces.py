"""
Interfaces for the classifier module.

Defines the ClassificationResult data transfer object and the IClassifier
Protocol that all classifiers (RuleEngine, future ML) must implement.
"""

from dataclasses import dataclass, field
from typing import Protocol

from src.email_processor.parser import EmailParsed


@dataclass
class ClassificationResult:
    """Result of classifying an email.

    Attributes:
        category: One of 'cliente', 'lead', 'proveedor', 'nulo'.
        confidence: Float between 0.0 and 1.0.
        method: Identifier for the classifier used ('rule_engine', 'ml_classifier', 'manual', 'skipped').
        details: Optional dict with classifier-specific metadata (matched rule, keyword, etc.).
    """
    category: str = "nulo"
    confidence: float = 0.0
    method: str = "rule_engine"
    details: dict | None = None


class IClassifier(Protocol):
    """Protocol that all classifiers must implement.

    Enables Strategy Pattern — swap RuleEngine for ML classifier later
    without changing the pipeline code.
    """

    async def classify(self, email: EmailParsed) -> ClassificationResult:
        """Classify a parsed email and return a ClassificationResult.

        Args:
            email: The parsed email to classify.

        Returns:
            ClassificationResult with category, confidence, method, and details.
        """
        ...
