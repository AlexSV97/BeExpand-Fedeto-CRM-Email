"""
Check the dashboard API for orchestrator results
"""
import httpx
import os

BASE = "http://localhost:8001/api/v1"

r = httpx.post(f"{BASE}/auth/login", json={
    "username": "admin",
    "password": os.getenv("ADMIN_PASSWORD", "<ADMIN_PASSWORD_DEMO>"),
})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Dashboard summary
r = httpx.get(f"{BASE}/dashboard/summary", headers=headers, timeout=30)
dash = r.json()

print("=== DASHBOARD ===")
print(f"Total emails: {dash.get('total_emails')}")
print(f"Emails hoy:   {dash.get('emails_today')}")
print(f"Contactos:    {dash.get('contacts_by_category')}")
print()

recent = dash.get("recent_emails", [])
print(f"=== ULTIMOS {len(recent)} EMAILS (con datos del Orchestrator) ===")
print()
for i, e in enumerate(recent, 1):
    depts = e.get("departments") or []
    res = e.get("resolution") or ""
    urg = e.get("urgency") or ""
    action = e.get("action_required") or ""
    summary = e.get("summary") or ""
    sender = e.get("sender_name") or ""
    cat = e.get("category") or "?"
    conf = e.get("confidence") or 0
    dept_str = ", ".join(depts) if depts else "N/A"

    print(f"--- #{i}: {e.get('subject', '?')} ---")
    print(f"    Remitente: {sender}")
    print(f"    Categoria: {cat} ({conf*100:.0f}%)")
    print(f"    Urgencia:  {urg}")
    print(f"    Accion:    {action}")
    print(f"    Deptos:    {dept_str}")
    print(f"    Metodo:    {res}")
    if summary:
        print(f"    Resumen:   {summary[:150]}")
    print()
