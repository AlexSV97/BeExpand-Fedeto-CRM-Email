"""
Test del pipeline de clasificación multi-agente en paralelo.

Ejecuta los 3 clasificadores (RuleEngine + BERT + LLM) en paralelo
sobre escenarios realistas, y muestra cómo el VoteResolver decide
la categoría final por consensus, majority o llm_judge.

Uso:
    python scripts/test_classifier.py [--verbose] [--inject-db]

    --verbose     Muestra detalles de cada voto individual
    --inject-db   Además, inyecta resultados en la BD para verlos en el Dashboard
"""

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Asegurar que podemos importar desde src/ ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  ESCENARIOS DE PRUEBA
# ═══════════════════════════════════════════════════════════

SCENARIOS: list[dict] = [
    # ── Cliente: keywords directas + semántica ──
    {
        "subject": "Factura de servicios septiembre",
        "body": "Adjunto el comprobante de pago de la factura mensual de servicios. Quedo atento al acuse.",
        "expected": ["cliente"],
        "note": "Keyword 'factura'+'pago' -> RuleEngine + BERT + LLM deberían coincidir en cliente",
    },
    {
        "subject": "Soporte técnico - incidencia #1234",
        "body": "Buenos días, desde ayer no podemos acceder al panel de facturación. Necesitamos que lo revisen con urgencia. Gracias.",
        "expected": ["cliente"],
        "note": "Reporte de incidencia de cliente existente",
    },
    {
        "subject": "Reunión de seguimiento proyecto Q3",
        "body": "Hola, tal como acordamos te envío la agenda para la reunión del próximo martes. Adjunto el informe de avance.",
        "expected": ["cliente"],
        "note": "Reunión de seguimiento con cliente -> todos deberían votar cliente",
    },
    # ── Lead: consultas comerciales ──
    {
        "subject": "Solicitud de presupuesto",
        "body": "Nos gustaría recibir información detallada y precios sobre sus servicios de consultoría TI para valorar una posible contratación.",
        "expected": ["lead"],
        "note": "Keyword 'presupuesto' + semántica de consulta comercial -> lead",
    },
    {
        "subject": "Consulta sobre planes empresariales",
        "body": "Estoy interesado en sus servicios pero me gustaría saber si tienen planes para pymes. ¿Podrían llamarme para comentarlo?",
        "expected": ["lead"],
        "note": "Sin keyword directa, semántica de lead -> BERT y LLM deberían capturarlo",
    },
    # ── Proveedor ──
    {
        "subject": "Oferta de materiales de oficina",
        "body": "Les ofrecemos nuestros productos de papelería con descuentos especiales para empresas. Somos proveedores autorizados de las principales marcas.",
        "expected": ["proveedor"],
        "note": "Keyword 'proveedor' + 'ofrecemos' -> proveedor",
    },
    {
        "subject": "Nuevo catálogo de suministros",
        "body": "Estimados, les presentamos nuestro nuevo catálogo de suministros industriales con precios competitivos para el sector.",
        "expected": ["proveedor", "lead"],
        "note": "Sin keyword directa, tono comercial entrante -> proveedor/lead según el agente",
    },
    # ── Nulo: spam / newsletters ──
    {
        "subject": "Newsletter semanal de tecnología",
        "body": "Descubre las últimas novedades en tecnología para tu negocio. Este mes te traemos los mejores consejos para digitalizar tu empresa.",
        "expected": ["nulo"],
        "note": "Newsletter genérica -> nulo",
    },
    {
        "subject": "Invitación a webinar gratuito",
        "body": "Te invitamos a nuestro webinar gratuito sobre transformación digital. Regístrate aquí para asegurar tu plaza.",
        "expected": ["nulo", "lead"],
        "note": "Márketing masivo -> nulo o lead según el agente",
    },
    # ── Inglés ──
    {
        "subject": "Invoice for January professional services",
        "body": "Please find attached the invoice for consulting services rendered in January. Thank you for your prompt payment.",
        "expected": ["cliente"],
        "note": "Inglés, keyword 'invoice' -> cliente, prueba multilingual",
    },
    {
        "subject": "Partnership opportunity with our company",
        "body": "We would like to discuss a potential collaboration with your company. We believe there is great synergy between our organizations.",
        "expected": ["lead", "proveedor"],
        "note": "Inglés, sin keyword directa -> LLM o BERT deciden",
    },
    # ── Casos bordes ──
    {
        "subject": "xyz qwerty",
        "body": "asdf lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore",
        "expected": ["nulo"],
        "note": "Texto sin sentido -> todos deberían votar nulo o muy baja confianza",
    },
]


# ═══════════════════════════════════════════════════════════
#  FUNCIÓN DE TEST
# ═══════════════════════════════════════════════════════════

