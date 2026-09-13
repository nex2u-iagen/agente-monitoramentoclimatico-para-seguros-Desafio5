"""Testes automatizados do SeguraMente — Versao Multi-Agentes com Tools."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from fixtures import (
    chuva_intensa_sao_paulo,
    granizo_rio_de_janeiro,
    ventos_fortes_salisvador,
)
from scripts.seed_db import seed as seed_database
from seguramente.agents.eligibility_agent import check_insured_eligibility
from seguramente.agents.event_agent import classify_weather_event
from seguramente.agents.notification_agent import (
    simulate_notification,
)
from seguramente.agents.supervisor import run_pipeline_from_observation
from seguramente.agents.weather_agent import (
    fetch_weather_from_observation,
)
from seguramente.database import Database
from seguramente.llm import LLMGenerationError, validate_message
from seguramente.rules import classify_event, evaluate_eligibility

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    """Cria um banco temporario para testes."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        database = Database(db_path)
        seed_database(
            csv_path=ROOT / "data" / "insured_profiles.csv",
            db_path=Path(db_path),
        )
        yield database


@pytest.fixture
def profiles_data(db):
    """Retorna perfis do banco como lista de dicts."""
    return [p.__dict__ for p in db.load_profiles()]


def test_classifica_chuva_intensa_por_limiar():
    event = classify_event(chuva_intensa_sao_paulo())
    assert event.event_type == "chuva_intensa"
    assert event.relevance is True
    assert event.severity == "moderada"


def test_classifica_granizo_por_codigo_wmo():
    event = classify_event(granizo_rio_de_janeiro())
    assert event.event_type == "granizo"
    assert event.severity == "alta"


def test_classifica_vento_forte_por_rajada():
    event = classify_event(ventos_fortes_salisvador())
    assert event.event_type == "ventos_fortes"
    assert event.relevance is True


def test_bloqueia_sem_consentimento_e_produto_incompativel(db):
    event = classify_event(chuva_intensa_sao_paulo())
    profiles = db.load_profiles()
    decisions = evaluate_eligibility(event, profiles)
    by_id = {decision.profile.profile_id: decision for decision in decisions}
    assert by_id["P001"].status == "elegivel"
    assert by_id["P005"].status == "bloqueado"
    assert "consentimento inativo" in by_id["P005"].reasons
    assert by_id["P007"].status == "bloqueado"
    assert "produto sem relacao com o evento" in by_id["P007"].reasons


def test_guardrail_rejeita_promessa_de_cobertura():
    with pytest.raises(LLMGenerationError):
        validate_message("Sua cobertura garantida está confirmada.")


def test_guardrail_aceita_mensagem_preventiva():
    text = validate_message(
        "Olá. Recolha objetos soltos e acompanhe os comunicados oficiais."
    )
    assert text.startswith("Olá")


def test_weather_tool_fetch_from_observation():
    """Testa a tool de weather com fixture."""
    observation = chuva_intensa_sao_paulo()
    obs_json = json.dumps(asdict(observation), default=str)
    result = fetch_weather_from_observation.invoke({"observation_json": obs_json})
    result_dict = json.loads(result)
    assert "location" in result_dict
    assert result_dict["location"] == "São Paulo, São Paulo, Brasil"


def test_event_tool_classifica_corretamente():
    """Testa a tool de classificação de eventos."""
    observation = chuva_intensa_sao_paulo()
    obs_json = json.dumps(asdict(observation), default=str)
    result = classify_weather_event.invoke({"observation_json": obs_json})
    result_dict = json.loads(result)
    assert result_dict["event_type"] == "chuva_intensa"
    assert result_dict["relevance"] is True


def test_eligibility_tool_verifica_perfis(profiles_data):
    """Testa a tool de elegibilidade."""
    observation = chuva_intensa_sao_paulo()
    event = classify_event(observation)
    event_json = json.dumps(asdict(event), default=str)
    profiles_json = json.dumps(profiles_data, default=str)

    result = check_insured_eligibility.invoke(
        {
            "event_json": event_json,
            "profiles_json": profiles_json,
        }
    )
    result_list = json.loads(result)
    assert len(result_list) == 21
    eligible = [d for d in result_list if d["status"] == "elegivel"]
    assert len(eligible) >= 1


def test_notification_tool_simula_envio():
    """Testa a tool de simulação de notificação."""
    msg = {
        "profile_id": "P001",
        "channel": "email",
        "recipient": "test@example.com",
        "text": "Mensagem teste",
    }
    result = simulate_notification.invoke({"message_json": json.dumps(msg)})
    result_dict = json.loads(result)
    assert "simulation_id" in result_dict
    assert "SIMULADO" in result_dict["status"]


def test_fluxo_completo_via_supervisor(profiles_data):
    """Testa o pipeline completo via run_pipeline_from_observation."""
    observation = chuva_intensa_sao_paulo()
    result = run_pipeline_from_observation(
        observation_dict=asdict(observation),
        profiles=profiles_data,
        approved=True,
    )
    assert result.get("event_data") is not None
    assert result["event_data"]["relevance"] is True
    assert len(result.get("messages_data", [])) >= 1
    assert len(result.get("simulations_data", [])) >= 1
    assert len(result.get("agent_logs", [])) >= 4


def test_database_seed_e_carrega(db):
    """Testa se o banco de dados seedou corretamente."""
    profiles = db.load_profiles()
    assert len(profiles) == 21
    ids = {p.profile_id for p in profiles}
    assert "P001" in ids
    assert "P007" in ids


def test_database_salva_simulacao(db):
    """Testa persistência de simulação."""
    from seguramente.models import SimulationRecord, utc_now_iso

    record = SimulationRecord(
        simulation_id="SIM-TEST-001",
        profile_id="P001",
        channel="email",
        recipient="test@example.com",
        text="Mensagem teste",
        status="SIMULADO",
        created_at=utc_now_iso(),
    )
    db.save_simulation(record)
    sims = db.get_simulations()
    assert len(sims) >= 1
    assert sims[0]["simulation_id"] == "SIM-TEST-001"


def test_database_salva_log_agente(db):
    """Testa persistência de log de agente."""
    db.save_agent_log(
        run_id="RUN-TEST-001",
        agent_name="weather_agent",
        action="fetch_weather",
        status="completed",
        input_summary="location=Sao Paulo",
        output_summary="Observação obtida",
    )
    logs = db.get_agent_logs("RUN-TEST-001")
    assert len(logs) == 1
    assert logs[0]["agent_name"] == "weather_agent"
