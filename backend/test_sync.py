"""
Test script: sync with Orchestrator and display results
"""
import httpx
import json
import time
import os

BASE = "http://localhost:8001/api/v1"

# Login
r = httpx.post(f"{BASE}/auth/login", json={
    "username": "admin",
    "password": os.getenv("ADMIN_PASSWORD", "<ADMIN_PASSWORD_DEMO>"),
})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Sync
print("Procesando 5 emails con el Orchestrator...")
print("(Analyzer + 3 clasificadores en paralelo + Resolver + Router + Action Executor)")
print()

start = time.time()
r = httpx.post(f"{BASE}/emails/sync", headers=headers, timeout=300)
elapsed = time.time() - start

result = r.json()
print(f"Tiempo total: {elapsed:.1f}s")
print(f"Conectado: {result.get('connected')}")
print(f"Procesados: {result.get('processed')}")
print(f"Errores: {result.get('errors')}")
print()

if result.get("results"):
    for i, item in enumerate(result["results"], 1):
        print(f"--- Email #{i} ---")
        print(f"  Asunto:    {item.get('subject', '?')}")
        print(f"  Remitente: {item.get('sender_name', '?')}")
        print(f"  Categoria: {item.get('category', '?')} (conf: {item.get('confidence', 0)*100:.0f}%)")
        
        votes = item.get("votes", [])
        vote_strs = [f"{v['agent']}={v['category']}({v['confidence']*100:.0f}%)" for v in votes]
        print(f"  Votos:     {' | '.join(vote_strs)}")
        
        print(f"  Resolucion: {item.get('resolution', '?')}")
        depts = item.get("routing", {}).get("departments", [])
        print(f"  Deptos:    {', '.join(depts) if depts else 'N/A'}")
        print(f"  Accion:    {item.get('action_required', '?')}")
        print(f"  Urgencia:  {item.get('urgency', '?')}")
        
        summary = item.get("summary")
        if summary:
            print(f"  Resumen:   {summary[:120]}")
        
        for a in item.get("actions", []):
            status = "OK" if a["success"] else "FALLO"
            detail = a.get("detail", "")
            print(f"  [{status}] {a['action']}: {detail}")
        
        if item.get("error"):
            print(f"  ERROR: {item['error']}")
        print()
else:
    print("No se procesaron correos.")
    if result.get("error"):
        print(f"Error: {result['error']}")

# Dashboard summary
print("=" * 60)
print("DASHBOARD RESUMEN:")
r = httpx.get(f"{BASE}/dashboard/summary", headers=headers, timeout=30)
if r.status_code == 200:
    dash = r.json()
    print(f"  Total emails: {dash.get('total_emails', 0)}")
    print(f"  Emails hoy: {dash.get('emails_today', 0)}")
    print(f"  Contactos por categoria: {dash.get('contacts_by_category', {})}")
    if dash.get("recent_emails"):
        print(f"\n  Feed ultimos emails con datos del orquestador:")
        for e in dash["recent_emails"]:
            depts = e.get("departments", [])
            dept_str = f" -> {', '.join(depts)}" if depts else ""
            res = e.get("resolution", "")
            res_str = f" [{res}]" if res else ""
            urg = e.get("urgency", "")
            urg_str = f" ({urg})" if urg else ""
            print(f"    - {e.get('subject', '?')} | {e.get('category', '?')}{urg_str}{res_str}{dept_str}")
