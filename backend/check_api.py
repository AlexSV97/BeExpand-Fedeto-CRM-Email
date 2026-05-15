"""
Check detailed errors from last sync by examining the actual action results
"""
import httpx

BASE = "http://localhost:8001/api/v1"

r = httpx.post(f"{BASE}/auth/login", json={
    "username": "admin",
    "password": "admin123",
})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Query emails to see stored extra_data
r = httpx.get(f"{BASE}/emails", headers=headers, timeout=30)
print("Emails API response status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print(f"Total: {len(data) if isinstance(data, list) else data}")
