"""
Cliente LLM unificado — OpenRouter con fallback a Ollama local.

- Si OPENROUTER_API_KEY está configurada → usa OpenRouter (cloud).
- Si no → fallback automático a Ollama (http://localhost:11434).
- El modelo se adapta según el backend activo.
"""

import asyncio
import json
import logging
import random
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_OLLAMA_BASE = "http://localhost:11434"
_OLLAMA_FALLBACK_MODEL = "qwen2.5:7b"


class LLMClient:
    """
    Cliente para llamadas LLM vía OpenRouter (preferido) u Ollama local (fallback).

    Uso:
        client = LLMClient(model="openrouter/owl-alpha")
        text = await client.generate("prompt")

    Si OPENROUTER_API_KEY no está configurada, usa Ollama automáticamente.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: int | None = None,
        use_chat_model: bool = False,
    ):
        settings = get_settings()
        self._settings = settings
        self._use_ollama = not settings.openrouter_api_key

        if self._use_ollama:
            # Modelo para Ollama — si se pidió un modelo específico, usarlo
            if model:
                self.model = model
            elif use_chat_model:
                # Para chat/classifier usamos el modelo principal de Ollama
                self.model = _OLLAMA_FALLBACK_MODEL
            else:
                self.model = settings.openrouter_model or _OLLAMA_FALLBACK_MODEL
            logger.info("LLMClient: usando Ollama (%s) — sin OPENROUTER_API_KEY", self.model)
        else:
            if model:
                self.model = model
            elif use_chat_model:
                self.model = settings.openrouter_chat_model
            else:
                self.model = settings.openrouter_model

        self.timeout = timeout or settings.openrouter_timeout or 120

    # ── API Pública ──────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 256,
    ) -> str:
        """Llamada tipo 'generate': prompt → texto."""
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
        """Envía a OpenRouter u Ollama según configuración."""
        if self._use_ollama:
            return await self._ollama_chat(messages, temperature, max_tokens)
        return await self._openrouter_chat(messages, temperature, max_tokens)

    async def _ollama_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Llama a Ollama (http://localhost:11434/api/chat) con timeout."""
        url = f"{_OLLAMA_BASE}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return content.strip() if content else ""
        except httpx.ConnectError:
            logger.error(
                "Ollama no disponible en %s. ¿Está corriendo? "
                "Ejecutá: ollama serve", _OLLAMA_BASE
            )
            raise
        except Exception:
            logger.exception("Ollama call failed (model: %s)", self.model)
            raise

    async def _openrouter_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Llama a OpenRouter (OpenAI-compatible) con reintentos ante rate limits."""
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

        max_retries = 6
        base_delay = 3.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self._settings.openrouter_base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                    if resp.status_code in (429, 502, 503):
                        retry_after = 0.0
                        try:
                            meta = resp.json().get("metadata", {})
                            retry_after = float(meta.get("retry_after_seconds_raw", 0))
                        except Exception:
                            pass

                        delay = max(retry_after, base_delay * (2**attempt))
                        # Añadir jitter ±20% para evitar thundering herd
                        jitter = random.uniform(0.8, 1.2)
                        delay *= jitter
                        logger.warning(
                            "OpenRouter %d, retry %d/%d in %.1fs",
                            resp.status_code, attempt + 1, max_retries, delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip() if content else ""

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    jitter = random.uniform(0.8, 1.2)
                    delay *= jitter
                    logger.warning(
                        "OpenRouter timeout, retry %d/%d in %.1fs",
                        attempt + 1, max_retries, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception("OpenRouter timeout after %d retries", max_retries)
                raise
            except Exception:
                logger.exception("OpenRouter call failed")
                raise

        raise RuntimeError(
            f"OpenRouter rate limited after {max_retries} retries"
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text using OpenRouter.

        Uses text-embedding-3-small (OpenAI-compatible via OpenRouter).
        Falls back to a zero vector if the API call fails.
        """
        if self._use_ollama:
            logger.warning("Embeddings no disponibles con Ollama — devolviendo vector cero")
            return [0.0] * 768

        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "text-embedding-3-small",
            "input": text,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._settings.openrouter_base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["data"][0]["embedding"]
                else:
                    logger.warning(
                        "Embedding API returned %d: %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return [0.0] * 768
        except Exception:
            logger.exception("Embedding generation failed, returning zero vector")
            return [0.0] * 768  # zero vector = no semantic match
