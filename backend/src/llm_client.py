"""
Cliente LLM unificado — OpenRouter (OpenAI-compatible) con fallback a Ollama.

Reemplaza todas las llamadas directas a Ollama en el código.
Cuando OPENROUTER_API_KEY está configurada, usa OpenRouter.
Si no, usa Ollama local como fallback (desarrollo local).
"""

import json
import logging
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Cliente unificado para llamadas LLM.

    Soporta:
    - OpenRouter API (OpenAI-compatible) — principal
    - Ollama API (local) — fallback automático

    Uso:
        client = LLMClient(model="qwen/qwen2.5-7b-instruct")
        text = await client.generate("prompt")
        text = await client.chat([{"role": "user", "content": "hola"}])
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: int | None = None,
        use_chat_model: bool = False,
    ):
        settings = get_settings()
        self._settings = settings

        # Elegir modelo según el contexto
        if model:
            self.model = model
        elif use_chat_model and settings.openrouter_api_key:
            self.model = settings.openrouter_chat_model
        elif settings.openrouter_api_key:
            self.model = settings.openrouter_model
        elif use_chat_model:
            self.model = settings.ollama_model
        else:
            self.model = settings.ollama_model

        self.timeout = timeout or settings.openrouter_timeout or 120
        self.use_openrouter = bool(settings.openrouter_api_key)

    # ── API Pública ──────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 256,
    ) -> str:
        """
        Llamada tipo 'generate': prompt → texto.

        Internamente se envía como chat completions con un único mensaje user.
        """
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]
        return await self._chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """Llamada tipo 'chat': lista de mensajes → respuesta."""
        return await self._chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ── Interno ──────────────────────────────────────────────────────────────

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Llama a OpenRouter o fallback a Ollama según configuración."""
        if self.use_openrouter:
            return await self._call_openrouter(messages, temperature, max_tokens)
        return await self._call_ollama(messages, temperature, max_tokens)

    async def _call_openrouter(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """OpenRouter API (OpenAI-compatible)."""
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self._settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content.strip() if content else ""
        except Exception:
            logger.exception("OpenRouter call failed")
            raise

    async def _call_ollama(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ollama API local (fallback)."""
        # Si es un solo mensaje user, usamos /api/generate
        # Si son múltiples (chat), usamos /api/chat
        if len(messages) == 1 and messages[0]["role"] == "user":
            return await self._ollama_generate(
                messages[0]["content"], temperature, max_tokens
            )
        return await self._ollama_chat(messages, temperature, max_tokens)

    async def _ollama_generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ollama /api/generate (prompt simple)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self._settings.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()

    async def _ollama_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ollama /api/chat (mensajes)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self._settings.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
