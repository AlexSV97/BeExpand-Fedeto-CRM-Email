"""
Re-run sync and capture detailed error messages for DB failures
"""
import httpx, sys

BASE = "http://localhost:8001/api/v1"

r = httpx.post(f"{BASE}/auth/login", json={
    "username": "admin",
    "password": "admin123",
})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# First check existing emails in DB
r = httpx.get(f"{BASE}/emails", headers=headers, timeout=30)
emails_data = r.json()
print(f"Existing emails in DB: {len(emails_data) if isinstance(emails_data, list) else 0}")

# Run sync
print("\nSyncing 8 INBOX emails...")
sys.stdout.flush()

r = httpx.post(f"{BASE}/emails/sync", headers=headers, timeout=600)
result = r.json()

print(f"Connected: {result.get('connected')}")
print(f"Fetched: {result.get('fetched')}")
print(f"Processed: {result.get('processed')}")
print(f"Errors: {result.get('errors')}")
print()

for i, item in enumerate((result.get("results") or []), 1):
    subj = (item.get("subject") or "?")[:55]
    cat = item.get("category") or "?"
    conf = (item.get("confidence") or 0) * 100
    res = item.get("resolution") or "?"
    
    print(f"--- #{i}: {subj} ---")
    print(f"   cat={cat}({conf:.0f}%) res={res}")
    for a in (item.get("actions") or []):
        status = "OK" if a.get("success") else "FALLO"
        detail = a.get("detail", "")
        print(f"   [{status}] {a.get('action')}: {detail}")
    
    if item.get("error"):
        print(f"   ORCH_ERROR: {item['error']}")
    print()

# Final DB check  
r = httpx.get(f"{BASE}/dashboard/summary", headers=headers, timeout=30)
dash = r.json()
print(f"Total en DB: {dash.get('total_emails')}")
print(f"Contactos: {dash.get('contacts_by_category')}")
