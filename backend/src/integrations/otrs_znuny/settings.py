from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OtrsZnunySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OTRS_ZNUNY_", env_file=".env", extra="ignore")

    base_url: str = ""
    api_token: str = ""
    api_prefix: str = "/api/v1"
    timeout_seconds: float = 15.0
    verify_ssl: bool = True
    default_queue: str = "Support"
    default_sla: str = "Standard"
    ai_actor_name: str = "Aiuken SOC AI"
    human_actor_name: str = "Human Operator"

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("api_prefix")
    @classmethod
    def _normalize_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            return f"/{value.lstrip('/')}"
        return value.rstrip("/") or "/api/v1"

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_token)

    def _join_path(self, suffix: str) -> str:
        return f"{self.api_prefix.rstrip('/')}{suffix}"

    def tickets_path(self) -> str:
        return self._join_path("/tickets")

    def ticket_path(self, ticket_id: str) -> str:
        return f"{self.tickets_path().rstrip('/')}/{ticket_id}"

    def ticket_articles_path(self, ticket_id: str) -> str:
        return f"{self.ticket_path(ticket_id).rstrip('/')}/articles"

    def ticket_update_path(self, ticket_id: str) -> str:
        return self.ticket_path(ticket_id)

    def queues_path(self) -> str:
        return self._join_path("/queues")

    def slas_path(self) -> str:
        return self._join_path("/slas")

    def auth_headers(self) -> dict[str, str]:
        if not self.api_token:
            return {"Accept": "application/json"}
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
