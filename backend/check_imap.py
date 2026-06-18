"""
Check how many UNSEEN emails are in Gmail inbox
"""
import imaplib
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

host = "imap.gmail.com"
user = os.getenv("IMAP_USER", "<IMAP_USER_DEMO>")
pwd = os.getenv("IMAP_PASSWORD")

print(f"Checking IMAP for {user}...")
conn = imaplib.IMAP4_SSL(host)
conn.login(user, pwd)
conn.select("INBOX")

status, msgs = conn.search(None, "ALL")
all_ids = msgs[0].split() if msgs[0] else []
print(f"Total emails in INBOX: {len(all_ids)}")

# Check unseen
status, msgs = conn.search(None, "UNSEEN")
unseen_ids = msgs[0].split() if msgs[0] else []
print(f"UNSEEN emails: {len(unseen_ids)}")

for uid in unseen_ids[:10]:
    data = conn.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
    raw = data[1][0][1].decode(errors="replace").strip()
    print(f"  [{uid.decode()}] {raw[:150]}")

conn.logout()
