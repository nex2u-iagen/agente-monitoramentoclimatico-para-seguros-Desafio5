"""Agente de Geração de Mensagens.

Wrapper que importa a tool de geração de mensagens do módulo tools.
"""

from __future__ import annotations

from ..tools.message_tool import generate_preventive_message

__all__ = ["generate_preventive_message"]
