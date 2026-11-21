"""Drill: the page's audit list keeps the rows a specialist wrote while the coordinator's call to it was open.

Found by the end-to-end check: the coordinator's "allowed" row for scout, router, critic or companion was written
into the session when the call started and saved when it ended, replacing the list and dropping every row the
specialist had added in between (blocked and withheld rows included). The session is modelled here the way it
behaved in that run: a write inside a tool call is pending until the call ends, then replaces the saved value.
No network, no key, no model. The policy plugin needs the ADK; without it this drill only says so.

Run from the repo folder: python3 tests/drill_audit.py
"""
import asyncio
import os
import sys
import tempfile
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ["AUDIT_LOG"] = os.path.join(tempfile.mkdtemp(prefix="gilmate-drill-"), "audit.jsonl")

from gilmate import guards  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


class State:
    """Saved values plus the writes of one open tool call."""
    def __init__(self, saved):
        self.saved, self.pending = saved, {}

    def get(self, key, default=None):
        return self.pending.get(key, self.saved.get(key, default))

    def __setitem__(self, key, value):
        self.pending[key] = value

    def to_dict(self):
        return {**self.saved, **self.pending}

    def call_ends(self):
        self.saved.update(self.pending)


def call(saved, agent, tool, call_id):
    return types.SimpleNamespace(name=tool), types.SimpleNamespace(
        state=State(saved), agent_name=agent, invocation_id="turn-1", function_call_id=call_id)


try:
    from gilmate.security import SecurityPlugin
except ImportError:
    SecurityPlugin = None
    print("note  not checked here: the policy plugin in gilmate/security.py needs the ADK")

if SecurityPlugin:
    plugin, saved = SecurityPlugin(), {"audit": [{"agent": "earlier", "tool": "turn", "decision": "allowed"}]}
    run = asyncio.run

    scout_tool, outer = call(saved, "coordinator", "scout", "call-scout")
    check("the coordinator's call to the scout is allowed",
          run(plugin.before_tool_callback(tool=scout_tool, tool_args={"request": "find"}, tool_context=outer)) is None)
    # the scout works while that call is open: one allowed search, one search the policy refuses
    for category, call_id in (("see", "call-1"), ("hotel", "call-2")):
        tool, inner = call(saved, "scout", "search_options", call_id)
        answer = run(plugin.before_tool_callback(tool=tool, tool_args={"category": category}, tool_context=inner))
        check("inside the scout: search_options category=%s is %s" % (category, "refused" if answer else "allowed"),
              bool(answer) == (category == "hotel"), answer)
        if not answer:
            run(plugin.after_tool_callback(tool=tool, tool_args={"category": category}, tool_context=inner, result={}))
        inner.state.call_ends()
    run(plugin.after_tool_callback(tool=scout_tool, tool_args={"request": "find"}, tool_context=outer, result={}))
    outer.state.call_ends()

    rows = [(r["agent"], r["tool"], r["decision"]) for r in saved["audit"]]
    check("after the scout returns, the session has every row, the specialist's too, in the order they happened",
          rows == [("earlier", "turn", "allowed"), ("coordinator", "scout", "allowed"),
                   ("scout", "search_options", "allowed"), ("scout", "search_options", "blocked")], rows)
    check("the chained file has the same three new rows and verifies",
          guards.verify_chain(os.environ["AUDIT_LOG"]) and len(open(os.environ["AUDIT_LOG"]).readlines()) == 3)

    # the limits of a specialist's tools count per call to it: a scout asked again may read the saved searches again
    def searches(call_id, count):
        answers = []
        for i in range(count):
            tool, inner = call(saved, "scout", "search_options", "%s-%d" % (call_id, i))
            answers.append(run(plugin.before_tool_callback(tool=tool, tool_args={"category": "eat"}, tool_context=inner)))
        return ["refused" if a else "allowed" for a in answers]

    plugin, saved = SecurityPlugin(), {"audit": []}
    tool, outer = call(saved, "coordinator", "scout", "scout-1")
    run(plugin.before_tool_callback(tool=tool, tool_args={}, tool_context=outer))
    got = searches("first", 4)
    check("within one call to the scout the fourth search is refused", got == ["allowed"] * 3 + ["refused"], got)
    tool, outer = call(saved, "coordinator", "scout", "scout-2")
    run(plugin.before_tool_callback(tool=tool, tool_args={}, tool_context=outer))
    got = searches("second", 4)
    check("a second call to the scout may search three times again", got == ["allowed"] * 3 + ["refused"], got)
    tool, outer = call(saved, "coordinator", "scout", "scout-3")
    got = run(plugin.before_tool_callback(tool=tool, tool_args={}, tool_context=outer))
    check("the calls to the scout itself stay limited per turn: the third is refused",
          bool(got) and got["rule"] == "scout.max_calls:2", got)
    plugin, saved = SecurityPlugin(), {"audit": [], "spatial_model": {}}
    answers = []
    for i in range(2):
        tool, outer = call(saved, "coordinator", "record_feedback", "tap-%d" % i)
        answers.append(run(plugin.before_tool_callback(tool=tool, tool_args={"leg_id": "s1>s2", "verdict": "too_far"}, tool_context=outer)))
        tool, outer = call(saved, "coordinator", "companion", "ask-%d" % i)
        run(plugin.before_tool_callback(tool=tool, tool_args={}, tool_context=outer))
    check("calling a specialist does not give the coordinator a second 'too far' in one turn",
          answers[0] is None and bool(answers[1]) and answers[1]["rule"] == "record_feedback.max_calls:1", answers)

    plugin, saved = SecurityPlugin(), {"audit": [{"tool": "turn"}, {"tool": "scout"}, {"tool": "search_options"}, {"tool": "search_options"}]}
    # a specialist that fails still gets its row
    tool, outer = call(saved, "coordinator", "critic", "call-critic")
    run(plugin.before_tool_callback(tool=tool, tool_args={}, tool_context=outer))
    run(plugin.on_tool_error_callback(tool=tool, tool_args={}, tool_context=outer, error=RuntimeError("stopped")))
    outer.state.call_ends()
    check("a specialist call that ends in an error keeps its row and the rows before it",
          [r["tool"] for r in saved["audit"]] == ["turn", "scout", "search_options", "search_options", "critic"],
          [r["tool"] for r in saved["audit"]])

print("drill_audit: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
