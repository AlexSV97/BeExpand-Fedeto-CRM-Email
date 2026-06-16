from __future__ import annotations

from collections.abc import Callable

import httpx

from src.domain.ticketing import Queue, SLA, Ticket
from src.integrations.otrs_znuny.settings import OtrsZnunySettings


class OtrsZnunyError(RuntimeError):
    pass


class OtrsZnunyConfigurationError(OtrsZnunyError):
    pass


class OtrsZnunyClient:
    def __init__(
        self,
        settings: OtrsZnunySettings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or OtrsZnunySettings()
        self._client = httpx.AsyncClient(
            base_url=self._settings.normalized_base_url or "http://localhost",
            timeout=self._settings.timeout_seconds,
            headers=self._settings.auth_headers(),
            transport=transport,
        )
        self._closed = False

    async def __aenter__(self) -> "OtrsZnunyClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if not self._closed:
            await self._client.aclose()
            self._closed = True

    def _ensure_configured(self) -> None:
        if not self._settings.is_configured:
            raise OtrsZnunyConfigurationError("OTRS/Znuny integration is not configured")

    async def _request(self, method: str, path: str, params: dict[str, str | int] | None = None) -> dict | list:
        self._ensure_configured()
        response = await self._client.request(method, path, params=params)
        if response.status_code >= 400:
            raise OtrsZnunyError(f"OTRS/Znuny API error {response.status_code}: {response.text}")
        if not response.content:
            return {}
        return response.json()

    @staticmethod
    def _unwrap_collection(payload: dict | list, plural_key: str) -> list[dict]:
        if isinstance(payload, list):
            return payload
        for key in (plural_key, "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    @staticmethod
    def _unwrap_single(payload: dict | list, singular_key: str) -> dict:
        if isinstance(payload, list):
            return payload[0] if payload else {}
        value = payload.get(singular_key)
        if isinstance(value, dict):
            return value
        for key in ("data", "item", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return candidate
        return payload

    async def list_tickets(
        self,
        *,
        queue: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if queue:
            params["queue"] = queue
        payload = await self._request("GET", self._settings.tickets_path(), params=params)
        items = self._unwrap_collection(payload, "tickets")
        return [Ticket.model_validate(item) for item in items]

    async def get_ticket(self, ticket_id: str) -> Ticket:
        payload = await self._request("GET", self._settings.ticket_path(ticket_id))
        ticket = self._unwrap_single(payload, "ticket")
        return Ticket.model_validate(ticket)

    async def list_queues(self) -> list[Queue]:
        payload = await self._request("GET", self._settings.queues_path())
        return [Queue.model_validate(item) for item in self._unwrap_collection(payload, "queues")]

    async def list_slas(self) -> list[SLA]:
        payload = await self._request("GET", self._settings.slas_path())
        return [SLA.model_validate(item) for item in self._unwrap_collection(payload, "slas")]
