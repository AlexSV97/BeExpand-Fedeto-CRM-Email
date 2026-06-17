import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0

        # Clean old entries
        self._requests[client_ip] = [t for t in self._requests[client_ip] if now - t < window]

        if len(self._requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later."
            )

        self._requests[client_ip].append(now)