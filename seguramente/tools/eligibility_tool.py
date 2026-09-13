"""Tool de verificacao de elegibilidade do SeguraMente.

Expoe a verificacao de elegibilidade como uma tool LangGraph.
Tools sao funcoes puras — logging e feito pelo supervisor.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from langchain_core.tools import tool

from ..models import InsuredProfile, WeatherEvent
from ..rules import evaluate_eligibility


@tool
def check_insured_eligibility(
    event_json: str,
    profiles_json: str,
    event_location: str = "",
) -> str:
    """Verifica quais segurados sao elegiveis para receber alerta preventivo.

    Use esta tool para aplicar as regras de negocio e determinar quais
    segurados devem receber notificacao com base no evento meteorologico.

    Args:
        event_json: JSON string com os dados do evento classificado.
        profiles_json: JSON string com a lista de perfis de segurados.
        event_location: Localidade do evento para filtrar por geolocalizacao.

    Returns:
        JSON string com as decisoes de elegibilidade para cada segurado.
    """
    event_dict = json.loads(event_json)
    profiles_list = json.loads(profiles_json)

    event = WeatherEvent(**event_dict)
    profiles = [InsuredProfile(**p) for p in profiles_list]
    decisions = evaluate_eligibility(event, profiles, event_location=event_location)

    decisions_data = []
    for d in decisions:
        d_dict = asdict(d)
        d_dict["profile"] = asdict(d.profile)
        decisions_data.append(d_dict)

    return json.dumps(decisions_data, default=str)
