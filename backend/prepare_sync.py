"""
IMAP cleanup + mark 4 forwarded copies as SEEN + re-send test emails
"""
import imaplib, os, smtplib, email.message, email.utils
from dotenv import load_dotenv

load_dotenv("backend/.env")

host = "imap.gmail.com"
user = os.getenv("IMAP_USER", "beexpandcrmpoc@gmail.com")
pwd = os.getenv("IMAP_PASSWORD")

# ── Step 1: Connect IMAP and clean up ──
conn = imaplib.IMAP4_SSL(host)
conn.login(user, pwd)
conn.select("INBOX")

# Mark known forwarded copies as SEEN so they dont interfere
status, msgs = conn.search(None, "UNSEEN")
unseen_ids = msgs[0].split() if msgs[0] else []
print(f"UNSEEN antes de limpiar: {len(unseen_ids)}")

for uid in unseen_ids:
    data = conn.fetch(uid, "BODY.PEEK[HEADER.FIELDS (FROM)]")
    from_hdr = data[1][0][1].decode(errors="replace") if len(data[1]) > 0 else ""
    if "BeExpand CRM" in from_hdr:
        conn.store(uid, "+FLAGS", "\\Seen")
        print(f"  Marcado SEEN (reenviado): ID {uid.decode()}")

# Mark original 5 as UNSEEN again (remove Seen)
status, msgs = conn.search(None, "ALL")
all_ids = msgs[0].split() if msgs[0] else []
# Find the 5 original test emails by unique subjects
for uid in all_ids:
    data = conn.fetch(uid, "BODY.PEEK[HEADER.FIELDS (SUBJECT)]")
    raw = data[1][0][1].decode(errors="replace")
    if any(kw in raw for kw in ["Factura mensual", "Solicitud de presupuesto", "Orden de compra", "Propuesta de colaboracion", "Newsletter Semanal"]):
        if b"\\Seen" in conn.fetch(uid, "FLAGS")[1][0][0]:
            conn.store(uid, "-FLAGS", "\\Seen")  # Remove Seen
            subject_clean = raw.replace("Subject: ", "").strip()[:60]
            print(f"  Re-marcado UNSEEN: ID {uid.decode()} | {subject_clean}")

status, msgs = conn.search(None, "UNSEEN")
new_unseen = msgs[0].split() if msgs[0] else []
print(f"\nUNSEEN despues de limpiar: {len(new_unseen)}")

conn.logout()

print("\nInbox lista. Sincronizando con Orchestrator...")
