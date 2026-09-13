"""Tool de classificacao de eventos meteorologicos do SeguraMente.

Expoe a classificacao de eventos como uma tool LangGraph.
Tools sao funcoes puras — logging e feito pelo supervisor.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from langchain_core.tools import tool

from ..models import WeatherObservation
from ..rules import classify_event


@tool
def classify_weather_event(observation_json: str) -> str:
    """Classifica o evento meteorologico a partir de dados observados.

    Use esta tool para analisar dados climaticos e determinar o tipo de evento
    relevante (granizo, alagamento, ventos fortes, chuva intensa) com base em
    limiares predefinidos.

    Args:
        observation_json: JSON string com os dados meteorologicos normalizados.

    Returns:
        JSON string com a classificacao do evento incluindo:
        - event_type: tipo do evento classificado
        - severity: severidade (baixa, moderada, alta, critica)
        - relevance: se o evento e relevante para comunicacao preventiva
        - justification: justificativa da classificacao
        - indicators: indicadores meteorologicos utilizados
    """
    obs_dict = json.loads(observation_json)
    observation = WeatherObservation(**obs_dict)
    event = classify_event(observation)
    return json.dumps(asdict(event), default=str)
