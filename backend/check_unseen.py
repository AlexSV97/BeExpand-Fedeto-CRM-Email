"""
Check current UNSEEN count and clean up old test emails
"""
import imaplib, os
from dotenv import load_dotenv

load_dotenv("backend/.env")

conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(
    os.getenv("IMAP_USER", "<IMAP_USER_DEMO>"),
    os.getenv("IMAP_PASSWORD"),
)
conn.select("INBOX")

status, msgs = conn.search(None, "UNSEEN")
unseen_ids = msgs[0].split() if msgs[0] else []
print(f"UNSEEN total: {len(unseen_ids)}")

for uid in unseen_ids:
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
    raw = data[1][0][1].decode(errors="replace").replace("\r\n", " | ").strip()[:120]
    print(f"  ID {uid.decode():>3}: {raw}")

conn.logout()
