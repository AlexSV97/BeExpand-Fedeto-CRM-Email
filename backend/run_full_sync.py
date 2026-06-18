"""
Full test sync with Orchestrator
"""
import httpx, time, sys, os

BASE = "http://localhost:8001/api/v1"

# Login
r = httpx.post(f"{BASE}/auth/login", json={
    "username": "admin",
    "password": os.getenv("ADMIN_PASSWORD", "<ADMIN_PASSWORD_DEMO>"),
})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("Syncing with Orchestrator... (timeout: 10 min)")
print()
sys.stdout.flush()

start = time.time()
r = httpx.post(f"{BASE}/emails/sync", headers=headers, timeout=600)
elapsed = time.time() - start

result = r.json()
print(f"Time: {elapsed:.1f}s")
print(f"Connected: {result.get('connected')}")
print(f"Fetched: {result.get('fetched')}")
print(f"Processed: {result.get('processed')}")
print(f"Errors: {result.get('errors')}")
print()
sys.stdout.flush()

if result.get("results"):
    for i, item in enumerate(result["results"], 1):
        cat = item.get("category", "?")
        conf = item.get("confidence", 0) or 0
        subj = item.get("subject", "?")[:60]
        sender = item.get("sender_name", "?")
        res = item.get("resolution", "?")
        depts = item.get("routing", {}).get("departments", [])
        dept_str = ", ".join(depts) if depts else "N/A"
        actions = item.get("actions", [])
        action_strs = []
        for a in actions:
            status = "OK" if a.get("success") else "FALLO"
            action_strs.append(f"{a.get('action','?')}={status}")
        votes = item.get("votes", [])
        vote_str = "; ".join([f"{v['agent']}={v['category']}" for v in (votes or [])])

        print(f"--- #{i}: {subj} ---")
        print(f"   sender={sender} category={cat}({conf*100:.0f}%) resolver={res}")
        print(f"   votes: {vote_str}")
        print(f"   depts={dept_str} actions={action_strs}")
        print()
        sys.stdout.flush()

# Now check dashboard
print("=" * 50)
print("DASHBOARD:")
sys.stdout.flush()
r = httpx.get(f"{BASE}/dashboard/summary", headers=headers, timeout=30)
dash = r.json()
print(f"Total emails: {dash.get('total_emails')}")
print(f"Emails hoy: {dash.get('emails_today')}")
print(f"Contactos: {dash.get('contacts_by_category')}")
print()
for e in (dash.get("recent_emails") or []):
    depts = e.get("departments") or []
    dept_str = ", ".join(depts) if depts else "N/A"
    res = e.get("resolution", "")
    urg = e.get("urgency", "")
    print(f"  [{e.get('category','?')}] {e.get('subject','?')[:60]} | {dept_str} | urg={urg} | {res}")
