"""
IMAP Connector — Módulo de conexión y descarga de correos.

¿Qué hace?
1. Se conecta al servidor IMAP (Ionos o Imax)
2. Se autentica con usuario y contraseña
3. Busca correos nuevos (no leídos)
4. Los descarga
5. Los devuelve para que el Parser los procese

Usa la librería estándar `imaplib` — sin dependencias externas.
"""

import imaplib
import email
from email.message import Message
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class IMAPConnector:
    """
    Conexión a un buzón IMAP.

    Esta clase es la puerta de entrada al sistema.
    Cada instancia se conecta a UN buzón (ej: "comercial@beexpand.com" en Ionos).
    Si hay varios buzones, se crea una instancia por cada uno.

    Ejemplo de uso:
        connector = IMAPConnector(
            host="imap.ionos.es",
            port=993,
            username="comercial@beexpand.com",
            password="contraseña"
        )
        connector.connect()
        emails = connector.fetch_unread()
        connector.logout()
    """

    def __init__(
        self,
        host: str,
        port: int = 993,
        username: str = "",
        password: str = "",
        use_ssl: bool = True,
    ):
        """
        Inicializa el conector.

        Parámetros:
            host: Dirección del servidor IMAP (ej: "imap.ionos.es")
            port: Puerto (993 para SSL, 143 para sin SSL)
            username: Email completo (ej: "user@ionos.es")
            password: Contraseña del buzón
            use_ssl: True → conexión segura (recomendado)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.connection: Optional[imaplib.IMAP4] = None

    # ──────────────────────────────────────────────
    # CONEXIÓN Y CIERRE
    # ──────────────────────────────────────────────

    def connect(self) -> bool:
        """
        Establece la conexión con el servidor IMAP.

        ¿Cómo funciona?
        - Si use_ssl=True: usa IMAP4_SSL (puerto 993, cifrado)
        - Si use_ssl=False: usa IMAP4 (puerto 143, sin cifrar)

        Returns:
            True si la conexión fue exitosa, False si falló
        """
        try:
            if self.use_ssl:
                logger.info(f"Conectando a {self.host}:{self.port} (SSL)...")
                self.connection = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                logger.info(f"Conectando a {self.host}:{self.port} (sin SSL)...")
                self.connection = imaplib.IMAP4(self.host, self.port)

            logger.info(f"Autenticando como {self.username}...")
            self.connection.login(self.username, self.password)
            logger.info("✅ Conexión y autenticación exitosas")
            return True

        except imaplib.IMAP4.error as e:
            logger.error(f"❌ Error IMAP: {e}")
            return False
        except ConnectionRefusedError:
            logger.error(f"❌ No se pudo conectar a {self.host}:{self.port}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}")
            return False

    def logout(self):
        """
        Cierra la conexión con el servidor.

        Importante: siempre llamar a logout() cuando se termine
        para no dejar conexiones abiertas.
        """
        if self.connection:
            try:
                self.connection.logout()
                logger.info("🔒 Conexión cerrada")
            except Exception:
                # Si ya está cerrada, no pasa nada
                pass
            finally:
                self.connection = None

    def is_connected(self) -> bool:
        """Verifica si la conexión sigue activa."""
        if not self.connection:
            return False
        try:
            # Un "noop" (no operation) comprueba que la conexión vive
            self.connection.noop()
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────
    # BÚSQUEDA DE CORREOS
    # ──────────────────────────────────────────────

    def _select_mailbox(self, mailbox: str = "INBOX") -> bool:
        """
        Selecciona la carpeta del buzón donde trabajar.

        Por defecto es INBOX (la bandeja de entrada).
        Podría ser "Sent", "Spam", etc.

        Returns:
            True si pudo seleccionar la carpeta
        """
        if not self.connection:
            return False

        try:
            result, data = self.connection.select(mailbox)
            if result == "OK":
                logger.debug(f"📁 Carpeta '{mailbox}' seleccionada")
                return True
            else:
                logger.warning(f"⚠️ No se pudo seleccionar '{mailbox}': {data}")
                return False
        except Exception as e:
            logger.error(f"❌ Error al seleccionar carpeta: {e}")
            return False

    def fetch_unread(self, mailbox: str = "INBOX") -> List[bytes]:
        """
        Busca y descarga todos los correos NO LEÍDOS.

        Este es el método principal que usará el sistema.
        El worker de Celery lo llamará periódicamente.

        ¿Cómo funciona?
        1. Selecciona la carpeta (INBOX)
        2. Busca emails con la bandera "UNSEEN" (no leídos)
        3. Descarga cada uno en formato raw (bytes)
        4. Los devuelve en una lista

        Args:
            mailbox: Carpeta a revisar (por defecto: INBOX)

        Returns:
            Lista de emails en bruto (raw bytes), listos para el Parser
        """
        if not self._select_mailbox(mailbox):
            return []

        try:
            # Buscar emails NO LEÍDOS
            # "UNSEEN" busca los que tienen la bandera "no leído"
            result, data = self.connection.search(None, "UNSEEN")

            if result != "OK":
                logger.warning("⚠️ Error en la búsqueda")
                return []

            # data[0] son los UIDs separados por espacios
            # Ejemplo: b"1 2 3 5 8"
            uids = data[0].split() if data[0] else []

            if not uids:
                logger.info("📭 No hay correos nuevos")
                return []

            logger.info(f"📨 Encontrados {len(uids)} correos nuevos")
            return self._fetch_by_uids(uids)

        except Exception as e:
            logger.error(f"❌ Error al buscar correos: {e}")
            return []

    def fetch_by_date(self, days: int = 1, mailbox: str = "INBOX") -> List[bytes]:
        """
        Busca correos de los últimos N días.

        Útil para la primera sincronización o para reprocesar.

        Args:
            days: Número de días hacia atrás
            mailbox: Carpeta a revisar

        Returns:
            Lista de emails en bruto
        """
        if not self._select_mailbox(mailbox):
            return []

        try:
            from datetime import datetime, timedelta

            # Fecha límite: hace N días
            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

            # Buscar emails DESDE esa fecha
            result, data = self.connection.search(None, f'SINCE {since_date}')

            if result != "OK":
                return []

            uids = data[0].split() if data[0] else []

            if not uids:
                logger.info(f"📭 No hay correos desde {since_date}")
                return []

            logger.info(f"📨 Encontrados {len(uids)} correos desde {since_date}")
            return self._fetch_by_uids(uids)

        except Exception as e:
            logger.error(f"❌ Error al buscar por fecha: {e}")
            return []

    def fetch_all_unseen(self, days: int = 7, mailbox: str = "INBOX") -> List[bytes]:
        """
        Combina: no leídos + últimos N días.

        Así evitamos procesar correos antiguos ya vistos.
        """
        if not self._select_mailbox(mailbox):
            return []

        try:
            from datetime import datetime, timedelta

            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

            # Buscar NO LEÍDOS desde la fecha
            result, data = self.connection.search(None, "UNSEEN", f'SINCE {since_date}')

            if result != "OK":
                return []

            uids = data[0].split() if data[0] else []

            if not uids:
                logger.info(f"📭 No hay correos nuevos desde {since_date}")
                return []

            logger.info(f"📨 Encontrados {len(uids)} correos nuevos (desde {since_date})")
            return self._fetch_by_uids(uids)

        except Exception as e:
            logger.error(f"❌ Error en fetch_all_unseen: {e}")
            return []

    # ──────────────────────────────────────────────
    # DESCARGA DE CORREOS
    # ──────────────────────────────────────────────

    def _fetch_by_uids(self, uids: List[bytes]) -> List[bytes]:
        """
        Descarga el contenido completo de cada email por su UID.

        El UID es como el "DNI" del email dentro del buzón.
        Nunca cambia, incluso si se mueve de carpeta.

        Args:
            uids: Lista de UIDs en bytes (ej: [b"1", b"5", b"8"])

        Returns:
            Lista de emails en raw (bytes)
        """
        if not self.connection:
            return []

        emails_raw = []

        for uid in uids:
            try:
                # RFC822 devuelve el email completo (cabeceras + cuerpo)
                result, data = self.connection.fetch(uid, "(RFC822)")

                if result != "OK":
                    logger.warning(f"⚠️ No se pudo descargar UID {uid}")
                    continue

                # data[0] es una tupla: (b'uid RFC822', bytes_del_email)
                # data[1] es el flag de cierre (b')')
                raw_email = data[0][1]
                emails_raw.append(raw_email)

                logger.debug(f"✅ Descargado email UID {uid.decode()}")

            except Exception as e:
                logger.error(f"❌ Error al descargar UID {uid}: {e}")
                continue

        logger.info(f"📦 Descargados {len(emails_raw)}/{len(uids)} emails")
        return emails_raw

    # ──────────────────────────────────────────────
    # MARCADO DE CORREOS
    # ──────────────────────────────────────────────

    def mark_as_seen(self, uid: bytes) -> bool:
        """
        Marca un email como LEÍDO en el servidor.

        Opcional: podemos decidir si marcar como leído
        inmediatamente o dejarlo como no leído hasta
        que se clasifique.

        Args:
            uid: UID del email a marcar

        Returns:
            True si se marcó correctamente
        """
        if not self.connection:
            return False

        try:
            # +FLAGS añade la bandera "SEEN" (leído)
            result, _ = self.connection.store(uid, "+FLAGS", "\\Seen")
            return result == "OK"
        except Exception as e:
            logger.error(f"❌ Error al marcar UID {uid} como leído: {e}")
            return False

    def move_to_folder(self, uid: bytes, folder: str) -> bool:
        """
        Mueve un email a otra carpeta.

        Útil para clasificar: mover a carpetas "Cliente", "Lead", etc.

        Args:
            uid: UID del email
            folder: Nombre de la carpeta destino

        Returns:
            True si se movió correctamente
        """
        if not self.connection:
            return False

        try:
            # COPY + STORE \\Deleted es el equivalente a "mover" en IMAP
            result, _ = self.connection.copy(uid, folder)
            if result == "OK":
                self.connection.store(uid, "+FLAGS", "\\Deleted")
                self.connection.expunge()
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error al mover UID {uid}: {e}")
            return False
