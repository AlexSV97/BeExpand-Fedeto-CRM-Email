"""
EmailContext — contrato compartido entre todos los agentes del orquestador.

Cada agente lee del contexto y escribe sus resultados en él.
El flujo completo:

1. Orchestrator recibe EmailData (desde IMAP fetcher)
2. Crea EmailContext con raw data
3. Lanza agentes en paralelo/secuencia:
   a. Analyzer → escribe extracted
   b. Classifier sub-agents → escriben votes[]
   c. Resolver → escribe final_category, final_confidence, resolution
   d. Router → escribe routing
   e. ActionExecutor → escribe actions[]
4. Retorna EmailContext completo como resultado
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ── Enumeraciones compartidas ──


class Category(str, Enum):
    """Categorías de clasificación del sistema."""

    CLIENTE = "cliente"
    LEAD = "lead"
    PROVEEDOR = "proveedor"
    NULO = "nulo"

    @classmethod
    def valid_categories(cls) -> list[str]:
        return [c.value for c in cls]


class ResolutionMethod(str, Enum):
    """Método usado para resolver la categoría final."""
    CONSENSUS = "consensus"
    MAJORITY = "majority"
    LLM_JUDGE = "llm_judge"
    FALLBACK = "fallback"


class Urgency(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class Department(str, Enum):
    """Departamentos a los que se puede enrutar un email."""
    CONTABILIDAD = "contabilidad"
    SOPORTE = "soporte"
    COMERCIAL = "comercial"
    PROVEEDORES = "proveedores"
    DIRECCION = "direccion"
    OTRO = "otro"


# ── Datos de entrada ──


@dataclass
class EmailData:
    """Datos crudos del email tal como salen del parseo IMAP."""

    message_id: str | None
    subject: str | None
    body_plain: str | None
    body_html: str | None
    sender_name: str
    sender_email: str
    recipients: list[str] = field(default_factory=list)
    has_attachments: bool = False
    received_at: datetime | None = None
    raw_headers: dict | None = None


# ── Resultados de agentes ──


@dataclass
class ExtractedInfo:
    """Información estructurada extraída por el Analyzer Agent."""

    company: str | None = None          # Empresa del remitente (si se deduce)
    position: str | None = None         # Cargo del remitente
    urgency: str = "media"              # alta | media | baja
    action_required: str | None = None  # pago | soporte | consulta | reunion | compra | otro
    action_description: str | None = None
    entities: dict = field(default_factory=dict)  # fechas, montos, referencias
    tone: str | None = None             # formal | informal | urgente | cordial
    summary: str | None = None          # Resumen 1-2 frases en español


@dataclass
class AnalyzerResult:
    """Resultado completo del Analyzer Agent."""
    success: bool
    extracted: ExtractedInfo | None = None
    error: str | None = None
    processing_time_ms: float = 0.0


@dataclass
class ClassifierVote:
    """Voto de un sub-agente del clasificador."""

    agent_name: str                     # rule_engine | bert | llm
    category: str                       # cliente | lead | proveedor | nulo
    confidence: float                   # 0.0 - 1.0
    reason: str | None = None           # Por qué votó así
    details: dict | None = None         # Metadatos adicionales


@dataclass
class RoutingDecision:
    """Decisión de enrutamiento del Router Agent."""

    departments: list[str] = field(default_factory=list)  # departamentos destino
    persons: list[str] = field(default_factory=list)      # personas específicas (si se sabe)
    rationale: str | None = None                          # Por qué se enrutó así
    priority: str = "normal"                              # normal | alta | urgente


@dataclass
class ActionResult:
    """Resultado de una acción ejecutada por el Action Executor."""

    action: str          # db_save | crm_sync | email_forward | dashboard_notify
    success: bool
    detail: str | None = None


# ── Contexto principal ──


@dataclass
class EmailContext:
    """
    Contexto compartido del email en proceso.

    Flujo de llenado:
    1. raw          ← Orchestrator (desde fetcher)
    2. extracted    ← Analyzer Agent
    3. votes[]      ← Classifier sub-agents (cada uno añade un voto)
    4. final_*      ← VoteResolver
    5. routing      ← Router Agent
    6. actions[]    ← Action Executor (cada acción se registra)
    """

    # Fase 1: Datos crudos (lo pone el Orchestrator)
    raw: EmailData

    # Fase 2: Análisis (lo escribe el Analyzer Agent)
    extracted: ExtractedInfo | None = None
    analyzer_result: AnalyzerResult | None = None

    # Fase 3: Votos de clasificación (los escriben los sub-agentes)
    votes: list[ClassifierVote] = field(default_factory=list)

    # Fase 4: Decisión final (lo escribe el VoteResolver)
    final_category: str | None = None
    final_confidence: float = 0.0
    resolution_method: str | None = None  # consensus | majority | llm_judge | fallback

    # Fase 5: Enrutamiento (lo escribe el Router Agent)
    routing: RoutingDecision | None = None

    # Fase 6: Acciones ejecutadas (lo escribe el Action Executor)
    actions: list[ActionResult] = field(default_factory=list)

    # Fase 6b: Borrador de respuesta (lo escribe el ReplySuggesterAgent)
    suggested_reply: str = ""

    # Metadatos del proceso
    processing_start: datetime | None = None
    processing_end: datetime | None = None
    error: str | None = None

    @property
    def processing_time_ms(self) -> float:
        if self.processing_start and self.processing_end:
            return (self.processing_end - self.processing_start).total_seconds() * 1000
        return 0.0

    @property
    def is_nulo(self) -> bool:
        """El email se considera spam/pendiente sin acción."""
        return self.final_category == Category.NULO.value

    @property
    def summary_dict(self) -> dict:
        """Resumen plano para respuestas API y dashboard."""
        return {
            "message_id": self.raw.message_id,
            "subject": self.raw.subject,
            "sender_name": self.raw.sender_name,
            "sender_email": self.raw.sender_email,
            "category": self.final_category,
            "confidence": self.final_confidence,
            "resolution": self.resolution_method,
            "votes": [
                {"agent": v.agent_name, "category": v.category, "confidence": v.confidence}
                for v in self.votes
            ],
            "summary": self.extracted.summary if self.extracted else None,
            "urgency": self.extracted.urgency if self.extracted else "media",
            "routing": {
                "departments": self.routing.departments if self.routing else [],
                "persons": self.routing.persons if self.routing else [],
            },
            "actions": [
                {"action": a.action, "success": a.success, "detail": a.detail}
                for a in self.actions
            ],
            "processing_time_ms": self.processing_time_ms,
            "error": self.error,
        }
