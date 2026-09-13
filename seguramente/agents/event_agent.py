"""Agente de Classificação de Eventos Meteorológicos.

Wrapper que importa a tool de classificação do módulo tools.
"""

from __future__ import annotations

from ..tools.event_tool import classify_weather_event

__all__ = ["classify_weather_event"]
