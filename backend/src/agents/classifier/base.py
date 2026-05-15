"""
BaseClassifierAgent — clase base para todos los sub-agentes de clasificación.

Cada sub-agente implementa `classify(subject, body) → ClassifierVote`.
El Orchestrator recolecta todos los votos y los resuelve.
"""

from abc import ABC, abstractmethod

from src.orchestrator.context import ClassifierVote


class BaseClassifierAgent(ABC):
    """Clase base para agentes de clasificación."""

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Nombre único del agente (rule_engine, bert, llm)."""
        ...

    @abstractmethod
    async def classify(self, subject: str, body: str) -> ClassifierVote:
        """
        Clasifica un email y retorna un voto.

        Args:
            subject: Asunto del email.
            body: Cuerpo del email en texto plano.

        Returns:
            ClassifierVote con categoría, confianza y razón.
        """
        ...
