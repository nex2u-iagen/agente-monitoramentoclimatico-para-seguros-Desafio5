"""Integração com APIs públicas da Open-Meteo.

A implementação não exige chave de API. Em produção, o cliente pode ser
substituído por uma implementação compatível com o mesmo contrato.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .models import WeatherObservation

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE_NAME = "Open-Meteo"


class WeatherAPIError(RuntimeError):
    """Erro controlado de integração meteorológica."""


@dataclass(frozen=True)
class OpenMeteoClient:
    timeout_seconds: int = 15
    session: requests.Session | None = None

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        session = self.session or requests.Session()
        try:
            response = session.get(url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise WeatherAPIError(
                f"Falha de comunicação com a fonte meteorológica: {exc}"
            ) from exc
        except ValueError as exc:
            raise WeatherAPIError(
                "A fonte meteorológica retornou JSON inválido."
            ) from exc
        if not isinstance(payload, dict):
            raise WeatherAPIError(
                "A fonte meteorológica retornou um formato inesperado."
            )
        return payload

    def geocode(self, location: str) -> dict[str, Any]:
        payload = self._get(
            GEOCODING_URL,
            {"name": location, "count": 1, "language": "pt", "format": "json"},
        )
        results = payload.get("results") or []
        if not results:
            raise WeatherAPIError(f"Localidade não encontrada: {location}")
        return results[0]

    def observe(self, location: str) -> WeatherObservation:
        place = self.geocode(location)
        latitude = float(place["latitude"])
        longitude = float(place["longitude"])
        label = ", ".join(
            value
            for value in [place.get("name"), place.get("admin1"), place.get("country")]
            if value
        )
        payload = self._get(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "UTC",
            },
        )
        current = payload.get("current") or {}
        hourly = payload.get("hourly") or {}
        probability_values = hourly.get("precipitation_probability") or []
        probability = int(probability_values[0]) if probability_values else None
        observed_at = str(
            current.get("time") or payload.get("generationtime_ms") or "unknown"
        )
        return WeatherObservation(
            source=SOURCE_NAME,
            source_url=FORECAST_URL,
            location=label or location,
            latitude=latitude,
            longitude=longitude,
            observed_at=observed_at,
            temperature_c=_as_float(current.get("temperature_2m")),
            precipitation_mm=_as_float(current.get("precipitation")),
            wind_speed_kmh=_as_float(current.get("wind_speed_10m")),
            wind_gust_kmh=_as_float(current.get("wind_gusts_10m")),
            precipitation_probability=probability,
            weather_code=_as_int(current.get("weather_code")),
            raw=payload,
        )


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _as_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def search_locations(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Busca localidades na API de geocodificacao da Open-Meteo.

    Args:
        query: Texto de busca (nome da cidade).
        limit: Numero maximo de resultados.

    Returns:
        Lista de dicts com name, admin1, country, latitude, longitude.
    """
    client = OpenMeteoClient()
    try:
        payload = client._get(
            GEOCODING_URL,
            {"name": query, "count": limit, "language": "pt", "format": "json"},
        )
    except WeatherAPIError:
        return []
    results = payload.get("results") or []
    return [
        {
            "name": r.get("name", ""),
            "admin1": r.get("admin1", ""),
            "country": r.get("country", ""),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "label": ", ".join(
                v for v in [r.get("name"), r.get("admin1"), r.get("country")] if v
            ),
        }
        for r in results
    ]
