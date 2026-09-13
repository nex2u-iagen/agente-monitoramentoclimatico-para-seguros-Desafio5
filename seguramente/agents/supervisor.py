"""Supervisor Orquestrador do SeguraMente.

Coordena a execucao sequencial dos agentes especializados.
Cada agente possui tools que podem ser invocadas.
Logging detalhado e feito pelo supervisor (tools sao funcoes puras).

Fluxo: Weather -> Event -> Eligibility -> Message -> Notification
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from ..database import get_database
from ..models import utc_now_iso
from .base import AgentError, SeguraMenteState
from .eligibility_agent import check_insured_eligibility
from .event_agent import classify_weather_event
from .message_agent import generate_preventive_message
from .notification_agent import send_email_notification, simulate_notification
from .weather_agent import fetch_weather_data, fetch_weather_from_observation


def _check_error(state: SeguraMenteState) -> Literal["__end__", "weather_agent"]:
    if state.get("error"):
        return END
    return "weather_agent"


def _after_weather(state: SeguraMenteState) -> Literal["__end__", "event_agent"]:
    if state.get("error") or not state.get("observation_data"):
        return END
    return "event_agent"


def _after_event(state: SeguraMenteState) -> Literal["__end__", "eligibility_agent"]:
    if state.get("error") or not state.get("event_data"):
        return END
    return "eligibility_agent"


def _after_eligibility(state: SeguraMenteState) -> Literal["__end__", "message_agent"]:
    if state.get("error"):
        return END
    if not state.get("eligibility_data"):
        return END
    return "message_agent"


def _after_message(state: SeguraMenteState) -> Literal["__end__", "notification_agent"]:
    if state.get("error"):
        return END
    return "notification_agent"


def _log_agent(
    db: Any,
    run_id: str,
    agent_name: str,
    action: str,
    status: str,
    input_summary: str = "",
    output_summary: str = "",
    started_at: str = "",
    completed_at: str = "",
    duration_ms: float | None = None,
    raw_input: Any = None,
    raw_output: Any = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    location: str | None = None,
) -> None:
    """Salva log detalhado do agente no banco."""
    db.save_agent_log(
        run_id=run_id,
        agent_name=agent_name,
        action=action,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


def _run_weather_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Executa o agente meteorologico usando a tool."""
    started = time.time()
    run_id = state.get("run_id", utc_now_iso())
    db = get_database()
    location = state.get("location", "")
    use_fixture = state.get("use_fixture", False)
    started_at = utc_now_iso()

    mode = "fixture" if use_fixture else "api"
    _log_agent(
        db,
        run_id,
        "weather_agent",
        "fetch_weather",
        "started",
        input_summary=f"location={location}, mode={mode}",
        started_at=started_at,
    )

    try:
        if use_fixture and state.get("observation_data"):
            obs_json = json.dumps(state["observation_data"], default=str)
            result = fetch_weather_from_observation.invoke(
                {"observation_json": obs_json}
            )
        else:
            result = fetch_weather_data.invoke({"location": location})

        result_dict = json.loads(result)
        elapsed_ms = (time.time() - started) * 1000

        if "error" in result_dict:
            raise AgentError(result_dict["error"])

        _log_agent(
            db,
            run_id,
            "weather_agent",
            "fetch_weather",
            "completed",
            input_summary=f"location={location}, mode={mode}",
            output_summary=(
                f"localidade={result_dict.get('location', 'N/A')}, "
                f"precip={result_dict.get('precipitation_mm')}mm, "
                f"gust={result_dict.get('wind_gust_kmh')}km/h, "
                f"code={result_dict.get('weather_code')}, "
                f"temp={result_dict.get('temperature_c')}C"
            ),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
            raw_input={"location": location, "mode": mode},
            raw_output=result_dict,
            location=result_dict.get("location"),
        )

        log_entry = {
            "agent_name": "weather_agent",
            "action": "fetch_weather",
            "status": "completed",
            "input_summary": f"location={location}, mode={mode}",
            "output_summary": (
                f"localidade={result_dict.get('location', 'N/A')}, "
                f"precip={result_dict.get('precipitation_mm')}mm, "
                f"gust={result_dict.get('wind_gust_kmh')}km/h"
            ),
            "started_at": started_at,
            "completed_at": utc_now_iso(),
            "duration_ms": elapsed_ms,
        }
        logs = state.get("agent_logs", []) + [log_entry]

        return {
            "observation_data": result_dict,
            "agent_logs": logs,
        }

    except (AgentError, json.JSONDecodeError, ValueError) as exc:
        elapsed_ms = (time.time() - started) * 1000
        _log_agent(
            db,
            run_id,
            "weather_agent",
            "fetch_weather",
            "error",
            input_summary=f"location={location}, mode={mode}",
            output_summary=str(exc),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
        )
        return {
            "error": str(exc),
            "agent_logs": state.get("agent_logs", [])
            + [
                {
                    "agent_name": "weather_agent",
                    "action": "fetch_weather",
                    "status": "error",
                    "output_summary": str(exc),
                    "started_at": started_at,
                    "completed_at": utc_now_iso(),
                    "duration_ms": elapsed_ms,
                }
            ],
        }


