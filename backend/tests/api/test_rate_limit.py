"""
Tests for the SOC rate limiter middleware.

Verifies that:
- Requests under the limit pass through
- Requests exceeding the limit raise HTTP 429
- Different IPs have independent counters
- The limiter cleans old entries after the window expires
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.middleware.rate_limit import RateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_request(client_ip: str = "127.0.0.1") -> MagicMock:
    """Create a mock Request with the given client IP."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = client_ip
    return request


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Unit tests for the RateLimiter class."""

    async def test_allows_under_limit(self):
        """Requests under the limit should pass without error."""
        limiter = RateLimiter(requests_per_minute=60)

        for _ in range(10):
            request = make_request("127.0.0.1")
            result = await limiter(request)
            assert result is None  # No exception means allowed

    async def test_raises_429_when_over_limit(self):
        """The 11th request in the same minute should be blocked."""
        limiter = RateLimiter(requests_per_minute=10)

        # First 10 should pass
        for _ in range(10):
            request = make_request("10.0.0.1")
            await limiter(request)

        # 11th should raise
        request = make_request("10.0.0.1")
        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    async def test_different_ips_have_independent_counters(self):
        """Each IP gets its own counter — one IP hitting the limit
        should not affect another IP."""
        limiter = RateLimiter(requests_per_minute=5)

        # Exhaust IP A
        for _ in range(5):
            await limiter(make_request("192.168.1.1"))

        # IP A should now be blocked
        with pytest.raises(HTTPException) as exc_info:
            await limiter(make_request("192.168.1.1"))
        assert exc_info.value.status_code == 429

        # IP B should still be allowed (independent counter)
        for _ in range(5):
            result = await limiter(make_request("192.168.1.2"))
            assert result is None

    async def test_handles_missing_client(self):
        """When request.client is None, the limiter should use 'unknown'."""
        limiter = RateLimiter(requests_per_minute=5)
        request = MagicMock()
        request.client = None

        for _ in range(5):
            result = await limiter(request)
            assert result is None

        # 6th should fail
        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)
        assert exc_info.value.status_code == 429

    async def test_allows_request_after_window_expires(self):
        """After the 60-second window expires, old entries are cleaned
        and new requests are allowed again."""
        limiter = RateLimiter(requests_per_minute=2)
        request = make_request("10.0.0.2")

        # Use up the limit
        await limiter(request)
        await limiter(request)

        # Should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)
        assert exc_info.value.status_code == 429

        # Manually age the timestamps past the 60s window
        # The limiter stores floats in _requests. We can access the
        # internal dict to simulate time passing.
        old_time = time.time() - 120  # 2 minutes ago
        limiter._requests["10.0.0.2"] = [old_time]

        # Should be allowed again (old entries were cleaned)
        result = await limiter(request)
        assert result is None

    async def test_high_limit_does_not_block_legitimate_traffic(self):
        """A limit of 1000 requests per minute should not block 100 requests."""
        limiter = RateLimiter(requests_per_minute=1000)
        request = make_request("10.0.0.3")

        for _ in range(100):
            result = await limiter(request)
            assert result is None

    async def test_zero_limit_blocks_immediately(self):
        """A limit of 0 should block even the first request."""
        limiter = RateLimiter(requests_per_minute=0)
        request = make_request("10.0.0.4")

        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)
        assert exc_info.value.status_code == 429
