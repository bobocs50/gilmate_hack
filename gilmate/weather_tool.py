"""The router's weather tool. The reading and every rule are in gilmate/weather.py; this is only the ADK wrapper."""
from google.adk.tools import ToolContext

from . import weather
from .tools import log


def weather_today(tool_context: ToolContext) -> dict:
    """Today's weather for the area being visited, from Open-Meteo, as a fixed verdict: rain none, possible or
    likely; heat ok, hot or very_hot; cold or not. The walking limit is already lowered by the system when rain is
    likely or it is very hot. When no weather could be read, plan as usual and say nothing about the weather."""
    state = tool_context.state
    weather.ensure(state, tool_context.agent_name, log)
    told = weather.facts(state)
    if not told:
        return {"status": "unavailable",
                "message": "No weather could be read. Plan as usual and do not say anything about the weather."}
    return {"status": "ok", **told["weather"]}
