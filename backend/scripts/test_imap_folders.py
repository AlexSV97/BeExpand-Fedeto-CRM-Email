"""
Test del movimiento a carpetas IMAP.

1. Conecta a Gmail vía IMAP
2. Busca correos NO VISTOS
3. Los procesa con el Orchestrator completo
4. Los mueve a la carpeta correspondiente (si aplica)
5. Muestra resumen detallado

Uso:
    python scripts/test_imap_folders.py [--verbose]

Requiere:
    - Ollama corriendo (http://127.0.0.1:11434)
    - .env con IMAP configurado
    - SQLite (aiuken.db) con las tablas creadas
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def test_sync(verbose: bool = False) -> None:
    from src.email_processor.fetcher import sync_emails

    print("=" * 65)
    print("  TEST: Movimiento a carpetas IMAP por categoría")
    print("=" * 65)

    summary = await sync_emails()

    print()
    print("─" * 65)
    print("  RESULTADO")
    print("─" * 65)

    if summary.get("error"):
        print(f"\n  ❌ Error: {summary['error']}")
        return

    print(f"\n  📧 Conectado:     {'✅' if summary.get('connected') else '❌'}")
    print(f"  📬 Correos encontrados: {summary.get('fetched', 0)}")
    print(f"  ⚙️  Procesados:          {summary.get('processed', 0)}")
    print(f"  📁 Movidos a carpetas:   {summary.get('moved_to_folders', 0)}")
    print(f"  ❌ Errores:              {summary.get('errors', 0)}")

    results = summary.get("results", [])
    if not results:
        print("\n  📭 No había correos nuevos. Envíate uno y vuelve a ejecutar.")
        return

    print(f"\n  {'─' * 55}")
    print(f"  {'ASUNTO':<35} {'CATEGORÍA':<12} {'CONF.'}")
    print(f"  {'─' * 55}")

    for r in results:
        subject = (r.get("subject") or "—")[:34]
        category = r.get("category") or "—"
        conf = f"{r.get('confidence', 0) * 100:.0f}%"
        print(f"  {subject:<35} {category:<12} {conf}")

        if verbose:
            print(f"    └─ Resolución: {r.get('resolution', '—')}")
            votes = r.get("votes", [])
            for v in votes:
                print(f"      · {v.get('agent', '?'):<12} → {v.get('category', '?'):<10} ({v.get('confidence', 0) * 100:.0f}%)")
            depts = r.get("routing", {}).get("departments", [])
            if depts:
                print(f"      · Ruta: {', '.join(depts)}")

    # Comprobar carpetas creadas en Gmail
    print()
    print("─" * 65)
    print("  VERIFICACIÓN EN GMAIL")
    print("─" * 65)
    print("""
  ✅ Los emails de cliente    → carpeta INBOX/Clientes
  ✅ Los emails de lead       → carpeta INBOX/Leads
  ✅ Los emails de proveedor  → carpeta INBOX/Proveedores
  ✅ Los nulos y otros        → se quedan en INBOX

  📌 Abre Gmail y mira en el menú de la izquierda.
     Si no ves las carpetas, haz clic en "Más" para
     mostrar todas las etiquetas.
""")

    if summary.get("moved_to_folders", 0) > 0:
        print("  🎯 Se movieron emails correctamente.")
    elif summary.get("processed", 0) > 0:
        print("  ℹ️  Los emails se procesaron pero no se movieron")
        print("     (probablemente clasificados como 'nulo' o no categorizados).")


def main():
    parser = argparse.ArgumentParser(description="Test movimiento a carpetas IMAP")
    parser.add_argument("--verbose", "-v", action="store_true", help="Muestra votos y detalles")
    args = parser.parse_args()
    asyncio.run(test_sync(verbose=args.verbose))


if __name__ == "__main__":
    main()
