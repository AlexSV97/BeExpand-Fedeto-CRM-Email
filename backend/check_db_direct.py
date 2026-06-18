"""
Check the aiuken.db database directly
"""
import sqlite3
import json

conn = sqlite3.connect("backend/aiuken.db")
cur = conn.cursor()

# Emails
cur.execute("SELECT id, subject, category, sender_name, sender_email FROM emails ORDER BY received_at DESC")
rows = cur.fetchall()
print(f"=== EMAILS: {len(rows)} ===")
for r in rows:
    subj = (r[1] or "?")[:70]
    print(f"  {r[2]:12s} | {r[3]:20s} | {subj}")

print()

# Contacts
cur.execute("SELECT id, name, email, category, company FROM contacts ORDER BY created_at DESC")
rows = cur.fetchall()
print(f"=== CONTACTOS: {len(rows)} ===")
for r in rows:
    comp = r[4] or "N/A"
    print(f"  {r[1]:20s} | {r[2]:30s} | {r[3]:12s} | {comp}")

print()

# Classification history
cur.execute("SELECT email_id, category, method FROM classification_history ORDER BY created_at DESC")
rows = cur.fetchall()
print(f"=== CLASSIFICATION HISTORY: {len(rows)} entries ===")
for r in rows:
    eid = r[0][:8] if r[0] else "?"
    print(f"  email={eid} | {r[1]:10s} | {r[2]}")

print()

# Extra data from first email
cur.execute("SELECT id, subject, extra_data FROM emails LIMIT 1")
r = cur.fetchone()
if r:
    ed = json.loads(r[2])
    print(f"=== EXTRA DATA: {r[1][:50]} ===")
    print(f"  resolution_method: {ed.get('resolution_method')}")
    print(f"  confidence: {ed.get('confidence')}")
    print(f"  votes: {json.dumps(ed.get('votes'), indent=4)}")
    print(f"  routing: {json.dumps(ed.get('routing'), indent=4)}")
    print(f"  analyzer: {json.dumps(ed.get('analyzer'), indent=4)}")
    print(f"  processing_time_ms: {ed.get('processing_time_ms')}")

conn.close()
