"""
Test completo del clasificador híbrido de 3 niveles.

Prueba escenarios realistas que ejercitan:
  - RuleEngine   (palabras clave → 70%)
  - DistilBERT   (semántica → ≥50%)
  - Ollama/LLM   (último recurso → ≥50%)
  - Fallback     (todo baja confianza → pendiente)

Uso:
    python scripts/test_classifier.py [--inject-db] [--verbose]

  --inject-db   Además prueba, inyecta datos de prueba en la BD
  --verbose     Muestra detalles de cada clasificación
"""

import argparse
import asyncio
import logging
import sys
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

Scenario = dict  # {subject, body, expected_categories, note}

TEST_SCENARIOS: list[Scenario] = [
    # ── RuleEngine: keywords directas ──
    {
        "subject": "Factura de servicios",
        "body": "Adjunto el pago de la factura mensual de internet",
        "expected_categories": ["cliente"],
        "note": "Keyword 'factura'/'pago' → RuleEngine",
    },
    {
        "subject": "Presupuesto anual 2025",
        "body": "Solicito presupuesto para consultoría de marketing digital",
        "expected_categories": ["lead"],
        "note": "Keyword 'presupuesto' → RuleEngine",
    },
    {
        "subject": "Orden de compra proveedores",
        "body": "Necesito materiales del proveedor principal para el proyecto",
        "expected_categories": ["proveedor"],
        "note": "Keyword 'proveedor'/'orden de compra' → RuleEngine",
    },
    {
        "subject": "Soporte técnico - incidencia #1234",
        "body": "Solicito ayuda con un bug en el sistema de facturación",
        "expected_categories": ["cliente"],
        "note": "Keyword 'soporte'/'ayuda' → RuleEngine",
    },
    {
        "subject": "Reunión de seguimiento",
        "body": "Confirmamos la reunión del jueves para revisar avances",
        "expected_categories": ["cliente"],
        "note": "Keyword 'reunión' → RuleEngine",
    },
    # ── BERT: sin keywords, pero semántica clara ──
    {
        "subject": "Consulta sobre planes",
        "body": "Quisiera saber el costo del plan premium para mi empresa",
        "expected_categories": ["lead"],
        "note": "Sin keyword, semántica de consulta comercial → BERT",
    },
    {
        "subject": "Gracias por su compra",
        "body": "Adjunto el recibo de su compra reciente. Esperamos que disfrute el producto.",
        "expected_categories": ["cliente"],
        "note": "Sin keyword, semántica de post-venta → BERT",
    },
    {
        "subject": "Nuevos productos en catálogo",
        "body": "Tenemos disponibles los nuevos modelos con descuento por volumen",
        "expected_categories": ["lead", "proveedor"],
        "note": "Sin keyword, tono comercial → BERT (lead o proveedor)",
    },
    # ── Multilingüe: inglés (DistilBERT multilingual) ──
    {
        "subject": "Invoice for January services",
        "body": "Please find attached the invoice for professional services rendered",
        "expected_categories": ["cliente"],
        "note": "Inglés, keyword 'invoice' → RuleEngine o BERT",
    },
    {
        "subject": "Partnership opportunity",
        "body": "We would like to discuss a potential collaboration with your company",
        "expected_categories": ["lead"],
        "note": "Inglés, sin keyword directa → BERT u Ollama",
    },
    # ── Ollama: BERT inseguro, LLM decide ──
    {
        "subject": "Aviso importante cambio fiscal",
        "body": "Les informamos que hemos cambiado nuestra dirección fiscal. Atentamente, el equipo de administración.",
        "expected_categories": ["proveedor", "pendiente"],
        "note": "Genérico, ni RuleEngine ni BERT seguros → Ollama decide",
    },
    {
        "subject": "Invitación evento networking",
        "body": "Te invitamos al evento anual de networking empresarial en la Cámara de Comercio",
        "expected_categories": ["lead", "cliente"],
        "note": "Evento comercial, puede ser lead o cliente → Ollama decide",
    },
    # ── Fallback: todo baja confianza ──
    {
        "subject": "xyz qwerty",
        "body": "asdf lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore",
        "expected_categories": ["pendiente"],
        "note": "Sin sentido, todo baja confianza → fallback",
    },
]


# ═══════════════════════════════════════════════════════════
#  FUNCIONES DE TEST
# ═══════════════════════════════════════════════════════════

def fmt_conf(conf: float) -> str:
    return f"{conf * 100:3.0f}%"

