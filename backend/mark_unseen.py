"""
Mark original 5 test emails as UNSEEN
"""
import imaplib, os
from dotenv import load_dotenv

load_dotenv("backend/.env")

conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(
    os.getenv("IMAP_USER", "beexpandcrmpoc@gmail.com"),
    os.getenv("IMAP_PASSWORD"),
)
conn.select("INBOX")

status, msgs = conn.search(None, "ALL")
all_ids = msgs[0].split() if msgs[0] else []

subject_keywords = ["Factura mensual", "de presupuesto", "Orden de compra", "colaboracion", "Newsletter Semanal"]

for uid in all_ids:
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
    raw_header = data[1][0][1].decode(errors="replace")
    flags_raw = data[1][0][0]
    
    # Skip forwarded copies
    if "BeExpand CRM" in raw_header:
        continue
    
    # Mark as UNSEEN if it matches our test emails
    if any(kw in raw_header for kw in subject_keywords):
        is_seen = b"\\Seen" in flags_raw
        if is_seen:
            conn.store(uid, "-FLAGS", "\\Seen")
        subject_clean = raw_header.split("Subject: ")[1].split("\\r")[0][:60] if "Subject: " in raw_header else raw_header[:60]
        status_label = "UNSEEN" if is_seen else "already UNSEEN"
        print(f"  [{status_label}] ID {uid.decode()} | {subject_clean}")

conn.logout()

print("\nDone. Ready to sync.")
