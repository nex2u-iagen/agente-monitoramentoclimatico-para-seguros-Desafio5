"""Schema de estado compartilhado e tipos auxiliares para os agentes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import MessagesState


class AgentError(RuntimeError):
    """Exceção controlada para erros nos agentes."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AgentLog:
    """Registro de execução de um agente para observabilidade."""

    agent_name: str
    action: str
    status: Literal["started", "completed", "error"]
    input_summary: str | None = None
    output_summary: str | None = None
    started_at: str = ""
    completed_at: str | None = None
    duration_ms: float | None = None


class SeguraMenteState(MessagesState):
    """State compartilhado entre todos os agentes do pipeline.

    Cada agente lê e escreve campos específicos neste state.
    O supervisor coordena a sequência de execução.
    """

    run_id: str = ""
    location: str = ""
    approved: bool = False
    error: str | None = None

    observation_data: dict[str, Any] | None = None
    event_data: dict[str, Any] | None = None
    profiles_data: list[dict[str, Any]] = field(default_factory=list)
    eligibility_data: list[dict[str, Any]] = field(default_factory=list)
    messages_data: list[dict[str, Any]] = field(default_factory=list)
    simulations_data: list[dict[str, Any]] = field(default_factory=list)
    agent_logs: list[dict[str, Any]] = field(default_factory=list)
