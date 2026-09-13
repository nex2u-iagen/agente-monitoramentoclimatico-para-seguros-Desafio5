"""Interface Streamlit do SeguraMente — Versao Multi-Agentes.

Exibe o status detalhado de cada agente em tempo real durante a execucao do pipeline.
"""

from __future__ import annotations

import sys
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

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
from seguramente.weather import search_locations

AGENTS_DISPLAY = [
    {
        "name": "weather_agent",
        "label": "Coletor Meteorologico",
        "icon": "weather_agent",
    },
    {"name": "event_agent", "label": "Analista de Eventos", "icon": "event_agent"},
    {
        "name": "eligibility_agent",
        "label": "Verificador de Elegibilidade",
        "icon": "eligibility_agent",
    },
    {"name": "message_agent", "label": "Gerador de Mensagens", "icon": "message_agent"},
    {
        "name": "notification_agent",
        "label": "Notificador",
        "icon": "notification_agent",
    },
]

st.set_page_config(page_title="SeguraMente", page_icon="", layout="wide")
st.title("SeguraMente")
st.caption("Sistema Multi-Agentes de Comunicacao Preventiva — Desafio 5 InsurMinds")

db = get_database()

import sqlite3 as _sqlite3

_conn_check = _sqlite3.connect(str(db._path))
try:
    _count = _conn_check.execute("SELECT COUNT(*) FROM insured_profiles").fetchone()[0]
except _sqlite3.OperationalError:
    _count = 0
_conn_check.close()

if _count == 0:
    import csv
    import sqlite3
    from pathlib import Path

    csv_path = Path(__file__).parent / "data" / "insured_profiles.csv"
    conn = sqlite3.connect(str(db._path))
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            conn.execute(
                "INSERT OR IGNORE INTO insured_profiles "
                "(profile_id, name, city, state, product, channel, consent, contact) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["profile_id"],
                    row["name"],
                    row["city"],
                    row["state"],
                    row["product"].strip().lower(),
                    row["channel"].strip().lower(),
                    row["consent"].strip().lower() in {"true", "1", "sim"},
                    row["contact"],
                ),
            )
    conn.commit()
    conn.close()
    st.toast("Banco de dados populado automaticamente.")

with st.sidebar:
    st.header("Configuracao da Execucao")
    execution_mode = st.radio(
        "Fonte meteorologica", ["Demonstracao reproduzivel", "API ao vivo"]
    )
    provider_mode = st.radio(
        "Provider LLM",
        ["template", "openai", "openai-compatible", "gemini"],
        help="Template = offline. OpenAI/Gemini = requer chave de API.",
    )
    if execution_mode == "Demonstracao reproduzivel":
        scenario = st.selectbox("Cenario", list(FIXTURES.keys()))
    else:
        db_cities = db.get_distinct_cities()
        location_options = db_cities + ["Outra (buscar cidade)"]
        selected = st.selectbox("Localidade", location_options)
        if selected == "Outra (buscar cidade)":
            search_query = st.text_input("Buscar cidade", value="")
            if search_query:
                results = search_locations(search_query)
                if results:
                    labels = [r["label"] for r in results]
                    chosen = st.selectbox("Selecione", labels)
                    location = next(r["name"] for r in results if r["label"] == chosen)
                else:
                    location = search_query
            else:
                location = "Sao Paulo"
        else:
            location = selected
    st.divider()
    st.info("Nenhuma comunicacao real e disparada. Todos os perfis sao sinteticos.")

    st.divider()
    st.subheader("Monitoramento de Cidades")
    cities = db.get_distinct_cities()
    st.write(f"Cidades com segurados: {', '.join(cities)}")
    monitor_approved = st.checkbox(
        "Aprovar envio real no monitoramento",
        key="monitor_approved",
    )
    if st.button("Monitorar todas as cidades", type="secondary"):
        import os

        os.environ["LLM_PROVIDER"] = provider_mode
        with st.status("Monitorando cidades...", expanded=True) as status:
            monitor_result = run_monitor(approved=monitor_approved)
            st.session_state["monitor_result"] = monitor_result
            status.update(
                label=f"Monitoramento concluido: {monitor_result['alerts_triggered']} alertas",
                state="complete",
                expanded=False,
            )
            st.success(f"{monitor_result['cities_scanned']} cidades escaneadas")

    st.divider()
    st.subheader("Webhook")
    st.code(
        "POST http://localhost:8000/webhook/alert\n"
        '{"location": "Sao Paulo", "approved": false}',
        language="json",
    )


