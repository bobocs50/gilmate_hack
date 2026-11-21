"""One plugin for every agent: each tool call is checked against the policy table first, and logged."""
from google.adk.plugins.base_plugin import BasePlugin

from . import guards, progress
from .tools import log

guards.POLICY.setdefault("record_picks", {"max_calls": 1, "args": {}})
guards.POLICY["save_options"]["max_calls"] = 4   # the scout may need to correct a rejected option more than once
guards.POLICY["find_place"]["max_calls"] = 20
guards.POLICY.setdefault("weather_today", {"max_calls": 1, "args": {}})      # the router's reading of gilmate/weather.py


# Tools whose answers are screened record by record by their own hook right after this plugin (gilmate/places.py):
# the MCP server's raw answer names what it withheld, so screening it here as one text would withhold all of it.
OWN_SCREEN = ("places_search", "place_details")
TYPED = ("text", "question")          # the fields of a page message that hold words the person typed

SPECIALISTS = ("scout", "option_scout", "router", "critic", "companion")     # called by the coordinator like tools
HER_DECISIONS = ("record_picks", "record_said", "record_context", "record_feedback", "forget_fact")      # the coordinator's own tools


class SecurityPlugin(BasePlugin):
    def __init__(self):
        super().__init__(name="security")
        self._calls = {}
        self._open = {}      # call id of a running specialist -> (audit rows before it started, its "allowed" row)

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        key = (tool_context.invocation_id, tool.name)
        calls = self._calls.get(key, 0)
        rule = guards.check_policy(tool.name, dict(tool_args or {}), calls, tool_context.state.to_dict()
                                   if hasattr(tool_context.state, "to_dict") else dict(tool_context.state))
        if rule:
            log(tool_context.state, tool_context.agent_name, tool.name, "blocked", rule,
                guards.redact(str(tool_args))[:160])
            return {"status": "denied", "rule": rule, "message": "Blocked by the policy table. Do not retry; say so."}
        self._calls[key] = calls + 1
        if tool.name in SPECIALISTS:
            # A specialist starts each call with nothing in mind, so the limits of its own tools count per call:
            # a scout asked a second time may read the saved searches again. The calls to the specialists
            # themselves and her decisions stay limited per turn.
            for other in [k for k in self._calls if k[0] == key[0] and k[1] not in SPECIALISTS + HER_DECISIONS]:
                del self._calls[other]
            # The specialist writes its own audit rows into the session while this call is open. A row written
            # here is saved only when the call ends and would then replace the list, losing the specialist's rows.
            # So the row goes into the file now and into the session in after_tool_callback, at its place.
            row = log(None, tool_context.agent_name, tool.name, "allowed", "", self._named(tool_args))
            self._open[tool_context.function_call_id] = (len(tool_context.state.get("audit", [])), row)
        else:
            log(tool_context.state, tool_context.agent_name, tool.name, "allowed", "", self._named(tool_args))
        return None

    @staticmethod
    def _named(tool_args):
        """The category or place name of a call, so its step can say "Searched the web: sights"."""
        return guards.redact("; ".join(f"{k}={v}" for k, v in (tool_args or {}).items()
                                       if k in ("category", "name")))[:120]

    async def on_user_message_callback(self, *, invocation_context, user_message):
        """Typed words that read like an instruction are noted in the chained log. The message is not changed:
        the tools read it themselves and keep only fixed choices (say, context) or drop the wish."""
        try:
            import json
            message = json.loads("".join(part.text or "" for part in user_message.parts))
            for field in TYPED:
                words = message.get(field) if isinstance(message, dict) else None
                rule = guards.screen_text(words) if isinstance(words, str) else None
                if rule:
                    log(None, "traveller", "typed_text", "flagged", rule,
                        "step=%s; field=%s" % (str(message.get("step"))[:20], field))
        except Exception:
            pass                       # a message that is not the page's JSON: the coordinator refuses it itself
        return None

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
        self._close(tool_context)
        return self._screened(tool, tool_context, result)

    @staticmethod
    def _screened(tool, tool_context, result):
        """What a tool returns is data. A string in it that reads like an instruction, or holds a key, does not
        reach the model: it is replaced, and an audit row names the field. Returns the changed result, or None."""
        if tool.name in SPECIALISTS or tool.name in OWN_SCREEN:
            return None                # a specialist's report is a model's text; the two Places tools: see OWN_SCREEN
        try:
            clean, withheld = guards.screen_fields(result)
        except Exception:
            clean, withheld = {"status": "withheld"}, [{"field": "", "rule": "screen_failed", "sample": ""}]
        if not withheld:
            return None
        for w in withheld:
            log(tool_context.state, tool_context.agent_name, tool.name, "withheld", w["rule"],
                "%s | %s" % (w["field"], w["sample"]))
        return clean if isinstance(clean, dict) else {"status": "ok", "result": clean}

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        self._close(tool_context)
        return None

    def _close(self, tool_context):
        held = self._open.pop(tool_context.function_call_id, None)
        if held:
            before, row = held
            rows = list(tool_context.state.get("audit", []))
            rows.insert(min(before, len(rows)), row)
            tool_context.state["audit"] = rows
            tool_context.state["progress"] = progress.steps(rows)
