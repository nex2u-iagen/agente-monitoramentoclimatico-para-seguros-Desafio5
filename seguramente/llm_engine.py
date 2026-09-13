"""Motor LLM multi-provider do SeguraMente.

Suporta OpenAI, OpenAI-compatible (Ollama, vLLM, etc.), Google Gemini
e modo template (offline). O provider é selecionado pela variável de
ambiente LLM_PROVIDER ou pelo parâmetro mode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .llm import (
    SYSTEM_PROMPT,
    LLMGenerationError,
    LLMProvider,
    OpenAICompatibleProvider,
    TemplateProvider,
    validate_message,
)
from .models import GeneratedMessage, InsuredProfile, WeatherEvent, utc_now_iso


@dataclass(frozen=True)
class GeminiProvider(LLMProvider):
    """Provider para Google Gemini via langchain-google-genai."""

    api_key: str
    timeout_seconds: int = 30

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        object.__setattr__(self, "name", "gemini")
        object.__setattr__(
            self,
            "model",
            model or os.getenv("SEGURAMENTE_LLM_MODEL", "gemini-3.6-flash"),
        )
        object.__setattr__(self, "api_key", api_key or os.getenv("GEMINI_API_KEY", ""))
        object.__setattr__(
            self, "timeout_seconds", int(os.getenv("SEGURAMENTE_LLM_TIMEOUT", "30"))
        )

    def generate(self, event: WeatherEvent, profile: InsuredProfile) -> str:
        if not self.api_key:
            raise LLMGenerationError("GEMINI_API_KEY não configurada.")

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise LLMGenerationError(
                "langchain-google-genai não instalado. "
                "Execute: pip install langchain-google-genai"
            ) from exc

        user_payload = {
            "evento": event.event_type,
            "severidade": event.severity,
            "justificativa": event.justification,
            "segurado": profile.name,
            "produto": profile.product,
            "canal": profile.channel,
            "localidade": f"{profile.city}/{profile.state}",
        }

        llm = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=0.2,
            max_tokens=180,
            timeout=self.timeout_seconds,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=str(user_payload)),
        ]

        try:
            response = llm.invoke(messages)
            text = response.content
            if isinstance(text, list):
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in text
                )
            if not text:
                raise LLMGenerationError("O Gemini não retornou conteúdo textual.")
            return str(text).strip()
        except Exception as exc:
            if isinstance(exc, LLMGenerationError):
                raise
            raise LLMGenerationError(f"Falha na geração pelo Gemini: {exc}") from exc


def build_llm_provider(mode: str | None = None) -> LLMProvider:
    """Factory que seleciona o provider baseado no modo ou variável de ambiente.

    Modos suportados:
    - 'openai': API OpenAI padrão
    - 'openai-compatible': Qualquer API compatível com OpenAI
    - 'gemini': Google Gemini
    - 'template': Offline, sem LLM (fallback para testes)
    """
    mode = mode or os.getenv("LLM_PROVIDER", "template")

    if mode == "openai":
        return OpenAICompatibleProvider(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://api.openai.com/v1",
            model=os.getenv("SEGURAMENTE_LLM_MODEL", "gpt-4.1-mini"),
        )
    elif mode == "openai-compatible":
        return OpenAICompatibleProvider(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
            model=os.getenv("SEGURAMENTE_LLM_MODEL"),
        )
    elif mode == "gemini":
        return GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=os.getenv("SEGURAMENTE_LLM_MODEL", "gemini-3.6-flash"),
        )
    else:
        return TemplateProvider()


def generate_message_for_agent(
    event: WeatherEvent,
    profile: InsuredProfile,
    provider: LLMProvider,
) -> GeneratedMessage:
    """Gera, valida e empacota a mensagem preventiva."""
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
