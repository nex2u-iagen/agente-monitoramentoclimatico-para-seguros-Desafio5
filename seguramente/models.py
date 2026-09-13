"""Modelos de domínio do fluxo SeguraMente."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Severity = Literal["baixa", "moderada", "alta", "critica"]
Channel = Literal["email", "sms", "push"]
DecisionStatus = Literal["elegivel", "bloqueado"]


@dataclass(frozen=True)
class WeatherObservation:
    """Observação normalizada recebida da fonte meteorológica."""

    source: str
    source_url: str
    location: str
    latitude: float
    longitude: float
    observed_at: str
    temperature_c: float | None
    precipitation_mm: float | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    precipitation_probability: int | None
    weather_code: int | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WeatherEvent:
    """Evento meteorológico classificado por regras determinísticas."""

    event_type: str
    severity: Severity
    relevance: bool
    justification: str
    indicators: dict[str, Any]


@dataclass(frozen=True)
class InsuredProfile:
    """Perfil sintético usado no cruzamento de elegibilidade."""

    profile_id: str
    name: str
    city: str
    state: str
    product: str
    channel: Channel
    consent: bool
    contact: str


@dataclass(frozen=True)
class EligibilityDecision:
    """Resultado auditável da aplicação das regras de negócio."""

    profile: InsuredProfile
    status: DecisionStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedMessage:
    """Mensagem preventiva gerada para revisão humana."""

    profile_id: str
    channel: Channel
    recipient: str
    text: str
    provider: str
    model: str
    generated_at: str


@dataclass(frozen=True)
class SimulationRecord:
    """Registro de envio simulado, sem conexão a canais reais."""

    simulation_id: str
    profile_id: str
    channel: Channel
    recipient: str
    text: str
    status: str
    created_at: str


@dataclass
class PipelineResult:
    """Resultado completo da execução ponta a ponta."""

    requested_location: str
    observation: WeatherObservation
    event: WeatherEvent
    decisions: list[EligibilityDecision]
    messages: list[GeneratedMessage]
    simulations: list[SimulationRecord]
    execution_started_at: str
    execution_finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    """Retorna timestamp UTC serializável e sem dependência de sistema local."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
