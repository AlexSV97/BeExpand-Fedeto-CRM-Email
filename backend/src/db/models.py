"""
Modelos SQLAlchemy 2.0 — Traducidos del diseño en docs/data-model.md

7 entidades que reflejan el modelo de datos acordado.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


# ── Enums compartidos ──

class ContactCategory(str, Enum):
    CLIENTE = "cliente"
    LEAD = "lead"
    PROVEEDOR = "proveedor"
    OTRO = "otro"
    PENDIENTE = "pendiente"


class EmailRelevance(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class EmailStatus(str, Enum):
    PENDIENTE = "pendiente"
    EN_SEGUIMIENTO = "en_seguimiento"
    CERRADO = "cerrado"
    ESCALADO = "escalado"


class ClassificationMethod(str, Enum):
    RULE_ENGINE = "rule_engine"
    ML_CLASSIFIER = "ml_classifier"
    MANUAL = "manual"


class OpportunityStage(str, Enum):
    NUEVA = "nueva"
    CALIFICADA = "calificada"
    PROPUESTA = "propuesta"
    NEGOCIACION = "negociacion"
    CERRADA_GANADA = "cerrada_ganada"
    CERRADA_PERDIDA = "cerrada_perdida"


class UserRole(str, Enum):
    ADMIN = "admin"
    VIEWER = "viewer"


# ── Modelos ──

class Account(Base):
    """Buzón IMAP que el sistema monitoriza."""
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email_host: Mapped[str] = mapped_column(String(255), nullable=False)
    email_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    email_user: Mapped[str] = mapped_column(String(255), nullable=False)
    email_pass: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    emails: Mapped[list["Email"]] = relationship("Email", back_populates="account")


class Email(Base):
    """Correo procesado por el sistema."""
    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    message_id: Mapped[Optional[str]] = mapped_column(String(255))
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body_plain: Mapped[Optional[str]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255))
    recipients: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    category: Mapped[Optional[str]] = mapped_column(String(20), default="pendiente")
    relevance: Mapped[Optional[str]] = mapped_column(String(10), default="media")
    status: Mapped[Optional[str]] = mapped_column(String(20), default="pendiente")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    otrs_ticket_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None
    )
    otrs_ticket_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("message_id", "account_id", name="uq_message_id_account"),
    )

    # Relaciones
    account: Mapped["Account"] = relationship("Account", back_populates="emails")
    classification_history: Mapped[list["ClassificationHistory"]] = relationship(
        "ClassificationHistory", back_populates="email", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship("Opportunity", back_populates="email")
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", secondary="email_contacts", back_populates="emails"
    )


class Contact(Base):
    """Contacto sincronizado con VTiger."""
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crm_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    company: Mapped[Optional[str]] = mapped_column(String(255))
    position: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(20), default="otro")
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(50), default="email")
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    first_email_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_email_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    email_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    emails: Mapped[list["Email"]] = relationship(
        "Email", secondary="email_contacts", back_populates="contacts"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship("Opportunity", back_populates="contact")


class EmailContact(Base):
    """Relación N:M entre emails y contactos."""
    __tablename__ = "email_contacts"

    email_id: Mapped[str] = mapped_column(String(36), ForeignKey("emails.id", ondelete="CASCADE"), primary_key=True)
    contact_id: Mapped[str] = mapped_column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10), primary_key=True)  # 'from' o 'to'


class ClassificationHistory(Base):
    """Traza de cada clasificación (para auditoría y futuro entrenamiento ML)."""
    __tablename__ = "classification_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id: Mapped[str] = mapped_column(String(36), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    email: Mapped["Email"] = relationship("Email", back_populates="classification_history")


class Opportunity(Base):
    """Oportunidad de negocio detectada."""
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("emails.id"))
    contact_id: Mapped[str] = mapped_column(String(36), ForeignKey("contacts.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="nueva")
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    probability: Mapped[Optional[int]] = mapped_column(Integer)
    expected_close: Mapped[Optional[date]] = mapped_column(Date)
    source: Mapped[Optional[str]] = mapped_column(String(50), default="email_automatic")
    crm_id: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    email: Mapped[Optional["Email"]] = relationship("Email", back_populates="opportunities")
    contact: Mapped["Contact"] = relationship("Contact", back_populates="opportunities")


class Setting(Base):
    """Configuración persistida en BD (key-value).
    
    Permite sobreescribir valores del .env sin modificar el archivo.
    Las claves siguen el mismo nombre que en Settings (ej: imap_server).
    """
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    """Usuario del sistema interno."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Invoice(Base):
    """Factura extraída de un adjunto de email."""
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id: Mapped[str] = mapped_column(String(36), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    numero: Mapped[Optional[str]] = mapped_column(String(100))
    proveedor: Mapped[Optional[str]] = mapped_column(String(255))
    importe: Mapped[Optional[float]] = mapped_column(Float)
    fecha: Mapped[Optional[date]] = mapped_column(Date)
    vencimiento: Mapped[Optional[date]] = mapped_column(Date)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReprocessTask(Base):
    """Tarea de reprocesado asíncrono para emails."""
    __tablename__ = "reprocess_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id: Mapped[str] = mapped_column(String(36), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | processing | completed | failed
    result_category: Mapped[Optional[str]] = mapped_column(String(20))
    result_confidence: Mapped[Optional[float]] = mapped_column(Float)
    result_resolution: Mapped[Optional[str]] = mapped_column(String(30))
    result_votes: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    processing_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class QueueModel(Base):
    """Cola OTRS persistida con jerarquía padre-hijo (CE-01).

    Fuente de verdad única para la topología de colas: reemplaza las dos
    topologías hardcoded (QueueStrategyService._topology y
    ActionExecutor.QUEUE_MAP). Se sincroniza desde OTRS con seed de fallback.

    El atributo Python `queue_metadata` mapea a la columna SQL `metadata`
    (no se puede usar `metadata` como atributo: lo reserva la Base declarativa).
    """
    __tablename__ = "queues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    tier: Mapped[Optional[str]] = mapped_column(String(20))  # n1 | n2 | n3 | special | None
    owner: Mapped[Optional[str]] = mapped_column(String(100))
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("queues.id", ondelete="SET NULL"), nullable=True
    )
    otrs_external_id: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    queue_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relación self-referencial: padre ↔ hijos
    parent: Mapped[Optional["QueueModel"]] = relationship(
        "QueueModel", remote_side="QueueModel.id", back_populates="children"
    )
    children: Mapped[list["QueueModel"]] = relationship(
        "QueueModel", back_populates="parent"
    )


class OperationalRecord(Base):
    """Registro duradero para aprobaciones, feedback, reportes y auditoría operativa."""
    __tablename__ = "operational_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    actor_kind: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

