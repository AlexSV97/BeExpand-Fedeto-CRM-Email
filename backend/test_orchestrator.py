"""
Test script para probar el Orchestrator vía API.
"""
import httpx
import json
import sys

BASE = "http://localhost:8001/api/v1"


def main():
    # 1. Login
    print("1. LOGIN...")
    r = httpx.post(f"{BASE}/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   OK - token obtenido\n")

    # 2. Sync emails (Orchestrator)
    print("2. SINCRONIZANDO CORREOS (Orchestrator)...")
    print("   Esto puede tardar ~30-60s por email (Ollama + BERT)...\n")
    r = httpx.post(
        f"{BASE}/emails/sync",
        headers=headers,
        timeout=300,
    )
    result = r.json()
    print(f"   Status: {r.status_code}")
    print(f"   Conectado IMAP: {result.get('connected')}")
    print(f"   Procesados: {result.get('processed')}")
    print(f"   Errores: {result.get('errors')}")

    if result.get("error"):
        print(f"   ERROR GENERAL: {result['error']}")

    # 3. Mostrar resultados por email
    if result.get("results"):
        print(f"\n   RESULTADOS ({len(result['results'])} emails):")
        print("=" * 70)
        for i, item in enumerate(result["results"], 1):
            print(f"\n   --- Email #{i} ---")
            print(f"   Asunto:    {item.get('subject', '(sin asunto)')}")
            print(f"   Remitente: {item.get('sender_name', '?')} <{item.get('sender_email', '?')}>")
            print(f"   Categoría: {item.get('category', 'N/A')}  (confianza: {item.get('confidence', 0)*100:.0f}%)")
            print(f"   Resolución: {item.get('resolution', 'N/A')}")
            print(f"   Urgencia:  {item.get('urgency', 'N/A')}")
            print(f"   Acción:    {item.get('action_required', 'N/A')}")
            
            routing = item.get("routing", {})
            if routing.get("departments"):
                print(f"   Departamentos: {', '.join(routing['departments'])}")
            if routing.get("persons"):
                print(f"   Personas: {', '.join(routing['persons'])}")
            
            if item.get("summary"):
                print(f"   Resumen:   {item['summary']}")
            
            if item.get("actions"):
                for a in item["actions"]:
                    status = "OK" if a["success"] else "FALLO"
                    print(f"   Acción [{status}]: {a['action']} - {a.get('detail', '')}")
            
            if item.get("error"):
                print(f"   ERROR: {item['error']}")
    else:
        print("\n   No se encontraron correos UNSEEN en la bandeja.")

    # 4. Dashboard summary
    print("\n\n3. DASHBOARD SUMMARY...")
    r = httpx.get(f"{BASE}/dashboard/summary", headers=headers, timeout=30)
    if r.status_code == 200:
        dash = r.json()
        print(f"   Total emails: {dash.get('total_emails', 0)}")
        print(f"   Emails hoy: {dash.get('emails_today', 0)}")
        print(f"   Contactos por categoría: {dash.get('contacts_by_category', {})}")
        if dash.get("recent_emails"):
            print(f"\n   Últimos emails con datos del orquestador:")
            for e in dash["recent_emails"]:
                depts = e.get("departments", [])
                dept_str = f" -> {', '.join(depts)}" if depts else ""
                res = e.get("resolution", "")
                res_str = f" [{res}]" if res else ""
                print(f"     - {e.get('subject', '?')} | {e.get('category', '?')}{res_str}{dept_str}")
    else:
        print(f"   Error: {r.status_code} - {r.text}")

    print("\n✅ PRUEBA COMPLETADA")


if __name__ == "__main__":
    main()
