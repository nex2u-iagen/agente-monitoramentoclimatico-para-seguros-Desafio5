"""Webhook FastAPI para disparar o pipeline de agentes via HTTP POST.

Permite que APIs externas (monitoramento meteorológico, sistemas de alerta)
disparem o pipeline multi-agentes do SeguraMente automaticamente.

Uso:
    uvicorn webhook:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /webhook/alert       - Dispara pipeline com localidade
    POST /webhook/fixture     - Dispara pipeline com fixture pré-definida
    GET  /webhook/health      - Health check
    GET  /webhook/runs/{id}   - Consulta logs de uma execução
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fixtures import FIXTURES
from seguramente.agents.base import AgentError
from seguramente.agents.supervisor import (
    run_monitor,
    run_pipeline,
    run_pipeline_from_observation,
)
from seguramente.database import get_database

app = FastAPI(
    title="SeguraMente Webhook",
    description="Endpoint para disparar o pipeline multi-agentes de alertas preventivos",
    version="3.0.0",
)


class AlertRequest(BaseModel):
    """Payload para alerta meteorológico via webhook."""

    location: str = Field(
        ...,
        description="Localidade para busca meteorológica (ex: 'São Paulo')",
        min_length=2,
        max_length=200,
    )
    approved: bool = Field(
        default=False,
        description="Se True, simula envio imediatamente sem espera de aprovação",
    )


class FixtureRequest(BaseModel):
    """Payload para execução com fixture pré-definida."""

    scenario: Literal["chuva_intensa", "granizo", "ventos_fortes", "alagamento"] = (
        Field(
            ...,
            description="Cenário fixture para demonstração",
        )
    )
    approved: bool = Field(
        default=False,
        description="Se True, simula envio imediatamente",
    )


class WebhookResponse(BaseModel):
    """Resposta padrao do webhook."""

    status: str
    run_id: str
    message: str
    agents_executed: list[str]
    event_type: str | None = None
    eligible_count: int = 0
    messages_generated: int = 0
    simulations_count: int = 0


class MonitorResponse(BaseModel):
    """Resposta do monitoramento de cidades."""

    status: str
    run_id: str
    cities_scanned: int
    alerts_triggered: int
    emails_sent: int
    results: list[dict]


@app.get("/webhook/health")
def health_check():
    """Health check do webhook."""
    return {
        "status": "healthy",
        "service": "SeguraMente Webhook",
        "version": "3.0.0",
    }


@app.post("/webhook/alert", response_model=WebhookResponse)
def receive_alert(request: AlertRequest):
    """Recebe um alerta meteorológico e dispara o pipeline de agentes.

    Este endpoint pode ser chamado por APIs de monitoramento meteorológico,
    sistemas de IoT, ou qualquer serviço que detecte condições climáticas
    relevantes para segurados.

    Exemplo de chamada:
        curl -X POST http://localhost:8000/webhook/alert \\
             -H "Content-Type: application/json" \\
             -d '{"location": "São Paulo", "approved": false}'
    """
    try:
        result = run_pipeline(
            location=request.location,
            approved=request.approved,
        )
    except (AgentError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao executar pipeline: {exc}")

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    event_data = result.get("event_data", {})
    return WebhookResponse(
        status="completed",
        run_id=result.get("run_id", ""),
        message=f"Pipeline executado para {request.location}",
        agents_executed=[log["agent_name"] for log in result.get("agent_logs", [])],
        event_type=event_data.get("event_type"),
        eligible_count=sum(
            1
            for d in result.get("eligibility_data", [])
            if d.get("status") == "elegivel"
        ),
        messages_generated=len(result.get("messages_data", [])),
        simulations_count=len(result.get("simulations_data", [])),
    )


@app.post("/webhook/fixture", response_model=WebhookResponse)
def receive_fixture_alert(request: FixtureRequest):
    """Executa o pipeline com um cenário fixture pré-definido.

    Útil para testes e demonstrações sem depender da API meteorológica.

    Exemplo de chamada:
        curl -X POST http://localhost:8000/webhook/fixture \\
             -H "Content-Type: application/json" \\
             -d '{"scenario": "granizo", "approved": true}'
    """
    if request.scenario not in FIXTURES:
        raise HTTPException(
            status_code=400,
            detail=f"Cenário '{request.scenario}' não encontrado. Use: {list(FIXTURES.keys())}",
        )

    try:
        observation = FIXTURES[request.scenario]()
        from dataclasses import asdict

        result = run_pipeline_from_observation(
            observation_dict=asdict(observation),
            approved=request.approved,
        )
    except (AgentError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao executar pipeline: {exc}")

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    event_data = result.get("event_data", {})
    return WebhookResponse(
        status="completed",
        run_id=result.get("run_id", ""),
        message=f"Pipeline executado com fixture {request.scenario}",
        agents_executed=[log["agent_name"] for log in result.get("agent_logs", [])],
        event_type=event_data.get("event_type"),
        eligible_count=sum(
            1
            for d in result.get("eligibility_data", [])
            if d.get("status") == "elegivel"
        ),
        messages_generated=len(result.get("messages_data", [])),
        simulations_count=len(result.get("simulations_data", [])),
    )


@app.get("/webhook/runs/{run_id}")
def get_run_logs(run_id: str):
    """Retorna os logs de execução dos agentes para um run_id específico."""
    db = get_database()
    logs = db.get_agent_logs(run_id)
    if not logs:
        raise HTTPException(
            status_code=404, detail=f"Nenhum log encontrado para run_id: {run_id}"
        )
    return {"run_id": run_id, "logs": logs}


@app.get("/webhook/runs")
def list_runs(limit: int = 20):
    """Lista as últimas execuções registradas."""
    db = get_database()
    logs = db.get_all_agent_logs(limit=limit)

    runs: dict[str, list] = {}
    for log in logs:
        rid = log["run_id"]
        if rid not in runs:
            runs[rid] = []
        runs[rid].append(log)

    return {"runs": runs}


@app.post("/webhook/monitor", response_model=MonitorResponse)
def monitor_cities(approved: bool = False):
    """Monitora todas as cidades dos segurados e dispara alertas.

    Para cada cidade com segurados ativos, consulta o clima,
    classifica o evento e executa o pipeline se relevante.

    Exemplo de chamada:
        curl -X POST "http://localhost:8000/webhook/monitor?approved=true"
    """
    try:
        result = run_monitor(approved=approved)
    except (AgentError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Erro no monitoramento: {exc}")

    return MonitorResponse(
        status="completed",
        run_id=result["run_id"],
        cities_scanned=result["cities_scanned"],
        alerts_triggered=result["alerts_triggered"],
        emails_sent=result["emails_sent"],
        results=result["results"],
    )
