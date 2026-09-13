"""Regras deterministicas de eventos e elegibilidade."""

from __future__ import annotations

from collections.abc import Iterable

from .models import (
    EligibilityDecision,
    InsuredProfile,
    WeatherEvent,
    WeatherObservation,
)

PRODUCTS_BY_EVENT: dict[str, set[str]] = {
    "chuva_intensa": {"residencial", "empresarial"},
    "granizo": {"automovel", "residencial"},
    "ventos_fortes": {"residencial", "empresarial", "automovel"},
    "alagamento": {"residencial", "empresarial"},
}

CHANNELS: set[str] = {"email", "sms", "push"}


def _location_matches(event_location: str, profile_city: str) -> bool:
    """Verifica se a cidade do perfil esta na localidade do evento.

    Compara case-insensitive. Se event_location for vazio, aceita todos.
    """
    if not event_location:
        return True
    return profile_city.lower() in event_location.lower()


def classify_event(observation: WeatherObservation) -> WeatherEvent:
    """Classifica a observacao com limiares documentados e reproduziveis.

    Limiares do MVP:
    - granizo: codigo WMO 96 ou 99;
    - alagamento: precipitacao atual >= 30 mm;
    - chuva intensa: precipitacao atual >= 10 mm ou probabilidade >= 70%;
    - ventos fortes: rajada >= 60 km/h.
    """

    rain = observation.precipitation_mm or 0.0
    gust = observation.wind_gust_kmh or 0.0
    probability = observation.precipitation_probability or 0
    code = observation.weather_code
    indicators = {
        "precipitation_mm": rain,
        "precipitation_probability": probability,
        "wind_gust_kmh": gust,
        "weather_code": code,
    }

    if code in {96, 99}:
        return WeatherEvent(
            event_type="granizo",
            severity="alta",
            relevance=True,
            justification="Codigo meteorologico WMO 96/99 indica trovoada com granizo.",
            indicators=indicators,
        )
    if rain >= 30:
        return WeatherEvent(
            event_type="alagamento",
            severity="critica",
            relevance=True,
            justification="Precipitacao atual igual ou superior a 30 mm indica risco elevado de alagamento.",
            indicators=indicators,
        )
    if gust >= 60:
        return WeatherEvent(
            event_type="ventos_fortes",
            severity="alta",
            relevance=True,
            justification="Rajada de vento igual ou superior a 60 km/h supera o limiar preventivo.",
            indicators=indicators,
        )
    if rain >= 10 or probability >= 70:
        return WeatherEvent(
            event_type="chuva_intensa",
            severity="moderada",
            relevance=True,
            justification="Precipitacao atual igual ou superior a 10 mm ou probabilidade igual ou superior a 70%.",
            indicators=indicators,
        )
    return WeatherEvent(
        event_type="sem_evento_relevante",
        severity="baixa",
        relevance=False,
        justification="Nenhum indicador ultrapassou os limiares de comunicacao preventiva.",
        indicators=indicators,
    )


def evaluate_eligibility(
    event: WeatherEvent,
    profiles: Iterable[InsuredProfile],
    event_location: str = "",
) -> list[EligibilityDecision]:
    """Aplica regras explicaveis e retorna aprovados e bloqueados.

    Args:
        event: Evento meteorologico classificado.
        profiles: Lista de perfis de segurados.
        event_location: Localidade do evento para filtrar por geolocalizacao.
    """

    decisions: list[EligibilityDecision] = []
    allowed_products = PRODUCTS_BY_EVENT.get(event.event_type, set())
    for profile in profiles:
        reasons: list[str] = []
        if not event.relevance:
            reasons.append("evento abaixo do limiar de relevancia")
        if not profile.consent:
            reasons.append("consentimento inativo")
        if profile.channel not in CHANNELS:
            reasons.append("canal nao suportado")
        if profile.product not in allowed_products:
            reasons.append("produto sem relacao com o evento")
        if not profile.contact.strip():
            reasons.append("contato ausente para o canal selecionado")
        if event_location and not _location_matches(event_location, profile.city):
            reasons.append("localidade fora da area afetada")
        if not reasons:
            reasons.append("localidade, produto, consentimento e canal compativeis")
            status = "elegivel"
        else:
            status = "bloqueado"
        decisions.append(
            EligibilityDecision(profile=profile, status=status, reasons=tuple(reasons))
        )
    return decisions
