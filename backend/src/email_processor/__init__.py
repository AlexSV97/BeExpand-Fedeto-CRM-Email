"""
Procesador de correos electrónicos.

Módulos:
- fetcher: conexión IMAP, parseo, clasificación por reglas, persistencia
"""

from src.email_processor.fetcher import sync_emails

__all__ = ["sync_emails"]
