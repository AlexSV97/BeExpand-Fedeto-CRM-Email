"""
VtigerClient — Cliente HTTP para la API REST de VTiger CRM.

VTiger usa un sistema de autenticación por "challenge":
  1. GET /webservice.php?operation=getchallenge&username=X
     → Recibís un challenge (token temporal)
  2. POST /webservice.php?operation=login
     → Mandás username + accessKey = MD5(challenge + tu_access_key)
     → Recibís un sessionId
  3. Usás ese sessionId en todas las llamadas siguientes

Si VTiger no responde, el cliente no rompe el pipeline —
lanza excepciones que CrmSyncService captura y maneja.
"""

import hashlib
import json
import logging
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Los endpoints de VTiger siempre pasan por webservice.php
VTIGER_WS = "/webservice.php"


class VtigerClientError(Exception):
    """Error genérico de comunicación con VTiger."""
    pass


class VtigerAuthError(VtigerClientError):
    """Error de autenticación (credenciales inválidas)."""
    pass


class VtigerClient:
    """Cliente asincrónico para la API REST de VTiger CRM.

    Uso:
        client = VtigerClient(
            url="https://tudominio.vtiger.com",
            username="admin@correo.com",
            access_key="xxx",
        )
        await client.login()
        contact_id = await client.create_contact({
            "email": "cliente@mail.com",
            "lastname": "García",
            "cf_1012": "Lead",
        })
    """

    def __init__(
        self,
        url: str,
        username: str,
        access_key: str,
        api_version: str = "v1",
        timeout: float = 30.0,
    ):
        """
        Args:
            url: URL base de VTiger (ej: https://tudominio.vtiger.com).
            username: Email del usuario de VTiger.
            access_key: Clave de acceso (la genera VTiger, no es la contraseña).
            api_version: Versión de la API (default: "v1").
            timeout: Timeout en segundos para cada llamada HTTP (default: 30).
        """
        self._base_url = url.rstrip("/")
        self._username = username
        self._access_key = access_key
        self._api_version = api_version
        self._session_id: Optional[str] = None  # Se setea en login()

        # Cliente HTTP asincrónico — una sola instancia para toda la vida del client
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
        )

    # ──────────────────────────────────────────────
    # AUTENTICACIÓN
    # ──────────────────────────────────────────────

    async def login(self) -> str:
        """Obtiene un sessionId de VTiger.

        Flujo:
            1. Pide un challenge (token temporal) con GET getchallenge
            2. Calcula accessKey = MD5(challenge + tu_access_key)
            3. Envía login con username + accessKey
            4. Recibe sessionId (válido por varias horas)

        Returns:
            El sessionId obtenido.

        Raises:
            VtigerAuthError: Si las credenciales son inválidas.
            VtigerClientError: Si hay error de conexión.
        """
        # ── Paso 1: Obtener challenge ──
        challenge = await self._get_challenge()
        logger.debug("Challenge obtenido exitosamente")

        # ── Paso 2: Calcular accessKey = MD5(challenge + access_key) ──
        # Este es el mecanismo de seguridad de VTiger:
        # nunca mandás tu access_key directamente, solo una combinación
        # con el challenge que expira después de usarse.
        key = hashlib.md5(
            f"{challenge}{self._access_key}".encode("utf-8")
        ).hexdigest()

        # ── Paso 3: Login ──
        params = {
            "operation": "login",
            "username": self._username,
            "accessKey": key,
        }

        data = await self._post(params)

        # VTiger devuelve éxito si tiene "sessionName" en el resultado
        if data.get("success") and data.get("result", {}).get("sessionName"):
            self._session_id = data["result"]["sessionName"]
            logger.info("Login exitoso en VTiger")
            return self._session_id

        # Si no tiene sessionName, probablemente las credenciales son inválidas
        error = data.get("error", {}).get("message", "Error desconocido")
        raise VtigerAuthError(f"Error de autenticación en VTiger: {error}")

    async def _get_challenge(self) -> str:
        """Pide un token de desafío a VTiger.

        GET /webservice.php?operation=getchallenge&username=...

        Returns:
            El token challenge (string).

        Raises:
            VtigerClientError: Si no se puede obtener el challenge.
        """
        params = {
            "operation": "getchallenge",
            "username": self._username,
        }

        response = await self._http.get(VTIGER_WS, params=params)

        if response.status_code != 200:
            raise VtigerClientError(
                f"Error HTTP {response.status_code} al obtener challenge"
            )

        data = response.json()
        if data.get("success") and data.get("result", {}).get("token"):
            return data["result"]["token"]

        error = data.get("error", {}).get("message", "Respuesta inesperada")
        raise VtigerClientError(f"Error al obtener challenge: {error}")

    # ──────────────────────────────────────────────
    # OPERACIONES CON CONTACTOS
    # ──────────────────────────────────────────────

    async def get_contact_by_email(self, email: str) -> Optional[dict]:
        """Busca un contacto en VTiger por su email.

        Args:
            email: Email del contacto a buscar.

        Returns:
            Dict con los datos del contacto si existe, None si no.
        """
        # Asegurarse de tener sesión activa
        if not self._session_id:
            await self.login()

        # VTiger search usa el módulo y una condición tipo SQL
        params = {
            "operation": "search",
            "sessionName": self._session_id,
            "query": (
                f"SELECT * FROM Contacts "
                f"WHERE email = '{email}' LIMIT 1;"
            ),
        }

        response = await self._http.get(VTIGER_WS, params=params)

        if response.status_code != 200:
            logger.warning("Error HTTP %s al buscar contacto %s", response.status_code, email)
            return None

        data = response.json()
        if data.get("success") and data.get("result"):
            # Devuelve lista aunque tenga 1 resultado
            results = data["result"]
            if isinstance(results, list) and len(results) > 0:
                return results[0]

        return None

    async def create_contact(self, contact_data: dict) -> Optional[str]:
        """Crea un contacto nuevo en VTiger.

        Args:
            contact_data: Dict con los campos del contacto
                         (email, lastname, assigned_user_id, etc.).

        Returns:
            ID del contacto creado, o None si falla.
        """
        return await self._create_record("Contacts", contact_data)

    async def update_contact(self, contact_id: str, contact_data: dict) -> bool:
        """Actualiza un contacto existente en VTiger.

        Args:
            contact_id: ID del contacto a actualizar.
            contact_data: Dict con los campos a modificar.

        Returns:
            True si se actualizó correctamente, False si no.
        """
        return await self._update_record("Contacts", contact_id, contact_data)

    # ──────────────────────────────────────────────
    # OPERACIONES CON OPORTUNIDADES
    # ──────────────────────────────────────────────

    async def create_opportunity(
        self,
        potential_data: dict,
    ) -> Optional[str]:
        """Crea una oportunidad (Potential) en VTiger.

        Args:
            potential_data: Dict con campos de la oportunidad
                          (potentialname, related_to, amount, closingdate, etc.).

        Returns:
            ID de la oportunidad creada, o None si falla.
        """
        return await self._create_record("Potentials", potential_data)

    # ──────────────────────────────────────────────
    # HELPERS INTERNOS
    # ──────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),         # Reintenta hasta 3 veces
        wait=wait_exponential(multiplier=1, min=1, max=4),  # Espera: 1s, 2s, 4s
        retry=retry_if_exception_type(httpx.TimeoutException),
        reraise=True,
    )
    async def _post(self, data: dict) -> dict:
        """Ejecuta un POST a webservice.php con reintentos automáticos.

        Args:
            data: Dict con los parámetros a enviar.

        Returns:
            Dict con la respuesta JSON de VTiger.

        Raises:
            httpx.TimeoutException: Si se agotan los reintentos.
        """
        response = await self._http.post(VTIGER_WS, data=data)

        if response.status_code != 200:
            raise VtigerClientError(
                f"Error HTTP {response.status_code}: {response.text[:200]}"
            )

        return response.json()

    async def _create_record(self, module: str, record_data: dict) -> Optional[str]:
        """Crea un registro en cualquier módulo de VTiger.

        Args:
            module: Nombre del módulo (Contacts, Potentials, etc.).
            record_data: Dict con los campos del registro.

        Returns:
            ID del registro creado, o None si falla.
        """
        if not self._session_id:
            await self.login()

        params = {
            "operation": "create",
            "sessionName": self._session_id,
            "elementType": module,
            "element": json.dumps(record_data),
        }

        data = await self._post(params)
        if data.get("success") and data.get("result", {}).get("id"):
            record_id = data["result"]["id"]
            logger.info("%s creado exitosamente: %s", module, record_id)
            return record_id

        logger.warning("Error al crear %s: %s", module, data.get("error"))
        return None

    async def _update_record(self, module: str, record_id: str, record_data: dict) -> bool:
        """Actualiza un registro existente en cualquier módulo.

        Args:
            module: Nombre del módulo.
            record_id: ID del registro a actualizar.
            record_data: Dict con los campos a modificar.

        Returns:
            True si se actualizó, False si falló.
        """
        if not self._session_id:
            await self.login()

        params = {
            "operation": "update",
            "sessionName": self._session_id,
            "elementType": module,
            "element": json.dumps({"id": record_id, **record_data}),
        }

        data = await self._post(params)
        if data.get("success") and data.get("result", {}).get("id"):
            logger.info("%s %s actualizado exitosamente", module, record_id)
            return True

        logger.warning("Error al actualizar %s %s: %s", module, record_id, data.get("error"))
        return False

    async def close(self):
        """Cierra la conexión HTTP explícitamente."""
        await self._http.aclose()
