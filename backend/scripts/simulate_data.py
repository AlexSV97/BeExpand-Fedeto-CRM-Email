"""
Simula ~30 días de actividad de email realista con patrón semanal.

Limpia cualquier simulación previa y genera datos desde 30 días atrás
hasta hoy, con distribución por categoría y estacionalidad semanal.

Uso:
    cd backend
    python scripts/simulate_data.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

DATABASE_URL = "sqlite+aiosqlite:///beexpand.db"

from sqlalchemy import or_

from src.db.models import Account, ClassificationHistory, Contact, Email, EmailContact

# ── Config ──

CATEGORY_WEIGHTS = {
    "cliente": 0.25,
    "lead": 0.30,
    "proveedor": 0.30,
    "nulo": 0.10,
    "sin_categoria": 0.05,
}

# Base de emails por día según día de la semana
# (lunes=0 ... domingo=6)
BASE_EMAILS_BY_DOW = {
    0: 18,   # lunes
    1: 15,   # martes
    2: 17,   # miércoles
    3: 14,   # jueves
    4: 12,   # viernes
    5: 2,    # sábado
    6: 3,    # domingo
}

SENDERS = [
    ("Maria Garcia", "maria.garcia@empresa.es"),
    ("Carlos Lopez", "carlos.lopez@proveedor.com"),
    ("Ana Martinez", "ana.martinez@cliente.com"),
    ("Javier Ruiz", "javier.ruiz@lead.es"),
    ("Laura Sanchez", "laura.sanchez@corp.com"),
    ("Pedro Jimenez", "pedro.jimenez@empresa.es"),
    ("Sofia Torres", "sofia.torres@startup.es"),
    ("Miguel Angel", "miguel.angel@cliente.com"),
    ("Elena Diaz", "elena.diaz@proveedor.es"),
    ("David Romero", "david.romero@lead.es"),
]

SUBJECTS_BY_CATEGORY = {
    "cliente": [
        "Solicitud de presupuesto para nuevo proyecto",
        "Confirmacion de pedido #{}",
        "Consulta sobre facturacion del servicio",
        "Renovacion del contrato anual",
        "Solicitud de ampliacion de servicio",
        "Informe de incidencia en plataforma",
        "Peticion de reunion comercial",
    ],
    "lead": [
        "Interes en sus servicios de consultoria",
        "Solicitud de informacion comercial",
        "Me gustaria recibir una demo del producto",
        "Consulta sobre precios y planes",
        "Posible colaboracion empresarial",
        "Solicitud de catalogo de servicios",
    ],
    "proveedor": [
        "Actualizacion de precios para el proximo trimestre",
        "Confirmacion de envio #{}",
        "Nuevo catalogo de productos disponibles",
        "Aviso de mantenimiento programado",
        "Factura mensual de servicios",
        "Oferta especial para clientes premium",
    ],
    "nulo": [
        "Gana un iPhone GRATIS",
        "Oferta increible, no pierdas esta oportunidad",
        "Has sido seleccionado para...",
        "Publicidad: {}",
        "Newsletter semanal de tecnologia",
        "Invitacion a webinar gratuito",
    ],
    "sin_categoria": [
        "Re: Documentacion pendiente",
        "Informacion general",
        "Comunicado interno",
        "Nota informativa",
    ],
}


def _pick(distribution: dict[str, float]) -> str:
    """Elige una categoría según su peso."""
    import random

    r = random.random()
    cumulative = 0.0
    for cat, weight in distribution.items():
        cumulative += weight
        if r <= cumulative:
            return cat
    return list(distribution.keys())[-1]


def _trend_factor(day_index: int, total_days: int) -> float:
    """Factor de tendencia: ligero crecimiento (~20% en el periodo)."""
    return 1.0 + 0.20 * (day_index / max(total_days - 1, 1))


async def main():
    import random

    random.seed(42)

    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        result = await session.execute(select(Account).limit(1))
        account = result.scalar_one_or_none()
        if not account:
            print("No se encontró ninguna cuenta. Abortando.")
            return
        account_id = account.id
        print(f"Usando cuenta: {account.name} ({account_id})")

        # ── 1. Limpiar simulaciones previas ──
        print("\nLimpiando simulaciones previas (Python-side)...")
        all_emails_result = await session.execute(
            select(Email).options(selectinload(Email.classification_history))
        )
        all_emails = all_emails_result.scalars().all()
        sim_email_ids = [
            e.id for e in all_emails
            if e.extra_data and isinstance(e.extra_data, dict) and e.extra_data.get("source") == "simulation"
        ]

        if sim_email_ids:
            for eid in sim_email_ids:
                email = next((e for e in all_emails if e.id == eid), None)
                if email:
                    for ch in email.classification_history:
                        await session.delete(ch)
                    await session.delete(email)
            await session.commit()
            print(f"  Limpiados {len(sim_email_ids)} emails simulados")
        else:
            print("  No hay simulaciones previas que limpiar")

        # Limpiar contactos de simulaciones previas (Python-side)
        all_contacts = (await session.execute(select(Contact))).scalars().all()
        sim_contacts = [
            c for c in all_contacts
            if c.extra_data and isinstance(c.extra_data, dict) and c.extra_data.get("source") == "simulation"
        ]
        for c in sim_contacts:
            await session.delete(c)
        if sim_contacts:
            await session.commit()
            print(f"  Limpiados {len(sim_contacts)} contactos simulados")

        # ── 2. Contar emails existentes (no simulación) ──
        from sqlalchemy import func as safunc

        result = await session.execute(
            select(safunc.date(Email.received_at), safunc.count(Email.id))
            .group_by(safunc.date(Email.received_at))
            .order_by(safunc.date(Email.received_at))
        )
        existing_all = {str(r[0]): r[1] for r in result.all()}
        print(f"Emails existentes actualmente: {sum(existing_all.values())}")
        for d, c in sorted(existing_all.items()):
            print(f"  {d}: {c}")

        # ── 3. Generar 30 días de datos simulados ──
        now = datetime.now(timezone.utc)
        today = now.date()
        total_new = 0
        total_ch = 0
        total_contacts = 0

        # Empezamos desde 30 días atrás hasta hoy (inclusive)
        DAYS_TO_SIMULATE = 30

        for day_offset in range(DAYS_TO_SIMULATE):
            target_date = today - timedelta(days=DAYS_TO_SIMULATE - 1 - day_offset)
            date_str = target_date.isoformat()
            dow = target_date.weekday()

            # No sobrescribir datos existentes
            existing_count = existing_all.get(date_str, 0)
            base_count = BASE_EMAILS_BY_DOW.get(dow, 10)
            # Añadir algo de variación aleatoria
            noise_pct = random.uniform(-0.3, 0.3)
            target_count = max(
                0, round(base_count * (1 + noise_pct) * _trend_factor(day_offset, DAYS_TO_SIMULATE))
            )

            if target_count <= 0:
                continue
            if existing_count >= target_count:
                continue

            need = target_count - existing_count
            if need <= 0:
                continue

            print(f"\n{date_str} (dow={dow}): generando {need} emails...")

            # Crear 0-2 contactos nuevos este día (repartidos en los 30 días)
            # Usamos day_offset para determinismo: 1 contacto cada ~2-3 días laborables
            contacts_today = 0
            if dow < 5:  # laborable
                if day_offset % 3 == 0:
                    contacts_today = 1
                if day_offset % 7 == 0:
                    contacts_today = 2
            contact_ids_today: list[str] = []
            base_names = [
                ("Innovatech SL", "info@innovatech.es"),
                ("DataCorp", "contacto@datacorp.com"),
                ("Soluciones Garcia", "soluciones@garcia.es"),
                ("TechWorld", "info@techworld.es"),
                ("Grupo Nexus", "admin@nexusgroup.com"),
                ("Consulting Pro", "info@consultingpro.es"),
                ("InnovaSoft", "ventas@innovasoft.com"),
                ("Business Hub", "contact@businesshub.es"),
                ("ServiTech", "info@servitech.es"),
                ("GlobalSys", "admin@globalsys.com"),
                ("NextGen Labs", "info@nextgenlabs.es"),
                ("QualityFirst", "contact@qualityfirst.com"),
                ("Open Solutions", "info@opensolutions.es"),
                ("Prime Consulting", "admin@primeconsulting.com"),
                ("Atlantic Corp", "info@atlanticcorp.es"),
            ]

            for ci in range(contacts_today):
                cname, cemail = base_names[(day_offset * 2 + ci) % len(base_names)]
                cemail_personalized = f"{cname.lower().replace(' ', '')}+{day_offset}@example.com"
                # Check if already exists in this run
                existing_c = await session.execute(
                    select(Contact).where(Contact.email == cemail_personalized)
                )
                existing_contact = existing_c.scalar_one_or_none()
                if existing_contact is not None:
                    print(f"  SKIP contact: {cemail_personalized} already exists")
                    continue
                print(f"  CREATE contact: {cemail_personalized}")
                contact_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    random.randint(9, 18), random.randint(0, 59), random.randint(0, 59),
                    tzinfo=timezone.utc,
                )
                contact = Contact(
                    id=str(uuid.uuid4()),
                    name=cname,
                    email=cemail_personalized,
                    company=cname,
                    category=random.choice(["cliente", "lead", "proveedor"]),
                    source="email",
                    extra_data={"source": "simulation"},
                    created_at=contact_dt,
                    first_email_at=contact_dt,
                    last_email_at=contact_dt,
                    email_count=random.randint(1, 5),
                )
                session.add(contact)
                contact_ids_today.append(contact.id)
                total_contacts += 1

            for i in range(need):
                hour = random.randint(8, 19)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                received_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, minute, second,
                    tzinfo=timezone.utc,
                )

                category = _pick(CATEGORY_WEIGHTS)
                sender_name, sender_email = random.choice(SENDERS)
                subject_templates = SUBJECTS_BY_CATEGORY.get(category, ["Asunto generico"])
                subject = random.choice(subject_templates)
                if "{}" in subject:
                    subject = subject.format(random.randint(1000, 9999))

                email_id = str(uuid.uuid4())

                email = Email(
                    id=email_id,
                    account_id=account_id,
                    message_id=f"<sim-{email_id}@{sender_email.split('@')[1]}>",
                    subject=subject,
                    body_plain=f"Correo simulado.\nCategoria: {category}\nRemitente: {sender_name}",
                    sender_email=sender_email,
                    sender_name=sender_name,
                    recipients=[{"email": "beexpandcrmpoc@gmail.com", "name": "BeExpand CRM"}],
                    has_attachments=False,
                    attachments=[],
                    received_at=received_dt,
                    processed_at=received_dt + timedelta(seconds=random.randint(30, 300)),
                    category=category,
                    relevance="media" if category != "nulo" else "baja",
                    status="pendiente",
                    summary=f"Simulado: {subject[:50]}",
                    extra_data={
                        "source": "simulation",
                        "analyzer": {
                            "company": sender_name.split()[-1] if len(sender_name.split()) > 1 else "Desconocida",
                            "urgency": "baja",
                            "action_required": None,
                            "entities": [],
                            "resumen": f"Correo simulado categoria {category}",
                        },
                        "routing": {"departments": ["general"]},
                        "resolution_method": "consensus",
                    },
                )
                session.add(email)

                # Vincular a contacto de este día por turno
                if contact_ids_today:
                    contact_idx = i % len(contact_ids_today)
                    contact = await session.get(Contact, contact_ids_today[contact_idx])
                    if contact:
                        contact.last_email_at = received_dt
                        contact.email_count = (contact.email_count or 0) + 1
                        link = EmailContact(
                            email_id=email.id,
                            contact_id=contact.id,
                            role="from",
                        )
                        session.add(link)

                # 3 clasificaciones por email (rule_engine, bert, llm)
                methods = ["rule_engine", "bert", "llm"]
                for method in methods:
                    # Pequeña probabilidad de desacuerdo entre clasificadores
                    if random.random() < 0.08:
                        other_cats = [c for c in CATEGORY_WEIGHTS if c != category]
                        ch_cat = random.choice(other_cats)
                        ch_conf = round(random.uniform(0.30, 0.55), 2)
                    else:
                        ch_cat = category
                        ch_conf = round(random.uniform(0.65, 0.98), 2)

                    ch = ClassificationHistory(
                        id=str(uuid.uuid4()),
                        email_id=email.id,
                        category=ch_cat,
                        confidence=ch_conf,
                        method=method,
                        details={
                            "reason": f"Simulacion: clasificacion via {method}",
                            "scores": {cat: round(random.uniform(0, 5), 1) for cat in CATEGORY_WEIGHTS},
                            "final_category": category,
                            "resolution": "consensus",
                        },
                    )
                    session.add(ch)
                    total_ch += 1

                total_new += 1

                if (i + 1) % 10 == 0:
                    print(f"  ... {i + 1}/{need}")

        print(f"\n{'='*40}")
        print(f"Resumen: {total_new} emails nuevos, {total_ch} clasificaciones, {total_contacts} contactos")

        if total_new > 0:
            await session.commit()
            print("Datos insertados correctamente")
        else:
            print("No se insertaron datos nuevos")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
