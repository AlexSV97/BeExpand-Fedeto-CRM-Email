"""
Full diagnostic: check ALL emails in inbox, DB state, server logs
"""
import imaplib, os
from dotenv import load_dotenv

load_dotenv("backend/.env")

host = "imap.gmail.com"
user = os.getenv("IMAP_USER", "beexpandcrmpoc@gmail.com")
pwd = os.getenv("IMAP_PASSWORD")

conn = imaplib.IMAP4_SSL(host)
conn.login(user, pwd)
conn.select("INBOX")

status, msgs = conn.search(None, "ALL")
all_ids = msgs[0].split() if msgs[0] else []
print(f"Total emails in INBOX: {len(all_ids)}")

status, msgs = conn.search(None, "UNSEEN")
unseen_ids = msgs[0].split() if msgs[0] else []
print(f"UNSEEN: {len(unseen_ids)}")
print()

# Show last 10 emails (regardless of Seen/Unseen)
last_10 = all_ids[-10:]
print("=== Last 10 emails in INBOX ===")
for uid in last_10:
    data = conn.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
    flags = data[1][0][0].decode() if isinstance(data[1][0][0], bytes) else str(data[1][0][0])
    raw_header = data[1][0][1].decode(errors="replace") if isinstance(data[1][0][1], bytes) else str(data[1][0][1])
    seen_status = "[SEEN]" if b"\\Seen" in data[1][0][0] else "[UNSEEN]"
    line = raw_header.strip()[:120].encode("ascii", errors="replace").decode("ascii")
    print(f"  ID {uid.decode():>3} {seen_status} | {line}")

conn.logout()
