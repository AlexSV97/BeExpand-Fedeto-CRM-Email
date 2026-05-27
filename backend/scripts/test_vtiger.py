"""Test VTiger connectivity from inside container."""
import sys; sys.path.insert(0, '/app')
import asyncio, httpx

async def test():
    # Test via Docker DNS
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("http://vtiger:80")
            print(f"vtiger:80 -> {r.status_code}")
    except Exception as e:
        print(f"vtiger:80 -> FAILED: {e}")
    
    # Test via host.docker.internal
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("http://host.docker.internal:8080")
            print(f"host.docker.internal:8080 -> {r.status_code}")
    except Exception as e:
        print(f"host.docker.internal:8080 -> FAILED: {e}")

asyncio.run(test())
