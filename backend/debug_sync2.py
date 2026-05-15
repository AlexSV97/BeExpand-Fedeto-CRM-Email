"""
Mark forwarded copies SEEN, clear DB, mark originals UNSEEN, sync, show DB errors
"""
import imaplib, os, sys, httpx, sqlite3
from dotenv import load_dotenv

load_dotenv("backend/.env")

USER = os.getenv("IMAP_USER", "beexpandcrmpoc@gmail.com")
PASS = os.getenv("IMAP_PASSWORD")

# --- IMAP Cleanup ---
conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(USER, PASS)
conn.select("INBOX")

# Mark forwarded copies SEEN
status, msgs = conn.search(None, "UNSEEN")
for uid in (msgs[0].split() if msgs[0] else []):
    data = conn.fetch(uid, "BODY.PEEK[HEADER.FIELDS (FROM)]")
    if "BeExpand CRM" in data[1][0][1].decode(errors="replace"):
        conn.store(uid, "+FLAGS", "\\Seen")

# Re-mark originals UNSEEN
status, msgs = conn.search(None, "ALL")
subject_kw = ["Factura mensual", "de presupuesto", "Orden de compra", "colaboracion", "Newsletter Semanal"]
for uid in (msgs[0].split() if msgs[0] else []):
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
    raw = data[1][0][1].decode(errors="replace")
    if "BeExpand CRM" in raw:
        continue
    if any(k in raw for k in subject_kw) and b"\\Seen" in data[1][0][0]:
        conn.store(uid, "-FLAGS", "\\Seen")

conn.logout()
print("1. IMAP ready - forwarded marked SEEN, originals UNSEEN")

# --- Clear DB ---
db = sqlite3.connect("backend/beexpand.db")
for table in ["classification_history", "emails", "contacts"]:
    db.execute(f"DELETE FROM {table}")
db.commit()
db.close()
print("2. DB cleared")

# --- Sync ---
BASE = "http://localhost:8001/api/v1"
r = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

print("3. Syncing...")
sys.stdout.flush()
r = httpx.post(f"{BASE}/emails/sync", headers=headers, timeout=600)
result = r.json()

print(f"   fetched={result.get('fetched')} processed={result.get('processed')} errors={result.get('errors')}\n")

for item in (result.get("results") or []):
    subj = (item.get("subject") or "?")[:50]
    cat = item.get("category") or "?"
    print(f"  {cat:10s} | {subj}")
    for a in (item.get("actions") or []):
        s = "OK" if a["success"] else "FALLO"
        d = a.get("detail", "")
        print(f"         [{s}] {a['action']}: {d}")
    if item.get("error"):
        print(f"         ERROR: {item['error']}")
    print()

print("4. DB State:")
db = sqlite3.connect("backend/beexpand.db")
for table in ["emails", "contacts"]:
    rows = db.execute(f"SELECT * FROM {table}").fetchall()
    print(f"   {table}: {len(rows)} rows")
    for r in rows[:5]:
        print(f"     {r}")
db.close()
