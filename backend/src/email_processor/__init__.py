"""
Procesador de correos electrónicos.

Módulos:
- fetcher: conexión IMAP, parseo, delegación al Orchestrator
- forwarder: reenvío SMTP a departamentos
"""

from src.email_processor.fetcher import sync_emails

__all__ = ["sync_emails"]
