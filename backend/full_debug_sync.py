"""
Clean up forwarded copies, re-mark originals as UNSEEN, then sync with full error detail
"""
import imaplib, os, sys, httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")

conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(
    os.getenv("IMAP_USER", "<IMAP_USER_DEMO>"),
    os.getenv("IMAP_PASSWORD"),
)
conn.select("INBOX")

# Step 1: Mark all forwarded copies (Aiuken SOC) as SEEN
status, msgs = conn.search(None, "UNSEEN")
unseen = msgs[0].split() if msgs[0] else []
marked = 0
for uid in unseen:
    data = conn.fetch(uid, "BODY.PEEK[HEADER.FIELDS (FROM)]")
    raw = data[1][0][1].decode(errors="replace")
    if "Aiuken SOC" in raw:
        conn.store(uid, "+FLAGS", "\\Seen")
        marked += 1
print(f"Forwarded copies marked SEEN: {marked}")

# Step 2: Re-mark original 5 test emails as UNSEEN
status, msgs = conn.search(None, "ALL")
all_ids = msgs[0].split() if msgs[0] else []
remarked = 0
for uid in all_ids:
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
    raw_header = data[1][0][1].decode(errors="replace")
    flags_raw = data[1][0][0]
    
    if "Aiuken SOC" in raw_header:
        continue  # skip forwarded copies
    
    subject_keywords = ["Factura mensual", "de presupuesto", "Orden de compra", "colaboracion", "Newsletter Semanal"]
    if any(kw in raw_header for kw in subject_keywords):
        if b"\\Seen" in flags_raw:
            conn.store(uid, "-FLAGS", "\\Seen")
            remarked += 1

conn.logout()

print(f"Originals re-marked UNSEEN: {remarked}")
print()

# Step 3: Clear DB and re-sync with full error details
print("Clearing DB...")
conn2 = sqlite3.connect("backend/aiuken.db")
conn2.execute("DELETE FROM classification_history")
conn2.execute("DELETE FROM emails")
conn2.execute("DELETE FROM contacts")
conn2.commit()
conn2.close()
print("DB cleared.")
print()

# Step 4: Sync
import sqlite3
BASE = "http://localhost:8001/api/v1"

r = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "<ADMIN_PASSWORD_DEMO>")})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("Syncing with Orchestrator...")
sys.stdout.flush()

r = httpx.post(f"{BASE}/emails/sync", headers=headers, timeout=600)
result = r.json()

print(f"Time: 514s (from previous run)")
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
    
    print(f"#{i} {subj}")
    print(f"   cat={cat}({conf:.0f}%) res={res}")
    
    for a in (item.get("actions") or []):
        status = "OK" if a.get("success") else "FALLO"
        detail = a.get("detail", "")
        print(f"   [{status}] {a.get('action')}: {detail}")
    
    if item.get("error"):
        print(f"   ORCH_ERROR: {item['error']}")
    print()

# Final DB state
r = httpx.get(f"{BASE}/dashboard/summary", headers=headers, timeout=30)
dash = r.json()
print(f"Dashboard: {dash.get('total_emails')} emails, contacts={dash.get('contacts_by_category')}")
