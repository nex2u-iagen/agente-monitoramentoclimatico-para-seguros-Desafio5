"""Agente de Notificação.

Wrapper que importa as tools de notificação do módulo tools.
"""

from __future__ import annotations

from ..tools.notification_tool import send_email_notification, simulate_notification

__all__ = ["send_email_notification", "simulate_notification"]
