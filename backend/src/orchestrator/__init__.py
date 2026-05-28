"""Orquestador de agentes — coordinación, contexto y resolución."""

from src.orchestrator.context import (
    ActionResult,
    AnalyzerResult,
    ClassifierVote,
    EmailContext,
    EmailData,
    ExtractedInfo,
    RoutingDecision,
)
from src.orchestrator.resolver import VoteResolver


def __getattr__(name):
    """Lazy imports to avoid circular dependency (orchestrator ↔ agents)."""
    if name == "Orchestrator":
        from src.orchestrator.orchestrator import Orchestrator as _o
        return _o
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "EmailContext",
    "EmailData",
    "ExtractedInfo",
    "ClassifierVote",
    "AnalyzerResult",
    "RoutingDecision",
    "ActionResult",
    "Orchestrator",
    "VoteResolver",
]