def render_agent_status(logs: list[dict], agent_name: str) -> tuple[str, str]:
    """Retorna (status_label, detail) para um agente baseado nos logs."""
    agent_logs = [l for l in logs if l.get("agent_name") == agent_name]
    if not agent_logs:
        return "Aguardando", ""
    last = agent_logs[-1]
    status = last.get("status", "")
    detail = last.get("output_summary", "")
    if status == "started":
        return "Executando", detail
    elif status == "completed":
        return "Concluido", detail
    elif status == "error":
        return "Erro", detail
    return status, detail


def show_agent_dashboard(logs: list[dict]):
    """Exibe dashboard visual dos agentes."""
    st.subheader("Status dos Agentes")

    cols = st.columns(len(AGENTS_DISPLAY))
    for idx, agent_info in enumerate(AGENTS_DISPLAY):
        with cols[idx]:
            status_label, detail = render_agent_status(logs, agent_info["name"])
            if status_label == "Concluido":
                st.success(f"**{agent_info['label']}**\n\nConcluido")
            elif status_label == "Executando":
                st.info(f"**{agent_info['label']}**\n\nExecutando...")
            elif status_label == "Erro":
                st.error(f"**{agent_info['label']}**\n\nErro")
            else:
                st.warning(f"**{agent_info['label']}**\n\nAguardando")
            if detail:
                st.caption(detail[:150])


def show_agent_details(logs: list[dict]):
    """Exibe detalhes expansveis de cada agente."""
    st.subheader("Detalhes por Agente")

    for agent_info in AGENTS_DISPLAY:
        agent_logs = [l for l in logs if l.get("agent_name") == agent_info["name"]]
        with st.expander(
            f"{agent_info['label']} — {len(agent_logs)} execucoes", expanded=False
        ):
            if not agent_logs:
                st.info("Nenhuma execucao registrada.")
                continue
            for log in agent_logs:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write(f"**Status:** {log.get('status', 'N/A')}")
                    st.write(f"**Inicio:** {log.get('started_at', 'N/A')}")
                    if log.get("duration_ms"):
                        st.write(f"**Duracao:** {log['duration_ms']:.0f}ms")
                with col2:
                    if log.get("input_summary"):
                        st.write(f"**Entrada:** {log['input_summary']}")
                    if log.get("output_summary"):
                        st.write(f"**Saida:** {log['output_summary']}")
                st.divider()


if "result" not in st.session_state:
    st.session_state.result = None

if st.button("Executar pipeline completo", type="primary"):
    import os

    os.environ["LLM_PROVIDER"] = provider_mode

    try:
        with st.status("Executando pipeline multi-agentes...", expanded=True) as status:
            st.write("Iniciando supervisor...")
            time.sleep(0.3)

            if execution_mode == "Demonstracao reproduzivel":
                observation = FIXTURES[scenario]()
                result = run_pipeline_from_observation(
                    observation_dict=asdict(observation),
                    approved=False,
                )
            else:
                if not location.strip():
                    st.error("Informe uma localidade.")
                    st.stop()
                result = run_pipeline(
                    location=location,
                    approved=False,
                )

            st.session_state.result = result
            status.update(label="Pipeline concluido!", state="complete", expanded=False)
            st.success("Pipeline executado com sucesso!")
    except (AgentError, ValueError, RuntimeError) as exc:
        st.error(f"Erro ao executar pipeline: {exc}")

result = st.session_state.result

if result is None:
    st.markdown(
        """
        ### Como demonstrar

        1. Selecione um cenario reproduzivel ou uma localidade real
        2. Escolha o provider LLM (template para offline)
        3. Clique em **Executar pipeline completo**
        4. Acompanhe o status de cada agente em tempo real
        5. Revise as mensagens geradas e registre a simulacao

        ### Webhook

        Execute o servidor FastAPI para receber alertas externos:
        ```bash
        uvicorn webhook:app --host 0.0.0.0 --port 8000
        ```
        """
    )
    st.stop()

logs = result.get("agent_logs", [])
show_agent_dashboard(logs)
show_agent_details(logs)

st.divider()

