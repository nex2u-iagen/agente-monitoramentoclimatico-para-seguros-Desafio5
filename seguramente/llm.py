"""Geração de mensagens preventivas com modelo de linguagem.

O modo OpenAI usa uma API compatível com o padrão Chat Completions. O modo
template existe apenas para testes e demonstrações offline, sem substituir a
integração de IA configurada para o MVP.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from .models import GeneratedMessage, InsuredProfile, WeatherEvent, utc_now_iso

PROHIBITED_PATTERNS = (
    r"cobertura garantida",
    r"indeniza(?:ção|remos|rá)",
    r"sinistro aprovado",
    r"senha",
    r"token",
    r"credencial",
    r"código de segurança",
)

SYSTEM_PROMPT = """Você é o gerador de comunicações preventivas da SeguraMente.
Escreva uma única mensagem curta em português do Brasil, clara e não alarmista.
A mensagem deve orientar prevenção diante do evento meteorológico informado.
Nunca prometa cobertura, indenização ou aprovação de sinistro.
Nunca solicite senha, token, documento, código de segurança ou credencial.
Não invente dados meteorológicos, valores, endereços ou contatos.
Retorne somente o texto da mensagem, sem aspas, título ou explicação técnica."""


class LLMGenerationError(RuntimeError):
    """Erro controlado na geração de mensagem."""


@dataclass(frozen=True)
class LLMProvider:
    name: str
    model: str

    def generate(self, event: WeatherEvent, profile: InsuredProfile) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class TemplateProvider(LLMProvider):
    """Provider determinístico usado para testes e execução offline."""

    def __init__(self) -> None:
        object.__setattr__(self, "name", "template-offline")
        object.__setattr__(self, "model", "guardrail-template-v1")

    def generate(self, event: WeatherEvent, profile: InsuredProfile) -> str:
        templates = {
            "chuva_intensa": "Verifique calhas, ralos e áreas externas e acompanhe os comunicados oficiais diante da previsão de chuva intensa em sua região.",
            "granizo": "Mantenha o veículo em local coberto quando possível e acompanhe os comunicados oficiais diante do risco de granizo em sua região.",
            "ventos_fortes": "Recolha objetos soltos em varandas e áreas externas e evite deslocamentos durante a ocorrência de ventos fortes.",
            "alagamento": "Verifique barreiras de entrada, equipamentos próximos ao piso e o plano interno de contingência diante do risco de alagamento.",
        }
        body = templates.get(
            event.event_type,
            "Acompanhe os comunicados oficiais e siga as orientações das autoridades locais.",
        )
        return f"Olá, {profile.name}. {body} Esta é uma orientação preventiva."


@dataclass(frozen=True)
class OpenAICompatibleProvider(LLMProvider):
    """Provider para endpoints OpenAI e compatíveis, sem credencial no código."""

    api_key: str
    base_url: str
    timeout_seconds: int = 30

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        object.__setattr__(self, "name", "openai-compatible")
        object.__setattr__(
            self, "model", model or os.getenv("SEGURAMENTE_LLM_MODEL", "gpt-4.1-mini")
        )
        object.__setattr__(self, "api_key", api_key or os.getenv("OPENAI_API_KEY", ""))
        object.__setattr__(
            self,
            "base_url",
            (
                base_url or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            ).rstrip("/"),
        )
        object.__setattr__(
            self, "timeout_seconds", int(os.getenv("SEGURAMENTE_LLM_TIMEOUT", "30"))
        )

    def generate(self, event: WeatherEvent, profile: InsuredProfile) -> str:
        if not self.api_key:
            raise LLMGenerationError(
                "OPENAI_API_KEY não configurada. Use o modo offline apenas para testes."
            )
        user_payload = {
            "evento": event.event_type,
            "severidade": event.severity,
            "justificativa": event.justification,
            "segurado": profile.name,
            "produto": profile.product,
            "canal": profile.channel,
            "localidade": f"{profile.city}/{profile.state}",
        }
        try:
            request_payload: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": str(user_payload)},
                ],
            }
            if self.model.startswith("gpt-5"):
                # GPT-5 usa max_completion_tokens para deixar orçamento para raciocínio.
                request_payload["max_completion_tokens"] = 180
                request_payload["reasoning"] = {"effort": "minimal"}
            else:
                request_payload["temperature"] = 0.2
                request_payload["max_tokens"] = 180
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            choice = payload["choices"][0]
            message_payload = choice.get("message") or {}
            text = (
                message_payload.get("content")
                or choice.get("text")
                or payload.get("output_text")
            )
            if isinstance(text, list):
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in text
                )
            if not text:
                raise LLMGenerationError(
                    "O modelo não retornou conteúdo textual visível."
                )
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise LLMGenerationError(
                f"Falha na geração pelo modelo de linguagem: {exc}"
            ) from exc
        return str(text).strip()


def validate_message(text: str) -> str:
    """Valida e normaliza a saída do modelo contra guardrails do desafio."""

    normalized = re.sub(r"\s+", " ", text).strip().strip('"')
    if not normalized:
        raise LLMGenerationError("O modelo retornou uma mensagem vazia.")
    for pattern in PROHIBITED_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            raise LLMGenerationError(
                f"A mensagem violou o guardrail de conteúdo: {pattern}"
            )
    if len(normalized) > 500:
        raise LLMGenerationError("A mensagem excede o limite de 500 caracteres do MVP.")
    return normalized


def generate_message(
    event: WeatherEvent, profile: InsuredProfile, provider: LLMProvider
) -> GeneratedMessage:
    """Gera, valida e empacota a mensagem para revisão humana."""

    text = validate_message(provider.generate(event, profile))
    return GeneratedMessage(
        profile_id=profile.profile_id,
        channel=profile.channel,
        recipient=profile.contact,
        text=text,
        provider=provider.name,
        model=provider.model,
        generated_at=utc_now_iso(),
    )


def build_provider(mode: str = "openai") -> LLMProvider:
    """Seleciona provider explicitamente, evitando fallback silencioso."""

    if mode == "template":
        return TemplateProvider()
    if mode in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider()
    raise ValueError("Provider inválido. Use 'openai' ou 'template'.")