def fmt_result(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"

def fmt_method(m: str) -> str:
    LABELS = {
        "rule_engine": "[Reglas]  ",
        "bert": "[BERT]    ",
        "ollama": "[Ollama]  ",
        "hybrid_fallback": "[Fallback]",
        "pendiente": "[Pend.]   ",
    }
    return LABELS.get(m, f"  {m:10s}")


async def test_classification(scenario: Scenario) -> dict:
    """Ejecuta hybrid_classify y retorna resultado."""
    from src.email_processor.fetcher import hybrid_classify

    subject = scenario["subject"]
    body = scenario["body"]

    category, confidence, method, reason = await hybrid_classify(subject, body)

    expected = scenario["expected_categories"]
    ok = category in expected

    return {
        "subject": subject,
        "body_preview": body[:60] + ("..." if len(body) > 60 else ""),
        "expected": "/".join(expected),
        "got": category,
        "confidence": confidence,
        "method": method,
        "reason": reason,
        "ok": ok,
    }


async def run_tests(verbose: bool = False) -> list[dict]:
    """Ejecuta todos los escenarios y muestra resultados."""
    HL = "=" * 70
    print(f"\n{HL}")
    print(f"  TEST DEL CLASIFICADOR HIBRIDO - 3 NIVELES")
    print(HL)
    print(f"  {len(TEST_SCENARIOS)} escenarios | Pipeline: Reglas -> BERT -> Ollama -> Fallback\n")

    results = []
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        result = await test_classification(scenario)
        results.append(result)

        icon = fmt_result(result["ok"])
        method_label = fmt_method(result["method"])
        conf_str = fmt_conf(result["confidence"])
        expected = result["expected"]
        got = result["got"]

        print(f"  {icon} [{i:02d}] {method_label} | {got:12s} ({conf_str}) | esperaba: {expected:15s}")
        print(f"         Asunto: {result['subject']}")

        if verbose:
            print(f"         Cuerpo: {result['body_preview']}")
            print(f"         Razón: {result['reason']}")
        print()

    # Resumen
    ok_count = sum(1 for r in results if r["ok"])
    total = len(results)
    print("=" * 70)
    print(f"  RESUMEN: {ok_count}/{total} acertados ({ok_count / total * 100:.0f}%)")
    print()

    # Breakdown por metodo
    by_method: dict[str, list[dict]] = {}
    for r in results:
        by_method.setdefault(r["method"], []).append(r)

    print("  -- Desglose por metodo --")
    for method, items in sorted(by_method.items()):
        method_label = fmt_method(method).strip()
        ok_m = sum(1 for i in items if i["ok"])
        print(f"     {method_label}: {ok_m}/{len(items)} correctos")
    print()

    return results


# ═══════════════════════════════════════════════════════════
#  INYECCIÓN EN BD (opcional)
# ═══════════════════════════════════════════════════════════

async def inject_test_data(results: list[dict], keep_existing: bool = True):
    """Inyecta escenarios de prueba en la BD para verlos en el Dashboard."""
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

        # Crear contactos de prueba
        test_contacts = {
            "cliente": {"name": "María García", "email": "maria.garcia@empresa.com"},
            "lead": {"name": "Carlos López", "email": "carlos.lopez@startup.com"},
            "proveedor": {"name": "Proveedores SA", "email": "info@proveedores.com"},
            "pendiente": {"name": "Remitente desconocido", "email": "contacto@web.com"},
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

        # Inyectar correos de prueba
        injected = 0
        now = datetime.now(timezone.utc)

        for i, (result_data, scenario) in enumerate(zip(results, TEST_SCENARIOS)):
            if not result_data["ok"]:
                continue  # Solo inyectar los acertados

            cat = result_data["got"]
            contact = contacts.get(cat, contacts["pendiente"])

            email = Email(
                id=str(uuid.uuid4()),
                account_id=account.id,
                subject=scenario["subject"],
                body_plain=scenario["body"],
                sender_email=contact.email,
                sender_name=contact.name,
                recipients=["admin@beexpand.com"],
                has_attachments=False,
                received_at=now,
                processed_at=now,
                category=result_data["got"],
                relevance="alta" if result_data["confidence"] >= 0.7 else "media",
                status="pendiente",
            )
            session.add(email)
            await session.flush()

            # ClassificationHistory
            ch = ClassificationHistory(
                id=str(uuid.uuid4()),
                email_id=email.id,
                category=result_data["got"],
                confidence=result_data["confidence"],
                method=result_data["method"],
                details={"reason": result_data["reason"], "test": True},
            )
            session.add(ch)

            # Actualizar contadores del contacto
            contact.email_count = (contact.email_count or 0) + 1
            if contact.first_email_at is None:
                contact.first_email_at = now
            contact.last_email_at = now

            injected += 1

        await session.commit()
        print(f"  📦 Inyectados {injected} correos de prueba en la BD")
        return injected


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Test del clasificador híbrido")
    parser.add_argument("--inject-db", action="store_true", help="Inyectar datos en BD")
    parser.add_argument("--verbose", action="store_true", help="Mostrar detalles")
    parser.add_argument("--keep", action="store_true", help="Conservar datos existentes en BD")
    args = parser.parse_args()

    # 1) Ejecutar tests
    results = await run_tests(verbose=args.verbose)

    # 2) Inyectar en BD si se pide
    if args.inject_db:
        print("=" * 70)
        print("  Inyectando datos de prueba en la BD...")
        injected = await inject_test_data(results, keep_existing=args.keep)
        print()

    # 3) Consejos
    if not args.inject_db:
        print("[TIP] ejecuta con --inject-db para poblar la BD y ver resultados en el Dashboard")
    print()


if __name__ == "__main__":
    asyncio.run(main())