def _run_event_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Executa o agente de classificacao usando a tool."""
    started = time.time()
    run_id = state.get("run_id", utc_now_iso())
    db = get_database()
    obs_data = state.get("observation_data")
    started_at = utc_now_iso()

    if not obs_data:
        return {"error": "Dados meteorologicos nao disponiveis."}

    _log_agent(
        db,
        run_id,
        "event_agent",
        "classify_event",
        "started",
        input_summary=(
            f"code={obs_data.get('weather_code')}, "
            f"precip={obs_data.get('precipitation_mm')}mm, "
            f"gust={obs_data.get('wind_gust_kmh')}km/h, "
            f"prob={obs_data.get('precipitation_probability')}%"
        ),
        started_at=started_at,
    )

    try:
        obs_json = json.dumps(obs_data, default=str)
        result = classify_weather_event.invoke({"observation_json": obs_json})
        result_dict = json.loads(result)
        elapsed_ms = (time.time() - started) * 1000

        if "error" in result_dict:
            raise AgentError(result_dict["error"])

        _log_agent(
            db,
            run_id,
            "event_agent",
            "classify_event",
            "completed",
            input_summary=(
                f"code={obs_data.get('weather_code')}, "
                f"precip={obs_data.get('precipitation_mm')}mm, "
                f"gust={obs_data.get('wind_gust_kmh')}km/h"
            ),
            output_summary=(
                f"tipo={result_dict.get('event_type')}, "
                f"severidade={result_dict.get('severity')}, "
                f"relevante={result_dict.get('relevance')}, "
                f"regra={result_dict.get('justification', '')[:80]}"
            ),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
            raw_input=obs_data,
            raw_output=result_dict,
        )

        log_entry = {
            "agent_name": "event_agent",
            "action": "classify_event",
            "status": "completed",
            "input_summary": f"code={obs_data.get('weather_code')}",
            "output_summary": f"tipo={result_dict.get('event_type')}, severidade={result_dict.get('severity')}",
            "started_at": started_at,
            "completed_at": utc_now_iso(),
            "duration_ms": elapsed_ms,
        }
        logs = state.get("agent_logs", []) + [log_entry]

        return {"event_data": result_dict, "agent_logs": logs}

    except (AgentError, json.JSONDecodeError, ValueError) as exc:
        elapsed_ms = (time.time() - started) * 1000
        _log_agent(
            db,
            run_id,
            "event_agent",
            "classify_event",
            "error",
            output_summary=str(exc),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
        )
        return {
            "error": str(exc),
            "agent_logs": state.get("agent_logs", [])
            + [
                {
                    "agent_name": "event_agent",
                    "action": "classify_event",
                    "status": "error",
                    "output_summary": str(exc),
                    "started_at": started_at,
                    "completed_at": utc_now_iso(),
                    "duration_ms": elapsed_ms,
                }
            ],
        }


def _run_eligibility_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Executa o agente de elegibilidade usando a tool."""
    started = time.time()
    run_id = state.get("run_id", utc_now_iso())
    db = get_database()
    event_data = state.get("event_data")
    profiles_data = state.get("profiles_data", [])
    obs_data = state.get("observation_data", {})
    event_location = obs_data.get("location", "")
    started_at = utc_now_iso()

    if not event_data:
        return {"error": "Dados do evento nao disponiveis."}

    _log_agent(
        db,
        run_id,
        "eligibility_agent",
        "evaluate_eligibility",
        "started",
        input_summary=(
            f"evento={event_data.get('event_type')}, "
            f"perfis={len(profiles_data)}, "
            f"cidade={event_location}"
        ),
        started_at=started_at,
    )

    try:
        event_json = json.dumps(event_data, default=str)
        profiles_json = json.dumps(profiles_data, default=str)
        result = check_insured_eligibility.invoke(
            {
                "event_json": event_json,
                "profiles_json": profiles_json,
                "event_location": event_location,
            }
        )
        result_list = json.loads(result)
        elapsed_ms = (time.time() - started) * 1000

        if isinstance(result_list, dict) and "error" in result_list:
            raise AgentError(result_list["error"])

        eligible = [d for d in result_list if d.get("status") == "elegivel"]
        blocked = [d for d in result_list if d.get("status") == "bloqueado"]

        eligible_ids = [d["profile"]["profile_id"] for d in eligible]
        blocked_summary = {}
        for d in blocked:
            for r in d.get("reasons", []):
                blocked_summary[r] = blocked_summary.get(r, 0) + 1

        _log_agent(
            db,
            run_id,
            "eligibility_agent",
            "evaluate_eligibility",
            "completed",
            input_summary=(
                f"evento={event_data.get('event_type')}, "
                f"perfis={len(profiles_data)}, "
                f"cidade={event_location}"
            ),
            output_summary=(
                f"{len(eligible)} elegiveis de {len(result_list)}: "
                f"{','.join(eligible_ids[:8])}{'...' if len(eligible_ids) > 8 else ''}; "
                f"{len(blocked)} bloqueados: "
                + ", ".join(f"{k}={v}" for k, v in blocked_summary.items())
            ),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
            raw_input={
                "event": event_data,
                "profiles_count": len(profiles_data),
                "location": event_location,
            },
            raw_output=result_list,
        )

        log_entry = {
            "agent_name": "eligibility_agent",
            "action": "evaluate_eligibility",
            "status": "completed",
            "input_summary": f"evento={event_data.get('event_type')}, perfis={len(profiles_data)}",
            "output_summary": f"{len(eligible)} elegiveis de {len(result_list)}",
            "started_at": started_at,
            "completed_at": utc_now_iso(),
            "duration_ms": elapsed_ms,
        }
        logs = state.get("agent_logs", []) + [log_entry]

        return {"eligibility_data": result_list, "agent_logs": logs}

    except (AgentError, json.JSONDecodeError, ValueError) as exc:
        elapsed_ms = (time.time() - started) * 1000
        _log_agent(
            db,
            run_id,
            "eligibility_agent",
            "evaluate_eligibility",
            "error",
            output_summary=str(exc),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
        )
        return {
            "error": str(exc),
            "agent_logs": state.get("agent_logs", [])
            + [
                {
                    "agent_name": "eligibility_agent",
                    "action": "evaluate_eligibility",
                    "status": "error",
                    "output_summary": str(exc),
                    "started_at": started_at,
                    "completed_at": utc_now_iso(),
                    "duration_ms": elapsed_ms,
                }
            ],
        }


