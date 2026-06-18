"""
Check Ollama status and clean state
"""
import httpx, sqlite3, os

# Check Ollama
try:
    r = httpx.get("http://localhost:11434/api/tags", timeout=5)
    models = r.json().get("models", [])
    print(f"Ollama: OK ({len(models)} models)")
    for m in models:
        print(f"  - {m['name']}")
except Exception as e:
    print(f"Ollama: NO ({e})")

print()

# Delete database for fresh start
db_path = "backend/aiuken.db"
if os.path.exists(db_path):
    try:
        # Try to delete - but it might be locked by the running server
        os.remove(db_path)
        print(f"Deleted: {db_path}")
    except PermissionError:
        print(f"Cannot delete {db_path} (in use by server)")
        # Clear tables instead
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM classification_history")
        conn.execute("DELETE FROM emails")
        conn.execute("DELETE FROM contacts")
        conn.commit()
        conn.close()
        print("Cleared all records from existing DB")
else:
    print("No existing DB found")
