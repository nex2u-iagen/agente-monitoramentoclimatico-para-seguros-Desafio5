"""Tools LangGraph do SeguraMente.

Cada tool é um módulo separado que expõe funcionalidades
que os agentes podem invocar.
"""

from .eligibility_tool import check_insured_eligibility
from .event_tool import classify_weather_event
from .message_tool import generate_preventive_message
from .notification_tool import send_email_notification, simulate_notification
from .weather_tool import fetch_weather_data, fetch_weather_from_observation

WEATHER_TOOLS = [fetch_weather_data, fetch_weather_from_observation]
EVENT_TOOLS = [classify_weather_event]
ELIGIBILITY_TOOLS = [check_insured_eligibility]
MESSAGE_TOOLS = [generate_preventive_message]
NOTIFICATION_TOOLS = [simulate_notification, send_email_notification]

ALL_TOOLS = (
    WEATHER_TOOLS + EVENT_TOOLS + ELIGIBILITY_TOOLS + MESSAGE_TOOLS + NOTIFICATION_TOOLS
)

__all__ = [
    "ALL_TOOLS",
    "ELIGIBILITY_TOOLS",
    "EVENT_TOOLS",
    "MESSAGE_TOOLS",
    "NOTIFICATION_TOOLS",
    "WEATHER_TOOLS",
    "check_insured_eligibility",
    "classify_weather_event",
    "fetch_weather_data",
    "fetch_weather_from_observation",
    "generate_preventive_message",
    "send_email_notification",
    "simulate_notification",
]
