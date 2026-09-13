"""Tools de coleta meteorologica do SeguraMente.

Expoe a API Open-Meteo como tools LangGraph.
Tools sao funcoes puras — logging e feito pelo supervisor.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from langchain_core.tools import tool

from ..weather import OpenMeteoClient


@tool
def fetch_weather_data(location: str) -> str:
    """Busca dados meteorologicos atuais para uma localidade via API Open-Meteo.

    Use esta tool para obter informacoes climaticas em tempo real como
    temperatura, precipitacao, velocidade do vento, rajadas e codigo do tempo.
    A API e gratuita e nao requer chave de autenticacao.

    Args:
        location: Nome da localidade para buscar o clima.

    Returns:
        JSON string com os dados meteorologicos normalizados.
    """
    client = OpenMeteoClient()
    observation = client.observe(location)
    return json.dumps(asdict(observation), default=str)


@tool
def fetch_weather_from_observation(observation_json: str) -> str:
    """Processa uma observacao meteorologica pre-definida (fixture) em formato JSON.

    Use esta tool quando ja possui dados meteorologicos e nao precisa buscar na API.

    Args:
        observation_json: JSON string com os dados da observacao meteorologica.

    Returns:
        JSON string com a observacao processada e validada.
    """
    obs_dict = json.loads(observation_json)
    required_fields = ["source", "location", "latitude", "longitude", "observed_at"]
    for field in required_fields:
        if field not in obs_dict:
            return json.dumps({"error": f"Campo obrigatorio ausente: {field}"})
    return json.dumps(obs_dict, default=str)