def _run_message_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Executa o agente de geracao de mensagens usando a tool."""
    started = time.time()
    run_id = state.get("run_id", utc_now_iso())
    db = get_database()
    event_data = state.get("event_data")
    eligibility_data = state.get("eligibility_data", [])
    started_at = utc_now_iso()

    if not event_data:
        return {"error": "Dados do evento nao disponiveis."}

    eligible_profiles = [d for d in eligibility_data if d.get("status") == "elegivel"]

    _log_agent(
        db,
        run_id,
        "message_agent",
        "generate_message",
        "started",
        input_summary=f"elegiveis={len(eligible_profiles)}, evento={event_data.get('event_type')}",
        started_at=started_at,
    )

    try:
        event_json = json.dumps(event_data, default=str)
        messages = []
        per_profile = []

        for decision_data in eligible_profiles:
            profile_json = json.dumps(decision_data.get("profile", {}), default=str)
            result = generate_preventive_message.invoke(
                {"event_json": event_json, "profile_json": profile_json}
            )
            msg_dict = json.loads(result)
            pid = decision_data.get("profile", {}).get("profile_id", "?")

            if "error" in msg_dict:
                per_profile.append(f"{pid}=erro({msg_dict['error'][:30]})")
            else:
                messages.append(msg_dict)
                per_profile.append(f"{pid}=ok")

        elapsed_ms = (time.time() - started) * 1000

        _log_agent(
            db,
            run_id,
            "message_agent",
            "generate_message",
            "completed",
            input_summary=f"elegiveis={len(eligible_profiles)}, evento={event_data.get('event_type')}",
            output_summary=f"{len(messages)} mensagens geradas: {'; '.join(per_profile)}",
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
            raw_input={
                "event_type": event_data.get("event_type"),
                "eligible_count": len(eligible_profiles),
            },
            raw_output={"messages_count": len(messages), "per_profile": per_profile},
        )

        log_entry = {
            "agent_name": "message_agent",
            "action": "generate_message",
            "status": "completed",
            "input_summary": f"elegiveis={len(eligible_profiles)}",
            "output_summary": f"{len(messages)} mensagens geradas",
            "started_at": started_at,
            "completed_at": utc_now_iso(),
            "duration_ms": elapsed_ms,
        }
        logs = state.get("agent_logs", []) + [log_entry]

        return {"messages_data": messages, "agent_logs": logs}

    except (AgentError, json.JSONDecodeError, ValueError) as exc:
        elapsed_ms = (time.time() - started) * 1000
        _log_agent(
            db,
            run_id,
            "message_agent",
            "generate_message",
            "error",
            output_summary=str(exc),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
        )
        return {
            "error": str(exc),
            "agent_logs": state.get("agent_logs", [])
            + [
                {
                    "agent_name": "message_agent",
                    "action": "generate_message",
                    "status": "error",
                    "output_summary": str(exc),
                    "started_at": started_at,
                    "completed_at": utc_now_iso(),
                    "duration_ms": elapsed_ms,
                }
            ],
        }


def _run_notification_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Executa o agente de notificacao usando a tool."""
    started = time.time()
    run_id = state.get("run_id", utc_now_iso())
    db = get_database()
    messages_data = state.get("messages_data", [])
    approved = state.get("approved", False)
    started_at = utc_now_iso()

    _log_agent(
        db,
        run_id,
        "notification_agent",
        "send_notification",
        "started",
        input_summary=f"mensagens={len(messages_data)}, approved={approved}",
        started_at=started_at,
    )

    try:
        simulations = []
        per_profile = []

        for msg_data in messages_data:
            msg_json = json.dumps(msg_data, default=str)
            pid = msg_data.get("profile_id", "?")
            recipient = msg_data.get("recipient", "?")

            if approved:
                result = send_email_notification.invoke({"message_json": msg_json})
            else:
                result = simulate_notification.invoke({"message_json": msg_json})

            sim_dict = json.loads(result)
            status = sim_dict.get("status", "ERRO")

            if "error" in sim_dict:
                per_profile.append(f"{pid}=erro({sim_dict['error'][:30]})")
            else:
                simulations.append(sim_dict)
                if "ENVIADO" in status:
                    per_profile.append(f"{pid}=ENVIADO({recipient})")
                elif "SIMULADO" in status:
                    per_profile.append(f"{pid}=SIMULADO({recipient})")
                else:
                    per_profile.append(f"{pid}=FALLBACK({recipient})")

        elapsed_ms = (time.time() - started) * 1000
        mode = "REAL" if approved else "SIMULADO"

        _log_agent(
            db,
            run_id,
            "notification_agent",
            "send_notification",
            "completed",
            input_summary=f"mensagens={len(messages_data)}, approved={approved}",
            output_summary=f"{len(simulations)} notificacoes ({mode}): {'; '.join(per_profile)}",
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
            raw_input={"messages_count": len(messages_data), "approved": approved},
            raw_output={
                "simulations_count": len(simulations),
                "per_profile": per_profile,
            },
        )

        log_entry = {
            "agent_name": "notification_agent",
            "action": "send_notification",
            "status": "completed",
            "input_summary": f"mensagens={len(messages_data)}, approved={approved}",
            "output_summary": f"{len(simulations)} notificacoes ({mode})",
            "started_at": started_at,
            "completed_at": utc_now_iso(),
            "duration_ms": elapsed_ms,
        }
        logs = state.get("agent_logs", []) + [log_entry]

        return {"simulations_data": simulations, "agent_logs": logs}

    except (AgentError, json.JSONDecodeError, ValueError) as exc:
        elapsed_ms = (time.time() - started) * 1000
        _log_agent(
            db,
            run_id,
            "notification_agent",
            "send_notification",
            "error",
            output_summary=str(exc),
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=elapsed_ms,
        )
        return {
            "error": str(exc),
            "agent_logs": state.get("agent_logs", [])
            + [
                {
                    "agent_name": "notification_agent",
                    "action": "send_notification",
                    "status": "error",
                    "output_summary": str(exc),
                    "started_at": started_at,
                    "completed_at": utc_now_iso(),
                    "duration_ms": elapsed_ms,
                }
            ],
        }