async def test_scenario(
    scenario: dict,
    rule_agent,
    bert_agent,
    llm_agent,
    resolver,
    verbose: bool,
) -> dict:
    """
    Ejecuta los 3 clasificadores EN PARALELO y luego el VoteResolver.
    No requiere BD — solo los agentes de clasificación.
    """
    from src.orchestrator.context import ClassifierVote, EmailContext, EmailData, ExtractedInfo

    subject = scenario["subject"]
    body = scenario["body"]

    # ── 1. Los 3 clasificadores votan EN PARALELO ──
    votes: list[ClassifierVote] = await asyncio.gather(
        rule_agent.classify(subject, body),
        bert_agent.classify(subject, body),
        llm_agent.classify(subject, body),
    )

    # ── 2. VoteResolver decide ──
    ctx = EmailContext(
        raw=EmailData(
            message_id=None,
            subject=subject,
            body_plain=body,
            body_html=None,
            sender_name="Test Remitente",
            sender_email="test@example.com",
        ),
        extracted=ExtractedInfo(
            urgency="media",
            action_required=None,
            company=None,
            summary=None,
        ),
        votes=votes,
    )

    category, confidence, method = await resolver.resolve(ctx)

    expected = scenario["expected"]
    ok = category in expected

    return {
        "subject": subject,
        "body_preview": body[:60] + ("..." if len(body) > 60 else ""),
        "expected": "/".join(expected),
        "final_category": category,
        "final_confidence": confidence,
        "resolution_method": method,
        "votes": votes,
        "ok": ok,
        "note": scenario["note"],
    }


# ═══════════════════════════════════════════════════════════
#  FORMATEO
# ═══════════════════════════════════════════════════════════

def fmt_conf(conf: float) -> str:
    return f"{conf * 100:3.0f}%"


