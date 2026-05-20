"""
Simula ~30 días de actividad de email realista con patrón semanal.

Genera datos de demo para la PoC del viernes: cuerpos de email con
contexto realista, clasificaciones variadas, contactos, oportunidades
y datos de analyzer/routing completos.

Uso:
    cd backend
    python scripts/simulate_data.py
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func as safunc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

DATABASE_URL = "sqlite+aiosqlite:///beexpand.db"

from src.db.models import Account, ClassificationHistory, Contact, Email, EmailContact, Opportunity

# ── Config ──

random.seed(42)

CATEGORY_WEIGHTS = {
    "cliente": 0.25,
    "lead": 0.30,
    "proveedor": 0.25,
    "nulo": 0.15,
    "sin_categoria": 0.05,
}

BASE_EMAILS_BY_DOW = {
    0: 18,   # lunes
    1: 15,   # martes
    2: 17,   # miércoles
    3: 14,   # jueves
    4: 12,   # viernes
    5: 2,    # sábado
    6: 3,    # domingo
}

# ── 20+ Remitentes realistas ──
SENDERS = [
    # Clientes
    ("María García", "maria.garcia@innovatech.es", "Innovatech SL"),
    ("Miguel Ángel Ruiz", "miguel.ruiz@datacorp.com", "DataCorp"),
    ("Ana Martínez López", "ana.martinez@solucionesgarcia.es", "Soluciones García"),
    ("Javier Fernández", "javier.fernandez@techworld.es", "TechWorld SL"),
    ("Laura Sánchez Pérez", "laura.sanchez@nexusgroup.com", "Grupo Nexus"),
    ("Pedro Jiménez", "pedro.jimenez@consultingpro.es", "Consulting Pro"),
    ("Sofía Torres", "sofia.torres@innovasoft.com", "InnovaSoft"),
    ("Carlos López", "carlos.lopez@businesshub.es", "Business Hub"),
    # Leads
    ("David Romero", "david.romero@startupidea.es", "Startup Idea"),
    ("Elena Díaz", "elena.diaz@digitalizate.es", "Digitalízate"),
    ("Roberto Martín", "roberto.martin@nextgenlabs.com", "NextGen Labs"),
    ("Isabel Gómez", "isabel.gomez@qualityfirst.com", "QualityFirst"),
    ("Álvaro Hernández", "alvaro.hernandez@opensolutions.es", "Open Solutions"),
    ("Patricia Ortiz", "patricia.ortiz@primeconsulting.com", "Prime Consulting"),
    ("Daniel Navarro", "daniel.navarro@atlanticcorp.es", "Atlantic Corp"),
    ("Carmen Ruiz", "carmen.ruiz@greenfield.es", "GreenField Tech"),
    # Proveedores
    ("José Manuel Vera", "jm.vera@suministrosvera.com", "Suministros Vera"),
    ("Rosa Romero", "rosa.romero@cloudservices.es", "Cloud Services"),
    ("Antonio Morales", "antonio.morales@infrasolutions.com", "InfraSolutions"),
    ("Marta Castillo", "marta.castillo@oficinatotal.es", "OficinaTotal"),
    ("Francisco Torres", "francisco.torres@cyberseguro.com", "CyberSeguro"),
    ("Luisa Fernández", "luisa.fernandez@telecomexpress.es", "Telecom Express"),
    # Spam/Newsletter
    ("Newsletter Tech", "newsletter@techweek.es", "TechWeek"),
    ("Ofertas Marketing", "info@ofertasmarketing.com", "Marketing Pro"),
    ("Notificaciones Azure", "azure-noreply@microsoft.com", "Microsoft Azure"),
]

# ── Cuerpos de email realistas por categoría ──

CLIENTE_BODIES = [
    "Buenos días, os escribo porque desde ayer estamos teniendo problemas con el acceso a la plataforma. Nos da error 500 al intentar iniciar sesión y no podemos trabajar. Necesitamos una solución urgente por favor. Gracias.",
    "Hola, tal como hablamos por teléfono os envío los detalles de la incidencia. El módulo de facturación no está generando los PDF correctamente, aparecen datos cortados. Adjunto capturas. Quedamos a la espera de vuestra respuesta.",
    "Buenas, queremos solicitar una ampliación del servicio de hosting contratado. Necesitamos pasar del plan básico al profesional porque estamos creciendo en tráfico. Decidnos qué necesitáis para hacer el cambio y precios actualizados.",
    "Estimados, os adjunto la documentación firmada para la renovación del contrato anual de mantenimiento. Tal como acordamos, las condiciones son las mismas del año anterior. Quedamos a la espera de la confirmación.",
    "Hola equipo, tal como acordamos en la última reunión os envío la agenda para el seguimiento del proyecto Q2. Necesitamos revisar los hitos alcanzados y reajustar los plazos pendientes. Confirmad asistencia por favor.",
    "Buenos días, solicitamos una reunión urgente con el departamento técnico para tratar la migración de nuestros datos al nuevo servidor. Llevamos dos semanas con retraso y necesitamos fechas concretas. Gracias.",
    "Hola, adjunto el informe de uso de la plataforma del último trimestre. Hemos duplicado el número de usuarios y necesitamos saber si nuestro plan actual lo soporta. Valorad si necesitamos escalar el servicio.",
    "Estimados, estamos teniendo problemas con los tiempos de carga del panel de administración. Desde la actualización de la semana pasada, tarda más de 30 segundos en cargar. En tickets anteriores ya reportamos esto.",
    "Buenas, necesitamos dar de alta a 5 nuevos usuarios en el sistema. Son del departamento de ventas que se han incorporado esta semana. Os enviamos la lista con nombres y correos. Gracias.",
    "Hola, el pago de la factura de este mes se ha realizado pero en el sistema aún aparece como pendiente. Podéis revisarlo? Número de factura: F-2026-{}. Gracias.",
]

LEAD_BODIES = [
    "Buenos días, estamos interesados en sus servicios de consultoría tecnológica para nuestra empresa. Somos una pyme del sector logístico y queremos digitalizar nuestros procesos. Podríais enviarnos información detallada y precios? Gracias.",
    "Hola, me gustaría recibir una demo de su plataforma de gestión empresarial. Hemos visto vuestra web y encaja con lo que buscamos. Preferiblemente esta semana si es posible. Un saludo.",
    "Estimados, os escribo para solicitar un presupuesto para la implantación de un CRM en nuestra empresa. Somos 25 usuarios y queremos algo personalizable. Agradecería que me llamaran para comentar los detalles.",
    "Buenas, estamos valorando diferentes proveedores de servicios cloud y queremos saber si ofrecéis planes para empresas en crecimiento. Necesitamos unos 500GB de almacenamiento con backups automáticos.",
    "Hola, soy el responsable de IT de una empresa de 50 empleados y estamos buscando un proveedor de ciberseguridad. Ofrecéis servicios de auditoría y protección? Agradecería información y tarifas.",
    "Estimados, me gustaría recibir información sobre sus soluciones de inteligencia artificial para negocio. Hemos oído hablar de su trabajo y nos gustaría explorar posibles colaboraciones. Un saludo.",
    "Buenos días, solicitamos información sobre sus servicios de desarrollo web. Necesitamos rediseñar nuestra tienda online y queremos un equipo con experiencia en ecommerce. Presupuesto aproximado para proyecto completo?",
    "Hola, estamos explorando opciones para externalizar nuestro soporte técnico. Ofrecéis ese servicio? Somos una empresa de 120 empleados y recibimos unas 200 solicitudes al mes. Gracias.",
    "Estimados, me interesa su programa de partners. Podríais enviarme información sobre los requisitos y beneficios del canal de colaboración? Trabajamos con empresas similares en el sector.",
    "Buenas, os escribo porque hemos visto que ofrecéis formación empresarial. Necesitamos un programa de capacitación digital para nuestro equipo de 15 personas. Presupuesto y disponibilidad por favor.",
]

PROVEEDOR_BODIES = [
    "Estimados, les informamos de la actualización de precios para el próximo trimestre. Debido al incremento de costes de materias primas, los precios de nuestros suministros aumentarán un 4% a partir del 1 de junio. Adjuntamos nuevo tarifario.",
    "Buenos días, confirmamos el envío del pedido nº {} solicitado esta semana. El transportista recogerá mañana viernes y la entrega está prevista para el lunes. Adjuntamos albarán y factura proforma.",
    "Hola, les presentamos nuestro nuevo catálogo de productos para este año. Hemos ampliado la gama con nuevas soluciones de software y hardware a precios competitivos. Estaremos encantados de resolver cualquier duda.",
    "Estimados, les informamos del mantenimiento programado de nuestros servidores para el próximo sábado de 22:00 a 02:00. Durante ese periodo el acceso a la plataforma puede verse afectado. Disculpen las molestias.",
    "Buenas, les adjuntamos la factura mensual correspondiente a los servicios prestados en abril. El importe total asciende a {}€ IVA incluido. El pago es mediante transferencia a 30 días fecha factura.",
    "Hola, queremos ofrecerles un descuento especial por fidelidad del 15% en todos nuestros productos durante el mes de mayo. Creemos que puede ser de interés para los proyectos que tienen entre manos.",
    "Estimados, les informamos de que hemos lanzado una nueva línea de servicios cloud con almacenamiento ilimitado. Como cliente preferente, tiene un 20% de descuento si contrata antes del 30 de junio.",
    "Buenos días, confirmamos la recepción de su pedido y informamos que el plazo de entrega será de 48-72 horas. Adjuntamos el resumen del pedido con los detalles acordados. Quedamos a su disposición.",
    "Hola, les escribimos para recordarles que la garantía de los equipos adquiridos expira el próximo mes. Ofrecemos un plan de extensión de garantía por 2 años adicionales con condiciones ventajosas. Adjuntamos info.",
    "Estimados, debido a problemas logísticos con nuestro proveedor de transporte, los pedidos de esta semana sufrirán un retraso de 2-3 días. Lamentamos las molestias y trabajamos para minimizar el impacto.",
]

NULO_BODIES = [
    "GANA UN IPHONE 16 GRATIS! Solo tienes que responder a este correo con tus datos y participarás en el sorteo del nuevo iPhone. No dejes pasar esta oportunidad única! Promoción válida hasta fin de mes.",
    "Newsletter semanal de tecnología: esta semana te traemos los 10 mejores consejos para proteger tu negocio digital, las últimas tendencias en IA y el análisis del nuevo reglamento de protección de datos.",
    "Has sido seleccionado para recibir una oferta exclusiva! Por tiempo limitado, accede a descuentos de hasta el 70% en formación online para tu empresa. Más de 500 cursos disponibles. No esperes más!",
    "Invitación a webinar gratuito: Cómo aumentar las ventas de tu negocio con marketing digital. Fecha: 25 de mayo a las 18:00. Ponente invitado: Juan Carlos Rodríguez, experto en growth marketing.",
    "Tu factura mensual de Microsoft Azure ya está disponible. Período de facturación: abril 2026. Importe: {}€. Puedes consultar el detalle en el portal de facturación de Azure.",
    "No te pierdas nuestra oferta especial! Por compras superiores a 100€ llévate un regalo sorpresa. Esta semana solo: gastos de envío gratuitos en toda la tienda online.",
    "Confirmación de registro: gracias por suscribirte a nuestra newsletter. A partir de ahora recibirás nuestras comunicaciones semanales con las últimas novedades del sector. Puedes darte de baja en cualquier momento.",
    "Alerta de seguridad: detectamos un intento de inicio de sesión en tu cuenta desde un dispositivo no reconocido. Si no fuiste tú, cambia tu contraseña inmediatamente. Atentamente, equipo de seguridad.",
    "Transforma tu negocio con nuestra solución todo en uno. Más de 10000 empresas ya confían en nosotros. Solicita tu demo gratuita ahora y descubre cómo podemos ayudarte a crecer.",
    "Resumen semanal de tu actividad en la plataforma: has recibido 15 visitas a tu perfil, 3 nuevos contactos y 2 mensajes. Inicia sesión para ver los detalles completos.",
]

SIN_CATEGORIA_BODIES = [
    "Buenos días, os reenvío la documentación pendiente del proyecto que comentamos la semana pasada. Por favor confirmad recepción. Un saludo.",
    "Hola, os adjunto la nota informativa sobre el cambio de normativa que afecta a nuestros procesos. Revisadla y comentamos en la próxima reunión.",
    "Comunicado interno: recordamos que el próximo viernes es festivo local, por lo que la oficina permanecerá cerrada. Planificad vuestras tareas en consecuencia.",
    "Buenas, os paso el informe de actividad del mes para vuestro conocimiento. Cualquier duda me comentáis.",
]

SUBJECTS_BY_CATEGORY = {
    "cliente": [
        "Incidencia en plataforma - acceso bloqueado",
        "Solicitud de ampliación de servicio contratado",
        "Renovación del contrato anual de mantenimiento",
        "Seguimiento proyecto Q2 - revisión de hitos",
        "Solicitud de reunión técnica urgente",
        "Informe trimestral de uso de plataforma",
        "Problemas de rendimiento post-actualización",
        "Alta de nuevos usuarios en el sistema",
        "Consulta sobre facturación del servicio",
        "Petición de migración de servidor",
    ],
    "lead": [
        "Solicitud de información servicios consultoría",
        "Demo de plataforma de gestión empresarial",
        "Presupuesto para implantación CRM",
        "Consulta sobre planes cloud empresariales",
        "Interés en servicios de ciberseguridad",
        "Información sobre soluciones IA para negocio",
        "Rediseño de tienda online - solicitud presupuesto",
        "Consulta externalización soporte técnico",
        "Interés en programa de partners",
        "Solicitud de formación digital para equipo",
    ],
    "proveedor": [
        "Actualización de precios Q3 2026",
        "Confirmación de envío pedido #{}",
        "Nuevo catálogo de productos 2026",
        "Aviso de mantenimiento programado",
        "Factura mensual de servicios abril",
        "Oferta especial descuento fidelidad",
        "Nueva línea de servicios cloud premium",
        "Confirmación y plazo de entrega pedido",
        "Extensión de garantía equipos",
        "Retraso logístico en pedidos semanales",
    ],
    "nulo": [
        "Gana un iPhone 16 GRATIS!",
        "Newsletter semanal de tecnología",
        "Oferta exclusiva formación online 70% dto",
        "Invitación webinar marketing digital",
        "Tu factura Azure {}€ está disponible",
        "Oferta especial - gastos de envío gratis",
        "Confirmación de suscripción newsletter",
        "Alerta de seguridad: nuevo inicio sesión",
        "Transforma tu negocio - solicita demo",
        "Resumen semanal de actividad",
    ],
    "sin_categoria": [
        "Re: Documentación pendiente",
        "Nota informativa cambio normativa",
        "Comunicado interno festivo local",
        "Informe de actividad mensual",
    ],
}


def _pick(distribution: dict[str, float]) -> str:
    """Elige una categoría según su peso."""
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


def _make_body(category: str, idx: int) -> tuple[str, dict]:
    """Genera un cuerpo de email realista y sus metadatos de analyzer."""
    bodies: dict[str, list[str]] = {
        "cliente": CLIENTE_BODIES,
        "lead": LEAD_BODIES,
        "proveedor": PROVEEDOR_BODIES,
        "nulo": NULO_BODIES,
        "sin_categoria": SIN_CATEGORIA_BODIES,
    }
    chosen = bodies.get(category, SIN_CATEGORIA_BODIES)
    body = chosen[idx % len(chosen)]
    body = body.replace("{}", str(random.randint(1000, 9999)))

    # Datos de analyzer según categoría
    analyzer = {
        "company": "",
        "urgency": "baja",
        "action_required": False,
        "entities": [],
        "resumen": body[:120] + "...",
    }

    if category == "cliente":
        empresas = ["Innovatech", "DataCorp", "TechWorld", "Grupo Nexus", "Consulting Pro"]
        analyzer["company"] = random.choice(empresas)
        analyzer["urgency"] = random.choices(
            ["alta", "media", "baja"], weights=[0.35, 0.45, 0.20]
        )[0]
        analyzer["action_required"] = True
        analyzer["entities"] = random.sample(
            ["incidencia", "facturación", "soporte", "migración", "contrato", "usuarios"],
            k=random.randint(1, 3),
        )
    elif category == "lead":
        empresas = ["Startup Idea", "Digitalízate", "NextGen Labs", "QualityFirst", "GreenField Tech"]
        analyzer["company"] = random.choice(empresas)
        analyzer["urgency"] = random.choices(
            ["alta", "media", "baja"], weights=[0.15, 0.50, 0.35]
        )[0]
        analyzer["action_required"] = True
        analyzer["entities"] = random.sample(
            ["presupuesto", "demo", "crm", "cloud", "ciberseguridad", "formación"],
            k=random.randint(1, 3),
        )
    elif category == "proveedor":
        empresas = ["Suministros Vera", "Cloud Services", "InfraSolutions", "CyberSeguro", "Telecom Express"]
        analyzer["company"] = random.choice(empresas)
        analyzer["urgency"] = random.choices(
            ["alta", "media", "baja"], weights=[0.10, 0.35, 0.55]
        )[0]
        analyzer["action_required"] = False
        analyzer["entities"] = random.sample(
            ["pedido", "factura", "catálogo", "mantenimiento", "precios", "garantía"],
            k=random.randint(1, 2),
        )
    elif category == "nulo":
        analyzer["company"] = ""
        analyzer["urgency"] = "baja"
        analyzer["action_required"] = False
        analyzer["entities"] = []

    return body, analyzer


def _get_departments(category: str) -> list[str]:
    """Departamento destino según categoría."""
    if category == "cliente":
        return random.sample(
            ["soporte", "comercial", "direccion"],
            k=random.randint(1, 2),
        )
    elif category == "lead":
        return ["comercial"]
    elif category == "proveedor":
        return random.sample(
            ["compras", "administracion", "direccion"],
            k=random.randint(1, 2),
        )
    return []


async def main():
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
        print("\n--- Limpiando simulaciones previas...")
        all_emails = (
            (await session.execute(
                select(Email).options(selectinload(Email.classification_history))
            ))
            .scalars()
            .all()
        )
        sim_email_ids = [
            e.id for e in all_emails
            if e.extra_data and isinstance(e.extra_data, dict)
            and e.extra_data.get("source") == "simulation"
        ]
        if sim_email_ids:
            for eid in sim_email_ids:
                email = next((e for e in all_emails if e.id == eid), None)
                if email:
                    for ch in email.classification_history:
                        await session.delete(ch)
                    await session.delete(email)
            await session.commit()
            print(f"  [OK] Eliminados {len(sim_email_ids)} emails simulados")
        else:
            print("  [i]  No hay simulaciones previas")

        # Limpiar contactos de simulación
        all_contacts = (await session.execute(select(Contact))).scalars().all()
        sim_contacts = [
            c for c in all_contacts
            if c.extra_data and isinstance(c.extra_data, dict)
            and c.extra_data.get("source") == "simulation"
        ]
        for c in sim_contacts:
            await session.delete(c)
        if sim_contacts:
            await session.commit()
            print(f"  [OK] Eliminados {len(sim_contacts)} contactos simulados")

        # Limpiar oportunidades de simulación
        all_opps = (
            await session.execute(
                select(Opportunity).options(selectinload(Opportunity.contact))
            )
        ).scalars().all()
        sim_opps = [
            o for o in all_opps
            if o.description and "[SIMULACIÓN]" in o.description
        ]
        for o in sim_opps:
            await session.delete(o)
        if sim_opps:
            await session.commit()
            print(f"  [OK] Eliminados {len(sim_opps)} oportunidades simuladas")

        # ── 2. Contar emails existentes ──
        result = await session.execute(
            select(safunc.date(Email.received_at), safunc.count(Email.id))
            .group_by(safunc.date(Email.received_at))
            .order_by(safunc.date(Email.received_at))
        )
        existing_all = {str(r[0]): r[1] for r in result.all()}
        total_existing = sum(existing_all.values())
        print(f"\n[data] Emails existentes (no simulación): {total_existing}")
        for d, c in sorted(existing_all.items()):
            print(f"  {d}: {c}")
        print()

        # ── 3. Generar 30 días de datos ──
        now = datetime.now(timezone.utc)
        today = now.date()
        DAYS_TO_SIMULATE = 30

        total_new = 0
        total_ch = 0
        total_contacts = 0
        total_opps = 0
        simulation_contact_ids: list[str] = []
        daily_contact_map: dict[str, list[str]] = {}

        # Base names para contactos de empresa
        contact_sources = [
            ("Innovatech SL", "info@innovatech.es"),
            ("DataCorp International", "contacto@datacorp.com"),
            ("Soluciones García SL", "soluciones@garcia.es"),
            ("TechWorld Solutions", "info@techworld.es"),
            ("Grupo Nexus AI", "admin@nexusgroup.com"),
            ("Consulting Pro España", "info@consultingpro.es"),
            ("InnovaSoft Technologies", "ventas@innovasoft.com"),
            ("Business Hub Spain", "contact@businesshub.es"),
            ("ServiTech Solutions", "info@servitech.es"),
            ("GlobalSys Corporation", "admin@globalsys.com"),
            ("NextGen Labs Spain", "info@nextgenlabs.es"),
            ("QualityFirst Group", "contact@qualityfirst.com"),
            ("Open Solutions Tech", "info@opensolutions.es"),
            ("Prime Consulting SL", "admin@primeconsulting.com"),
            ("Atlantic Corp España", "info@atlanticcorp.es"),
            ("Digitalízate Business", "hola@digitalizate.es"),
            ("GreenField Tech SL", "info@greenfieldtech.es"),
            ("Cloud Services Spain", "ventas@cloudservices.es"),
        ]

        for day_offset in range(DAYS_TO_SIMULATE):
            target_date = today - timedelta(days=DAYS_TO_SIMULATE - 1 - day_offset)
            date_str = target_date.isoformat()
            dow = target_date.weekday()

            existing_count = existing_all.get(date_str, 0)
            base_count = BASE_EMAILS_BY_DOW.get(dow, 10)
            noise_pct = random.uniform(-0.3, 0.3)
            target_count = max(
                0,
                round(base_count * (1 + noise_pct) * _trend_factor(day_offset, DAYS_TO_SIMULATE)),
            )
            if target_count <= 0:
                continue
            if existing_count >= target_count:
                continue
            need = target_count - existing_count
            if need <= 0:
                continue

            print(f"[date] {date_str} (día {day_offset+1}/{DAYS_TO_SIMULATE}, dow={dow}): {need} emails...")

            # Crear 0-2 contactos empresariales nuevos este día
            contacts_today: list[str] = []
            if dow < 5:
                n_contacts = 0
                if day_offset % 3 == 0:
                    n_contacts = 1
                if day_offset % 7 == 0:
                    n_contacts = 2

                for ci in range(n_contacts):
                    cname, cemail_base = contact_sources[(day_offset * 2 + ci) % len(contact_sources)]
                    cemail = f"{cname.lower().replace(' ', '').replace('sl', '').replace('spain', '').replace('españa', '')}+{day_offset}@example.com"
                    cemail = cemail.replace("++", "+")

                    existing_c = await session.execute(
                        select(Contact).where(Contact.email == cemail)
                    )
                    if existing_c.scalar_one_or_none():
                        continue

                    contact_dt = datetime(
                        target_date.year, target_date.month, target_date.day,
                        random.randint(9, 18), random.randint(0, 59), random.randint(0, 59),
                        tzinfo=timezone.utc,
                    )
                    cat = random.choice(["cliente", "lead", "proveedor"])
                    contact = Contact(
                        id=str(uuid.uuid4()),
                        name=cname,
                        email=cemail,
                        company=cname,
                        category=cat,
                        source="email",
                        extra_data={"source": "simulation"},
                        created_at=contact_dt,
                        first_email_at=contact_dt,
                        last_email_at=contact_dt,
                        email_count=random.randint(1, 5),
                    )
                    session.add(contact)
                    contacts_today.append(contact.id)
                    total_contacts += 1
                    print(f"  [contact] Nuevo contacto: {cname} ({cat})")

            daily_contact_map[date_str] = contacts_today
            simulation_contact_ids.extend(contacts_today)

            # Generar los emails de este día
            for i in range(need):
                hour = random.randint(8, 20)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                received_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, minute, second,
                    tzinfo=timezone.utc,
                )

                category = _pick(CATEGORY_WEIGHTS)

                # Seleccionar remitente según categoría
                if category == "nulo":
                    sender_idx = random.choice([-5, -4, -3, -2, -1])
                elif category == "proveedor":
                    sender_idx = random.choice([-6, -7, -8, -9, -10])
                elif category == "cliente":
                    sender_idx = random.choice([0, 1, 2, 3, 4, 5, 6])
                elif category == "lead":
                    sender_idx = random.choice([7, 8, 9, 10, 11, 12, 13, 14, 15])
                else:
                    sender_idx = random.randint(0, len(SENDERS) - 1)

                sender_name, sender_email, sender_company = SENDERS[sender_idx]

                subject_templates = SUBJECTS_BY_CATEGORY.get(category, ["Asunto genérico"])
                subject = random.choice(subject_templates)
                if "{}" in subject:
                    subject = subject.replace("{}", str(random.randint(1000, 9999)), 1)

                body, analyzer = _make_body(category, i)
                departments = _get_departments(category)

                email_id = str(uuid.uuid4())
                domain = sender_email.split("@")[1] if "@" in sender_email else "example.com"

                email = Email(
                    id=email_id,
                    account_id=account_id,
                    message_id=f"<sim-{email_id}@{domain}>",
                    subject=subject,
                    body_plain=body,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    recipients=[{"email": "beexpandcrmpoc@gmail.com", "name": "BeExpand CRM"}],
                    has_attachments=category in ("cliente", "proveedor") and random.random() < 0.3,
                    attachments=[],
                    received_at=received_dt,
                    processed_at=received_dt + timedelta(seconds=random.randint(30, 300)),
                    category=category if category != "sin_categoria" else None,
                    relevance=(
                        "alta" if category == "cliente" and analyzer.get("urgency") == "alta"
                        else "media" if category in ("cliente", "lead")
                        else "baja" if category == "nulo"
                        else "media"
                    ),
                    status="pendiente",
                    summary=analyzer.get("resumen", subject)[:200],
                    extra_data={
                        "source": "simulation",
                        "analyzer": analyzer,
                        "routing": {"departments": departments},
                        "resolution_method": random.choice(
                            ["consensus", "consensus", "consensus", "majority"]
                        ),
                    },
                )
                session.add(email)

                # Vincular a contactos empresariales
                if contacts_today:
                    contact_idx = i % len(contacts_today)
                    contact = await session.get(Contact, contacts_today[contact_idx])
                    if contact:
                        contact.last_email_at = received_dt
                        contact.email_count = (contact.email_count or 0) + 1
                        session.add(
                            EmailContact(email_id=email.id, contact_id=contact.id, role="from")
                        )

                # 3 clasificaciones por email con desacuerdos realistas
                methods = ["rule_engine", "bert", "llm"]
                for method in methods:
                    if category == "sin_categoria":
                        # Para emails sin categoría clara: desacuerdo entre clasificadores
                        ch_cat = random.choice(["cliente", "lead", "proveedor", "nulo"])
                        ch_conf = round(random.uniform(0.30, 0.55), 2)
                    elif random.random() < 0.10:
                        # 10% de los casos: un clasificador disiente
                        other_cats = [c for c in ("cliente", "lead", "proveedor", "nulo") if c != category]
                        ch_cat = random.choice(other_cats)
                        ch_conf = round(random.uniform(0.30, 0.50), 2)
                    else:
                        ch_cat = category
                        ch_conf = round(random.uniform(0.65, 0.98), 2)

                    # Detalles de clasificación realistas
                    reason = {
                        "rule_engine": f"keywords detectados: {', '.join(random.sample(['factura','presupuesto','contrato','soporte','pedido','demo','newsletter','oferta'], k=random.randint(1,3)))}",
                        "bert": f"análisis semántico: {random.uniform(0.5, 0.95):.0%} similitud con categoría {ch_cat}",
                        "llm": f"análisis contextual: {random.choice(['tono formal y solicitud comercial', 'urgencia en solicitud de soporte', 'comunicación proveedor estándar', 'newsletter sin relevancia', 'interés en contratar servicios'])}",
                    }.get(method, f"votación {method}")

                    ch = ClassificationHistory(
                        id=str(uuid.uuid4()),
                        email_id=email.id,
                        category=ch_cat,
                        confidence=ch_conf,
                        method=method,
                        details={
                            "reason": reason,
                            "scores": {
                                cat: round(random.uniform(0, 5), 1)
                                for cat in ("cliente", "lead", "proveedor", "nulo")
                            },
                            "final_category": category,
                            "resolution": "consensus",
                            "analyzer_company": analyzer.get("company", ""),
                        },
                    )
                    session.add(ch)
                    total_ch += 1

                total_new += 1

            if need > 0:
                print(f"  [OK] {need} emails generados")

        # ── 4. Crear oportunidades de ejemplo ──
        print(f"\n[case] Creando oportunidades de negocio...")
        if simulation_contact_ids:
            # Seleccionar algunos contactos para crear oportunidades
            opp_contacts = simulation_contact_ids[:15]  # hasta 15 contactos
            stages = ["calificacion", "propuesta", "negociacion", "cerrada_ganada", "cerrada_perdida"]
            for idx, cid in enumerate(opp_contacts):
                contact = await session.get(Contact, cid)
                if not contact:
                    continue
                stage = stages[idx % len(stages)]
                opp_value = random.choice([5000.00, 12000.00, 25000.00, 45000.00, 80000.00, 150000.00])
                opp = Opportunity(
                    id=str(uuid.uuid4()),
                    contact_id=contact.id,
                    title=f"Oportunidad: {contact.name}",
                    description=f"[SIMULACIÓN] Oportunidad generada con {contact.name} para servicios de consultoría y desarrollo.",
                    stage=stage,
                    value=opp_value,
                    probability=random.choice([20, 30, 50, 70, 90]),
                    expected_close=(
                        datetime.now(timezone.utc) + timedelta(days=random.randint(15, 90))
                    ).date(),
                    created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 20)),
                )
                session.add(opp)
                total_opps += 1
            print(f"  [OK] {total_opps} oportunidades creadas")

        # ── 5. Commit final ──
        print(f"\n{'='*50}")
        print(f"[data] RESUMEN FINAL")
        print(f"{'='*50}")
        print(f"  Emails generados:     {total_new}")
        print(f"  Clasificaciones:      {total_ch}")
        print(f"  Contactos nuevos:     {total_contacts}")
        print(f"  Oportunidades:        {total_opps}")

        if total_new > 0:
            await session.commit()
            print(f"\n[OK] Datos insertados correctamente en la base de datos")
        else:
            print(f"\n[i]  No se insertaron datos nuevos")

        # Mostrar stats finales
        result = await session.execute(
            select(safunc.count(Email.id))
        )
        total_emails_db = result.scalar()
        result = await session.execute(
            select(safunc.count(Contact.id))
        )
        total_contacts_db = result.scalar()
        result = await session.execute(
            select(safunc.count(Opportunity.id))
        )
        total_opps_db = result.scalar()
        print(f"\n[growth] Estado actual de la BD:")
        print(f"  Total emails:          {total_emails_db}")
        print(f"  Total contactos:       {total_contacts_db}")
        print(f"  Total oportunidades:   {total_opps_db}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
