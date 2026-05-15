"""
Check DB state after sync
"""
import sqlite3, json

conn = sqlite3.connect("backend/beexpand.db")
cur = conn.cursor()

print("=== EMAILS ===")
cur.execute("SELECT id, subject, category, sender_name, sender_email FROM emails ORDER BY received_at DESC")
rows = cur.fetchall()
print(f"Total: {len(rows)}")
for r in rows:
    subj = (r[1] or "?")[:60]
    print(f"  cat={r[2]:10s} | name={r[3]:20s} | email={r[4]} | subj={subj}")

print()

print("=== CONTACTS ===")
cur.execute("SELECT name, email, category, company, email_count FROM contacts")
rows = cur.fetchall()
print(f"Total: {len(rows)}")
for r in rows:
    print(f"  name={r[0]:20s} | email={r[1]:30s} | cat={r[2]:10s} | emp={r[3] or 'N/A':15s} | count={r[4]}")

print()

print("=== CLASSIFICATION HISTORY ===")
cur.execute("SELECT id, email_id, category, method FROM classification_history")
rows = cur.fetchall()
print(f"Total: {len(rows)}")
for r in rows:
    eid = r[1][:8] if r[1] else "?"
    print(f"  email={eid} | {r[2]:10s} | {r[3]}")

print()

# Check last error from extra_data
cur.execute("SELECT subject, extra_data FROM emails WHERE extra_data LIKE '%error%' OR extra_data LIKE '%FALLO%'")
rows = cur.fetchall()
if rows:
    print("=== EMAILS WITH ERRORS ===")
    for r in rows:
        ed = json.loads(r[1])
        print(f"  subj={r[0][:50]}")

# Get details from failed DB saves - check if there are any error messages
# The action results are stored in the sync response but not in DB
# Let me check for duplicates
print()
print("=== CHECK MESSAGE_ID DUPLICATES ===")
cur.execute("SELECT message_id, COUNT(*) FROM emails GROUP BY message_id HAVING COUNT(*) > 1")
rows = cur.fetchall()
print(f"Duplicados: {len(rows)}")

# Check sender emails
print()
print("=== CHECK SENDER EMAILS ===")
cur.execute("SELECT sender_email, COUNT(*) FROM emails GROUP BY sender_email")
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]:35s} x{r[1]}")

conn.close()
