"""Tool de geracao de mensagens preventivas do SeguraMente.

Expoe a geracao de mensagens como uma tool LangGraph.
Tools sao funcoes puras — logging e feito pelo supervisor.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from langchain_core.tools import tool

from ..llm_engine import build_llm_provider, generate_message_for_agent
from ..models import InsuredProfile, WeatherEvent


@tool
def generate_preventive_message(event_json: str, profile_json: str) -> str:
    """Gera uma mensagem preventiva personalizada para um segurado especifico.

    Use esta tool para criar mensagens de orientacao preventiva baseadas no
    evento meteorologico e no perfil do segurado.

    Args:
        event_json: JSON string com os dados do evento classificado.
        profile_json: JSON string com os dados do perfil do segurado.

    Returns:
        JSON string com a mensagem gerada incluindo:
        - profile_id, channel, recipient, text, provider, model, generated_at
    """
    event_dict = json.loads(event_json)
    profile_dict = json.loads(profile_json)

    event = WeatherEvent(**event_dict)
    profile = InsuredProfile(**profile_dict)
    provider = build_llm_provider()

    message = generate_message_for_agent(event, profile, provider)
    return json.dumps(asdict(message), default=str)
