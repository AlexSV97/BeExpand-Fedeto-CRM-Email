"""
1. Mark all forwarded copies as SEEN
2. Re-mark originals as UNSEEN  
3. Run sync and capture all error details
"""
import imaplib, os, sys, httpx, sqlite3
from dotenv import load_dotenv
load_dotenv("backend/.env")

USER = os.getenv("IMAP_EMAIL", "<IMAP_EMAIL_DEMO>")
PASS = os.getenv("IMAP_PASSWORD")

conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(USER, PASS)
conn.select("INBOX")

# Mark all forwarded copies SEEN
status, msgs = conn.search(None, "UNSEEN")
for uid in (msgs[0].split() if msgs[0] else []):
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM)])")
    raw = data[1][0][1].decode(errors="replace")
    if "Aiuken SOC" in raw:
        conn.store(uid, "+FLAGS", "\\Seen")

# Re-mark original test emails UNSEEN
status, msgs = conn.search(None, "ALL")
subject_kw = ["Factura mensual", "de presupuesto", "Orden de compra", "colaboracion", "Newsletter Semanal"]
remarked = 0
for uid in (msgs[0].split() if msgs[0] else []):
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
    raw = data[1][0][1].decode(errors="replace")
    flags = data[1][0][0]
    if "Aiuken SOC" in raw:
        continue
    if any(k in raw for k in subject_kw):
        if b"\\Seen" in flags:
            conn.store(uid, "-FLAGS", "\\Seen")
            remarked += 1

# Count UNSEEN
status, msgs = conn.search(None, "UNSEEN")
unseen = msgs[0].split() if msgs[0] else []
print(f"UNSEEN ready: {len(unseen)}")
conn.logout()

if not unseen:
    print("Nothing to sync. Trying to send new emails...")
    sys.exit(0)

# Clear DB
db = sqlite3.connect("backend/beexpand.db")
for tbl in ["classification_history", "emails", "contacts"]:
    db.execute(f"DELETE FROM {tbl}")
db.commit()
db.close()

# Sync with error capture
BASE = "http://localhost:8001/api/v1"
r = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "<ADMIN_PASSWORD_DEMO>")})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

print("\nSyncing...")
sys.stdout.flush()
r = httpx.post(f"{BASE}/emails/sync", headers=headers, timeout=600)
result = r.json()

print(f"fetched={result.get('fetched')} processed={result.get('processed')} errors={result.get('errors')}\n")

for item in (result.get("results") or []):
    subj = (item.get("subject") or "?")[:55]
    cat = item.get("category") or "?"
    conf = (item.get("confidence") or 0) * 100
    sender = item.get("sender_name") or "(empty)"
    
    print(f"  {cat:10s} {conf:3.0f}% sender={sender} | {subj}")
    for a in (item.get("actions") or []):
        s = "OK" if a.get("success") else "**** FALLO ****"
        d = a.get("detail", "")
        print(f"   [{s}] {a.get('action')}: {d}")
    if item.get("error"):
        print(f"   ORCH_ERROR: {item['error']}")
    print()

# Final report
db = sqlite3.connect("backend/beexpand.db")
for tbl in ["emails", "contacts"]:
    rows = db.execute(f"SELECT count(*) FROM {tbl}").fetchone()
    print(f"DB {tbl}: {rows[0]}")
db.close()
