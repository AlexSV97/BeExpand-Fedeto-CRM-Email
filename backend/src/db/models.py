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
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
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
    method: Mapped[str] = mapped_column(String(20), nullable=False)
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