def fmt_ok(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"


METHOD_LABEL = {
    "consensus": "CONSENSUS",
    "majority":  "MAJORITY",
    "llm_judge": "LLM_JUDGE",
    "fallback":  "FALLBACK",
}


def render_vote(vote) -> str:
    """Renderiza un voto individual en una línea."""
    return (
        f"    [{vote.agent_name:12s}] -> {vote.category:10s} "
        f"({fmt_conf(vote.confidence)})  {vote.reason or ''}"
    )


# ═══════════════════════════════════════════════════════════
#  EJECUTOR
# ═══════════════════════════════════════════════════════════

async def run_tests(verbose: bool = False) -> list[dict]:
    """Crea los agentes, ejecuta todos los escenarios y muestra resultados."""
    from src.agents.classifier.rule_agent import RuleClassifierAgent
    from src.agents.classifier.bert_agent import BertClassifierAgent
    from src.agents.classifier.llm_agent import LLMClassifierAgent
    from src.orchestrator.resolver import VoteResolver

    # Crear agentes
    rule_agent = RuleClassifierAgent()
    bert_agent = BertClassifierAgent()
    llm_agent = LLMClassifierAgent()
    resolver = VoteResolver()

    HL = "=" * 72
    print(f"\n{HL}")
    print(f"  PIPELINE DE CLASIFICACIÓN MULTI-AGENTE EN PARALELO")
    print(f"  {len(SCENARIOS)} escenarios | 3 agentes en paralelo -> VoteResolver\n")

    results = []
    for i, scenario in enumerate(SCENARIOS, 1):
        start = time.time()

        result = await test_scenario(
            scenario, rule_agent, bert_agent, llm_agent, resolver, verbose,
        )

        elapsed = (time.time() - start) * 1000
        results.append(result)

        # Cabecera del escenario
        method_label = METHOD_LABEL.get(result["resolution_method"], result["resolution_method"])
        print(
            f"  {fmt_ok(result['ok'])} [{i:02d}] {method_label} "
            f"-> {result['final_category']:10s} ({fmt_conf(result['final_confidence'])})"
        )
        print(f"         Asunto: {result['subject']}")
        print(f"         Esperado: {result['expected']:15s}  |  {elapsed:5.0f}ms total")
        if verbose:
            print(f"         Nota: {result['note']}")

        # Votos individuales (si verbose o si falló)
        if verbose or not result["ok"]:
            print(f"         Votos:")
            for vote in result["votes"]:
                print(render_vote(vote))

        print()

    # ── Resumen ──
    ok_count = sum(1 for r in results if r["ok"])
    total = len(results)
    print(HL)
    print(f"  ** RESUMEN: {ok_count}/{total} acertados ({ok_count / total * 100:.0f}%)")
    print()

    # Desglose por método de resolución
    print(f"  -- Desglose por método de resolución --")
    by_method: dict[str, list[dict]] = {}
    for r in results:
        by_method.setdefault(r["resolution_method"], []).append(r)

    for method, items in sorted(by_method.items()):
        label = METHOD_LABEL.get(method, method)
        ok_m = sum(1 for i in items if i["ok"])
        print(f"     {label}: {ok_m}/{len(items)} correctos")
    print()

    # Desglose por voto individual
    print(f"  -- Aciertos por agente --")
    agent_results: dict[str, list[bool]] = {}
    for r in results:
        for vote in r["votes"]:
            agent_results.setdefault(vote.agent_name, []).append(vote.category in SCENARIOS[results.index(r)]["expected"])
    for agent, ok_list in sorted(agent_results.items()):
        agent_ok = sum(1 for o in ok_list if o)
        print(f"     {agent:12s}: {agent_ok}/{len(ok_list)} correctos ({agent_ok / len(ok_list) * 100:.0f}%)")
    print()

    return results


# ═══════════════════════════════════════════════════════════
#  INYECCIÓN EN BD (opcional)
# ═══════════════════════════════════════════════════════════

async def inject_test_data(results: list[dict], keep_existing: bool = True):
    """Inyecta los resultados de la clasificación en la BD para verlos en el Dashboard."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.db.models import Account, ClassificationHistory, Contact, Email
    from src.db.session import async_session_factory

    async with async_session_factory() as session:
        # Obtener o crear cuenta
        result = await session.execute(select(Account))
        account = result.scalar_one_or_none()

        if account is None:
            account = Account(
                id=str(uuid.uuid4()),
                name="Test Account",
                email_host="imap.gmail.com",
                email_port=993,
                email_user="test@example.com",
                email_pass="test",
                provider="test",
                active=True,
            )
            session.add(account)
            await session.flush()
            logger.info("Cuenta de test creada")

        # Limpiar datos previos de test si se pide
        if not keep_existing:
            test_emails = await session.execute(
                select(Email).where(Email.account_id == account.id)
            )
            for e in test_emails.scalars():
                await session.delete(e)

        # Crear contactos de prueba por categoría
        test_contacts = {
            "cliente":   {"name": "María García",       "email": "maria.garcia@empresa.com"},
            "lead":      {"name": "Carlos López",       "email": "carlos.lopez@startup.com"},
            "proveedor": {"name": "Proveedores SA",     "email": "info@proveedores.com"},
            "nulo":      {"name": "Remitente desconocido", "email": "contacto@web.com"},
        }

        contacts = {}
        for cat, data in test_contacts.items():
            result = await session.execute(
                select(Contact).where(Contact.email == data["email"])
            )
            contact = result.scalar_one_or_none()
            if contact is None:
                contact = Contact(
                    id=str(uuid.uuid4()),
                    name=data["name"],
                    email=data["email"],
                    category=cat,
                    source="test",
                )
                session.add(contact)
                await session.flush()
            contacts[cat] = contact

        # Inyectar correos con sus clasificaciones
        injected = 0
        now = datetime.now(timezone.utc)

        for scenario, result_data in zip(SCENARIOS, results):
            cat = result_data["final_category"]
            contact = contacts.get(cat, contacts["nulo"])

            email = Email(
                id=str(uuid.uuid4()),
                account_id=account.id,
                subject=scenario["subject"],
                body_plain=scenario["body"],
                sender_email=contact.email,
                sender_name=contact.name,
                recipients=["admin@aiuken.com"],
                has_attachments=False,
                received_at=now,
                processed_at=now,
                category=cat,
                relevance="alta" if result_data["final_confidence"] >= 0.7 else "media",
                status="pendiente",
            )
            session.add(email)
            await session.flush()

            # Guardar cada voto individual como ClassificationHistory
            for vote in result_data["votes"]:
                ch = ClassificationHistory(
                    id=str(uuid.uuid4()),
                    email_id=email.id,
                    category=vote.category,
                    confidence=vote.confidence,
                    method=vote.agent_name,
                    details={
                        "reason": vote.reason,
                        "resolution": result_data["resolution_method"],
                        "final_category": cat,
                    },
                )
                session.add(ch)

            # Actualizar contadores del contacto
            contact.email_count = (contact.email_count or 0) + 1
            if contact.first_email_at is None:
                contact.first_email_at = now
            contact.last_email_at = now

            injected += 1

        await session.commit()
        print(f"  [DB] Inyectados {injected} correos de prueba en la BD")
        return injected


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Test del pipeline multi-agente en paralelo")
    parser.add_argument("--verbose", action="store_true", help="Mostrar detalles de cada voto")
    parser.add_argument("--inject-db", action="store_true", help="Inyectar resultados en la BD")
    parser.add_argument("--keep", action="store_true", help="Conservar datos existentes en BD")
    args = parser.parse_args()

    # 1) Ejecutar tests
    results = await run_tests(verbose=args.verbose)

    # 2) Inyectar en BD si se pide
    if args.inject_db:
        print("=" * 72)
        print("  Inyectando datos de prueba en la BD...")
        injected = await inject_test_data(results, keep_existing=args.keep)
        print()

    # 3) Consejos
    if not args.inject_db:
        print("[TIP] ejecuta con --inject-db para poblar la BD y ver resultados en el Dashboard")
    print()


if __name__ == "__main__":
    asyncio.run(main())