def create_supervisor_graph() -> StateGraph:
    """Cria o grafo de orquestracao do supervisor."""
    graph = StateGraph(SeguraMenteState)
    graph.add_node("weather_agent", _run_weather_agent)
    graph.add_node("event_agent", _run_event_agent)
    graph.add_node("eligibility_agent", _run_eligibility_agent)
    graph.add_node("message_agent", _run_message_agent)
    graph.add_node("notification_agent", _run_notification_agent)
    graph.set_entry_point("weather_agent")
    graph.add_conditional_edges(
        "weather_agent", _after_weather, {"event_agent": "event_agent", END: END}
    )
    graph.add_conditional_edges(
        "event_agent",
        _after_event,
        {"eligibility_agent": "eligibility_agent", END: END},
    )
    graph.add_conditional_edges(
        "eligibility_agent",
        _after_eligibility,
        {"message_agent": "message_agent", END: END},
    )
    graph.add_conditional_edges(
        "message_agent",
        _after_message,
        {"notification_agent": "notification_agent", END: END},
    )
    graph.add_edge("notification_agent", END)
    return graph


def run_pipeline(
    location: str,
    profiles: list[dict[str, Any]] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Executa o pipeline completo de agentes.

    Args:
        location: Localidade para busca meteorologica.
        profiles: Lista de perfis de segurados (dicts).
        approved: Se True, envia email real. Se False, apenas simula.

    Returns:
        Dict com todos os dados do pipeline e logs.
    """
    run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
    db = get_database()

    if profiles is None:
        profiles_data = [p.__dict__ for p in db.load_profiles()]
    else:
        profiles_data = profiles

    initial_state: dict[str, Any] = {
        "run_id": run_id,
        "location": location,
        "approved": approved,
        "use_fixture": False,
        "profiles_data": profiles_data,
        "observation_data": None,
        "event_data": None,
        "eligibility_data": [],
        "messages_data": [],
        "simulations_data": [],
        "agent_logs": [],
        "error": None,
    }

    graph = create_supervisor_graph()
    compiled = graph.compile()
    result = compiled.invoke(initial_state)

    return dict(result)


def run_pipeline_from_observation(
    observation_dict: dict[str, Any],
    profiles: list[dict[str, Any]] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Executa o pipeline a partir de uma observacao pre-definida (fixture)."""
    run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
    db = get_database()

    if profiles is None:
        profiles_data = [p.__dict__ for p in db.load_profiles()]
    else:
        profiles_data = profiles

    initial_state: dict[str, Any] = {
        "run_id": run_id,
        "location": observation_dict.get("location", ""),
        "approved": approved,
        "use_fixture": True,
        "profiles_data": profiles_data,
        "observation_data": observation_dict,
        "event_data": None,
        "eligibility_data": [],
        "messages_data": [],
        "simulations_data": [],
        "agent_logs": [],
        "error": None,
    }

    state = _run_weather_agent(initial_state)
    if state.get("error"):
        return state
    initial_state.update(state)

    state = _run_event_agent(initial_state)
    if state.get("error"):
        return state
    initial_state.update(state)

    state = _run_eligibility_agent(initial_state)
    if state.get("error"):
        return state
    initial_state.update(state)

    state = _run_message_agent(initial_state)
    if state.get("error"):
        return state
    initial_state.update(state)

    state = _run_notification_agent(initial_state)
    if state.get("error"):
        return state
    initial_state.update(state)

    return initial_state


def run_monitor(approved: bool = False) -> dict[str, Any]:
    """Monitora todas as cidades dos segurados e dispara alertas quando necessario.

    Para cada cidade com segurados ativos, consulta o clima, classifica o evento
    e executa o pipeline completo se o evento for relevante.

    Args:
        approved: Se True, envia email real. Se False, apenas simula.

    Returns:
        Dict com resumo do monitoramento de todas as cidades.
    """
    db = get_database()
    cities = db.get_distinct_cities()
    run_id = f"RUN-MONITOR-{uuid.uuid4().hex[:8].upper()}"

    results = []
    alerts_triggered = 0
    emails_sent = 0

    for city in cities:
        city_result = run_pipeline(location=city, approved=approved)

        if city_result.get("error"):
            results.append(
                {
                    "city": city,
                    "status": "erro",
                    "error": city_result["error"],
                }
            )
            continue

        event_data = city_result.get("event_data", {})
        eligible_count = sum(
            1
            for d in city_result.get("eligibility_data", [])
            if d.get("status") == "elegivel"
        )
        simulations_count = len(city_result.get("simulations_data", []))

        if event_data.get("relevance") and eligible_count > 0:
            alerts_triggered += 1
            emails_sent += simulations_count

        results.append(
            {
                "city": city,
                "status": "ok",
                "event_type": event_data.get("event_type", "sem_evento"),
                "severity": event_data.get("severity", "baixa"),
                "relevant": event_data.get("relevance", False),
                "eligible_count": eligible_count,
                "simulations_count": simulations_count,
            }
        )

    return {
        "run_id": run_id,
        "cities_scanned": len(cities),
        "alerts_triggered": alerts_triggered,
        "emails_sent": emails_sent,
        "results": results,
    }
