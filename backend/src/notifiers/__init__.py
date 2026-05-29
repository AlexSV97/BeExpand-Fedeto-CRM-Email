"""
Módulo de notificaciones externas.

Actualmente soporta WhatsApp Business API para alertas de correos urgentes.
TelegramNotifier se mantiene por compatibilidad pero está deprecado.
"""

from src.notifiers.whatsapp import WhatsAppNotifier

__all__ = ["WhatsAppNotifier"]
