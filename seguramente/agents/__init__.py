"""Agentes especializados do SeguraMente."""

from .base import AgentLog, SeguraMenteState
from .eligibility_agent import check_insured_eligibility
from .event_agent import classify_weather_event
from .message_agent import generate_preventive_message
from .notification_agent import send_email_notification, simulate_notification
from .supervisor import (
    create_supervisor_graph,
    run_pipeline,
    run_pipeline_from_observation,
)
from .weather_agent import fetch_weather_data, fetch_weather_from_observation

ALL_TOOLS = [
    fetch_weather_data,
    fetch_weather_from_observation,
    classify_weather_event,
    check_insured_eligibility,
    generate_preventive_message,
    simulate_notification,
    send_email_notification,
]

__all__ = [
    "ALL_TOOLS",
    "AgentLog",
    "SeguraMenteState",
    "check_insured_eligibility",
    "classify_weather_event",
    "create_supervisor_graph",
    "fetch_weather_data",
    "fetch_weather_from_observation",
    "generate_preventive_message",
    "run_pipeline",
    "run_pipeline_from_observation",
    "send_email_notification",
    "simulate_notification",
]
