"""
Mark original 5 test emails as UNSEEN (remove Seen flag)
"""
import imaplib, os
from dotenv import load_dotenv

load_dotenv("backend/.env")

conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(
    os.getenv("IMAP_USER", "<IMAP_USER_DEMO>"),
    os.getenv("IMAP_PASSWORD")
)
conn.select("INBOX")

status, msgs = conn.search(None, "ALL")
all_ids = msgs[0].split() if msgs[0] else []

# Find original test emails by known keywords in subject
subject_keywords = ["Factura mensual", "de presupuesto", "Orden de compra", "colaboracion", "Newsletter Semanal"]

for uid in all_ids:
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
    raw_header = data[1][0][1].decode(errors="replace")
    flags = data[1][0][0]
    
    # Only process if NOT a forwarded copy (dont contain "Aiuken SOC" in From)
    if "Aiuken SOC" in raw_header:
        continue
    
    if any(kw in raw_header for kw in subject_keywords):
        is_seen = b"\\Seen" in flags
        subject_clean = raw_header.replace("Subject: ", "").split("\\r\\n")[0][:60]
        if is_seen:
            conn.store(uid, "-FLAGS", "\\Seen")
            print(f"  Marcado UNSEEN: ID {uid.decode()} | {subject_clean}")
        else:
            same_from = "Maria Garcia" in raw_header or "Carlos" in raw_header or "Ana Lopez" in raw_header or "Javier Ruiz" in raw_header or "Newsletter" in raw_header
            if same_from:
                print(f"  Ya UNSEEN: ID {uid.decode()} | {subject_clean}")

# Check result
status, msgs = conn.search(None, "UNSEEN")
unseen_ids = msgs[0].split() if msgs[0] else []
print(f"\nUNSEEN despues: {len(unseen_ids)}")
for uid in unseen_ids:
    data = conn.fetch(uid, "BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)]")
    raw = data[1][0][1].decode(errors="replace").strip()[:100]
    print(f"  ID {uid.decode()}: {raw}")

conn.logout()