event_data = result.get("event_data", {})
if event_data:
    st.header("1. Classificacao do Evento")
    col1, col2, col3 = st.columns(3)
    col1.metric("Tipo", event_data.get("event_type", "N/A").replace("_", " ").title())
    col2.metric("Severidade", event_data.get("severity", "N/A").title())
    col3.metric("Relevante", "Sim" if event_data.get("relevance") else "Nao")
    st.write(f"**Justificativa:** {event_data.get('justification', 'N/A')}")
    if event_data.get("indicators"):
        st.json(event_data["indicators"])

obs_data = result.get("observation_data", {})
if obs_data:
    with st.expander("Dados Meteorologicos Completos", expanded=False):
        st.json(obs_data)

eligibility_data = result.get("eligibility_data", [])
if eligibility_data:
    st.header("2. Elegibilidade dos Segurados")
    decisions_df = pd.DataFrame(
        [
            {
                "Perfil": d.get("profile", {}).get("name", "N/A"),
                "Cidade": d.get("profile", {}).get("city", "N/A"),
                "Produto": d.get("profile", {}).get("product", "N/A"),
                "Canal": d.get("profile", {}).get("channel", "N/A"),
                "Consentimento": "Ativo"
                if d.get("profile", {}).get("consent")
                else "Inativo",
                "Status": d.get("status", "N/A"),
                "Motivo": "; ".join(d.get("reasons", [])),
            }
            for d in eligibility_data
        ]
    )
    st.dataframe(decisions_df, width="stretch", hide_index=True)

messages_data = result.get("messages_data", [])
st.header("3. Mensagens Geradas")
if not messages_data:
    st.warning(
        "Nenhuma mensagem gerada: evento irrelevante ou todos perfis bloqueados."
    )
else:
    for idx, msg in enumerate(messages_data, start=1):
        with st.container(border=True):
            st.write(
                f"**Mensagem {idx} — {msg.get('channel', '').upper()} — {msg.get('recipient', '')}**"
            )
            st.write(msg.get("text", ""))
            st.caption(
                f"Provider: {msg.get('provider', 'N/A')} | "
                f"Modelo: {msg.get('model', 'N/A')} | "
                f"Gerada em: {msg.get('generated_at', 'N/A')}"
            )

    st.divider()
    st.subheader("Revisao Humana e Envio")
    approved = st.checkbox(
        "Confirmo que revisei as mensagens e autorizo o envio de email real."
    )
    if approved:
        st.warning("Emails REAIS serao enviados para os destinatarios listados acima.")
    if st.button("Enviar notificacoes", disabled=not approved, type="primary"):
        import os

        os.environ["LLM_PROVIDER"] = provider_mode

        updated_result = run_pipeline_from_observation(
            observation_dict=result.get("observation_data", {}),
            approved=True,
        )
        result["simulations_data"] = updated_result.get("simulations_data", [])
        st.session_state.result = result
        st.success("Notificacoes enviadas! Confira o historico abaixo.")
        st.rerun()

simulations_data = result.get("simulations_data", [])
st.header("4. Historico de Notificacoes")
if simulations_data:
    sim_df = pd.DataFrame(
        [
            {
                "ID": s.get("simulation_id", ""),
                "Perfil": s.get("profile_id", ""),
                "Canal": s.get("channel", ""),
                "Destinatario": s.get("recipient", ""),
                "Status": s.get("status", ""),
                "Criado em": s.get("created_at", ""),
            }
            for s in simulations_data
        ]
    )
    st.dataframe(sim_df, width="stretch", hide_index=True)
else:
    st.info("Nenhuma notificacao registrada. A revisao humana e obrigatoria.")

st.divider()
st.subheader("Historico de Execucoes no Banco")
with st.expander("Ver logs de agentes no SQLite", expanded=False):
    all_logs = db.get_all_agent_logs(limit=30)
    if all_logs:
        logs_df = pd.DataFrame(all_logs)
        st.dataframe(logs_df, width="stretch", hide_index=True)
    else:
        st.info("Nenhum log registrado no banco de dados.")

monitor_result = st.session_state.get("monitor_result")
if monitor_result:
    st.divider()
    st.header("5. Resultado do Monitoramento")
    col1, col2, col3 = st.columns(3)
    col1.metric("Cidades escaneadas", monitor_result["cities_scanned"])
    col2.metric("Alertas acionados", monitor_result["alerts_triggered"])
    col3.metric("Emails enviados", monitor_result["emails_sent"])

    if monitor_result.get("results"):
        monitor_df = pd.DataFrame(monitor_result["results"])
        st.dataframe(monitor_df, width="stretch", hide_index=True)
