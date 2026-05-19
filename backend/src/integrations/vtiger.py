"""
Cliente REST para VTiger CRM.

Flujo de autenticación:
1. GET  getchallenge → token
2. POST login con MD5(token + accessKey) → sessionName
3. Operaciones CRUD con sessionName

Uso:
    client = VTigerClient()
    await client.login()
    contact_id = await client.create_contact({...})
"""

import hashlib
import json
import logging
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

VTIGER_WS = "/webservice.php"


class VTigerError(Exception):
    """Error de comunicación con VTiger CRM."""


class VTigerAuthError(VTigerError):
    """Error de autenticación con VTiger CRM."""


class VTigerClient:
    """Cliente REST para la API WebService de VTiger."""

    def __init__(self, base_url: str | None = None, access_key: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.vtiger_url).rstrip("/")
        self.access_key = access_key or settings.vtiger_token
        self._session_name: str | None = None
        self._user_id: str | None = None
        self._http = httpx.AsyncClient(timeout=15.0)

    async def _request(
        self,
        method: str,
        operation: str,
        data: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Ejecuta una llamada al webservice de VTiger."""
        url = f"{self.base_url}{VTIGER_WS}"
        if params is None:
            params = {}
        params["operation"] = operation

        try:
            if method == "GET":
                resp = await self._http.get(url, params=params, timeout=15.0)
            else:
                resp = await self._http.post(url, params=params, data=data, timeout=15.0)
            resp.raise_for_status()
            body = resp.json()
        except httpx.TimeoutException:
            raise VTigerError(f"Timeout conectando con VTiger: {self.base_url}")
        except httpx.HTTPStatusError as e:
            raise VTigerError(f"Error HTTP {e.response.status_code} en VTiger: {e.response.text}")
        except json.JSONDecodeError:
            raise VTigerError(f"Respuesta no JSON de VTiger: {resp.text[:200]}")

        if not body.get("success"):
            error_detail = body.get("error", {}).get("message", body)
            raise VTigerError(f"VTiger error: {error_detail}")

        return body["result"]

    async def login(self) -> str:
        """
        Autentica contra VTiger: getchallenge + login.

        Returns:
            sessionName para operaciones posteriores.

        Raises:
            VTigerAuthError si las credenciales son inválidas.
        """
        if not self.base_url:
            raise VTigerAuthError("VTiger URL no configurada (vtiger_url)")
        if not self.access_key:
            raise VTigerAuthError("VTiger access key no configurada (vtiger_token)")

        # El username VTiger normalmente es el email admin
        # Se puede configurar explícitamente con vtiger_username
        # o se toma de imap_email como fallback
        settings = get_settings()
        username = settings.vtiger_username or settings.imap_email
        if not username:
            raise VTigerAuthError(
                "No se puede determinar el usuario VTiger. "
                "Configura vtiger_username en .env"
            )

        # Paso 1: getchallenge
        try:
            challenge = await self._request(
                "GET", "getchallenge", params={"username": username}
            )
        except VTigerError as e:
            raise VTigerAuthError(f"Error en getchallenge: {e}")

        token = challenge.get("token")
        if not token:
            raise VTigerAuthError("No se recibió token en getchallenge")

        # Paso 2: login con MD5(token + accessKey)
        access_key_hash = hashlib.md5(
            f"{token}{self.access_key}".encode("utf-8")
        ).hexdigest()

        try:
            login_result = await self._request(
                "POST",
                "login",
                data={"username": username, "accessKey": access_key_hash},
            )
        except VTigerError as e:
            raise VTigerAuthError(f"Error en login: {e}")

        self._session_name = login_result.get("sessionName")
        self._user_id = login_result.get("userId")

        if not self._session_name:
            raise VTigerAuthError("No se recibió sessionName en login")

        logger.info(
            "Conectado a VTiger %s (userId: %s)", self.base_url, self._user_id
        )
        return self._session_name

    @property
    def is_connected(self) -> bool:
        return self._session_name is not None

    async def ensure_session(self) -> str:
        """Retorna sessionName, haciendo login si es necesario."""
        if not self._session_name:
            return await self.login()
        return self._session_name

    # ── Contacts ──

    async def find_contact_by_email(self, email: str) -> dict | None:
        """
        Busca un contacto en VTiger por email.

        Returns:
            Dict con datos del contacto, o None si no existe.
        """
        session = await self.ensure_session()
        # NOTA: VTiger 7.2 REQUIERE punto y coma al final
        query = f"SELECT id, firstname, lastname, email, phone FROM Contacts WHERE email = '{email}';"

        try:
            result = await self._request(
                "GET",
                "query",
                params={"sessionName": session, "query": query},
            )
        except VTigerError:
            return None

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    async def create_contact(self, contact_data: dict) -> str:
        """
        Crea un contacto en VTiger.

        Args:
            contact_data: Diccionario con campos del contacto.
                Mínimo requerido: {"lastname": "..."}

        Returns:
            ID de VTiger del contacto creado (ej: "4x1001").
        """
        session = await self.ensure_session()

        # Asegurar campos obligatorios
        if "lastname" not in contact_data or not contact_data["lastname"]:
            raise VTigerError("lastname es obligatorio para crear contacto en VTiger")

        # Asignar al usuario por defecto si no se especifica
        if "assigned_user_id" not in contact_data and self._user_id:
            contact_data["assigned_user_id"] = self._user_id

        result = await self._request(
            "POST",
            "create",
            data={
                "sessionName": session,
                "elementType": "Contacts",
                "element": json.dumps(contact_data, ensure_ascii=False),
            },
        )
        contact_id = result.get("id", "")
        logger.info("Contacto creado en VTiger: %s (%s)", contact_id, contact_data.get("email"))
        return contact_id

    async def update_contact(self, contact_id: str, contact_data: dict) -> str:
        """
        Actualiza un contacto existente en VTiger.

        Args:
            contact_id: ID de VTiger (ej: "4x1001").
            contact_data: Campos a actualizar. Debe incluir "id".

        Returns:
            ID de VTiger del contacto actualizado.
        """
        session = await self.ensure_session()
        contact_data["id"] = contact_id
        if "assigned_user_id" not in contact_data and self._user_id:
            contact_data["assigned_user_id"] = self._user_id

        result = await self._request(
            "POST",
            "update",
            data={
                "sessionName": session,
                "elementType": "Contacts",
                "element": json.dumps(contact_data, ensure_ascii=False),
            },
        )
        updated_id = result.get("id", contact_id)
        logger.info("Contacto actualizado en VTiger: %s", updated_id)
        return updated_id

    async def delete_contact(self, contact_id: str) -> None:
        """
        Elimina un contacto en VTiger por su ID.

        Args:
            contact_id: ID de VTiger (ej: "12x15").
        """
        session = await self.ensure_session()
        try:
            await self._request(
                "POST", "delete",
                data={"sessionName": session, "id": contact_id},
            )
            logger.info("Contacto eliminado en VTiger: %s", contact_id)
        except VTigerError as e:
            logger.warning("Error al eliminar contacto %s: %s", contact_id, e)

    async def upsert_contact(self, contact_data: dict, lookup_email: str | None = None) -> str:
        """
        Crea o actualiza un contacto. Si existe por email, actualiza; si no, crea.

        Args:
            contact_data: Datos del contacto.
            lookup_email: Email para búsqueda. Por defecto usa contact_data["email"].

        Returns:
            ID de VTiger.
        """
        email = lookup_email or contact_data.get("email")
        if email:
            existing = await self.find_contact_by_email(email)
            if existing:
                vtiger_id = existing["id"]
                try:
                    return await self.update_contact(vtiger_id, contact_data)
                except VTigerError:
                    # Workaround: VTiger 7.2.0 bug — update falla con
                    # "Database error" incluso en contactos válidos.
                    # Eliminamos y recreamos como fallback.
                    logger.warning(
                        "Update falló para %s, haciendo delete+create", email
                    )
                    await self.delete_contact(vtiger_id)
                    return await self.create_contact(contact_data)

        return await self.create_contact(contact_data)

    async def close(self):
        """Cierra la sesión HTTP."""
        await self._http.aclose()
