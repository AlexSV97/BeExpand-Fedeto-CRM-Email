"""
Módulo de notificaciones externas.
Actualmente soporta Telegram para alertas de correos urgentes.
"""

from src.notifiers.telegram import TelegramNotifier

__all__ = ["TelegramNotifier"]
