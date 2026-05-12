"""
Classifier package — email classification subsystem.

Provides:
- ClassificationResult: dataclass for classification output
- IClassifier: Protocol for classifier implementations
- RuleEngineClassifier: keyword-based rule evaluation engine
- ClassifierService: orchestration layer for the pipeline
"""

from src.email_processor.classifier.interfaces import ClassificationResult, IClassifier
from src.email_processor.classifier.rule_engine import RuleEngineClassifier
from src.email_processor.classifier.service import ClassifierService

__all__ = [
    "ClassificationResult",
    "IClassifier",
    "RuleEngineClassifier",
    "ClassifierService",
]
