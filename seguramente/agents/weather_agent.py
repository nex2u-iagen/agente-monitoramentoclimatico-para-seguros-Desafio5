"""Agente de Coleta Meteorológica.

Wrapper que importa as tools de coleta meteorológica do módulo tools.
"""

from __future__ import annotations

from ..tools.weather_tool import fetch_weather_data, fetch_weather_from_observation

__all__ = ["fetch_weather_data", "fetch_weather_from_observation"]
