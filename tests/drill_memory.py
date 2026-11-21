"""Drill: Gilmate's memory of one traveller (CONTRACT.md section 6).

One "too far" tap gives a candidate walking limit, two give a kept one, the next route's fits_profile flags
change, and forgetting the fact restores the old result. Uses the map extract in data/.
No network, no key, no model.

Run from the repo folder: python3 tests/drill_memory.py
"""
import copy
import os
import sys
import tempfile
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from gilmate import guards, memory, osm  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


# Three real places from the map extract, one per category, a few hundred metres apart.
PLACES = [("o1", "see", "node/597685675"),      # Hachiko Memorial Statue
          ("o2", "shop", "node/11034183301"),   # Loft
          ("o3", "eat", "node/4360904389")]     # Uobei
ON_MAP = osm.load()["places"]
check("the three drill places are in the map extract with their categories",
      all(ref in ON_MAP and ON_MAP[ref]["category"] == cat for _, cat, ref in PLACES))
if FAILED:
    print("drill_memory: FAILED, the map extract no longer has the drill places")
    sys.exit(1)

OPTIONS = [{"id": oid, "category": cat, "name": ON_MAP[ref]["name"], "summary": {"en": "", "ko": ""}, "facts": [],
            "place": {k: ON_MAP[ref][k] for k in ("lat", "lon", "osm_id", "access")}} for oid, cat, ref in PLACES]
PICKS = ["o1", "o2", "o3"]
PROFILE = {"walk": "medium", "stairs": "ok", "rest": "sometimes", "wish": None, "language": "ko"}
FACT_KEYS = {"id", "key", "value", "group", "source", "evidence", "at", "effect", "status", "changed_legs"}
DAY1, DAY2 = "2026-11-21", "2026-11-22"


def at(day, clock):
    return time.strptime(day + " " + clock, "%Y-%m-%d %H:%M")


def plain(state):
    return state.to_dict() if hasattr(state, "to_dict") else dict(state)


def new_session(earlier=None):
    """A fresh session for the same traveller: ADK carries over only the keys that start with "user:"."""
    state = {k: copy.deepcopy(v) for k, v in plain(earlier or {}).items() if k.startswith("user:")}
    state["profile"] = dict(PROFILE)
    return state


def route(state, day, order=PICKS):
    """Build and publish a route the way propose_route and submit_review do."""
    model, _ = osm.build_model(memory.profile(state), OPTIONS, PICKS, list(order), None, memory.learned_limit(state, day))
    state["spatial_model"] = model
    memory.note_route(state, model, day)
    return model


def flags(model):
    return {leg["id"]: leg["fits_profile"] for leg in model["legs"]}


def fact(state, key):
    return next((f for f in memory.read(state)["facts"] if f["key"] == key), None)


HANGUL = __import__("re").compile("[\uac00-\ud7a3]")


def both_languages(f):
    """Evidence and effect are {en, ko}: an English sentence and a Korean one, both written by Python."""
    return all(isinstance(f[k], dict) and set(f[k]) == {"en", "ko"} and f[k]["en"] and not HANGUL.search(f[k]["en"])
               and HANGUL.search(f[k]["ko"]) for k in ("evidence", "effect"))


def without_time(model):
    return {k: v for k, v in model.items() if k != "generated_at"}


# --- no learned limit: exactly today's behaviour --------------------------------------------------------------
today, _ = osm.build_model(PROFILE, OPTIONS, PICKS, PICKS)
explicit_none, _ = osm.build_model(PROFILE, OPTIONS, PICKS, PICKS, None, None)
check("build_model without a learned limit equals build_model with learned_limit_m=None",
      without_time(today) == without_time(explicit_none))
for walk, want in (("short", 300), ("medium", 600), ("long", None)):
    got = osm.walk_limit({"walk": walk})
    check("no learned limit: walk=%s keeps the limit %r" % (walk, want), got == want, got)
    got = [leg["fits_profile"] for leg in osm.build_model({**PROFILE, "walk": walk}, OPTIONS, PICKS, PICKS)[0]["legs"]]
    expect = [want is None or leg["distance_m"] <= want for leg in today["legs"]]
    check("no learned limit: walk=%s flags follow her answer alone" % walk, got == expect, got)
# --- the lower of the two limits applies ------------------------------------------------------------------------
for walk, want in (("short", 300), ("medium", 450), ("long", 450)):
    got = osm.walk_limit({"walk": walk}, 450)
    check("learned 450 m with walk=%s: the lower limit applies, %d m" % (walk, want), got == want, got)
check("a learned limit alone, with no answer about walking, applies as it is", osm.walk_limit({}, 450) == 450)
check("learned 341 m, answer short: 300 m applies; a learned limit never lifts her answer",
      osm.walk_limit({"walk": "short"}, 341) == 300, osm.walk_limit({"walk": "short"}, 341))
SHORT = {**PROFILE, "walk": "short"}
asked_only, _ = osm.build_model(SHORT, OPTIONS, PICKS, PICKS)
with_341, _ = osm.build_model(SHORT, OPTIONS, PICKS, PICKS, None, 341)
check("learned 341 m, answer short: the route is the one her answer alone gives, flags and warnings",
      without_time(with_341) == without_time(asked_only), flags(with_341))
check("learned 341 m, answer short: every flag is exactly distance <= 300",
      all(leg["fits_profile"] == (leg["distance_m"] <= 300) for leg in with_341["legs"]),
      [(leg["distance_m"], leg["fits_profile"]) for leg in with_341["legs"]])
check("learned 341 m, answer short: long-walk warnings name the 300 m she asked for, not 341",
      all("300 m you asked for" in h["detail"]["en"] and "341" not in h["detail"]["en"] and "341" not in h["detail"]["ko"]
          for h in with_341["hazards"] if h["kind"] == "long_walk")
      and any(h["kind"] == "long_walk" for h in with_341["hazards"]), with_341["hazards"])
check("learned 341 m, answer short: the learned limit changed no walk",
      osm.legs_changed_by_limit(with_341, SHORT, 341) == [], osm.legs_changed_by_limit(with_341, SHORT, 341))
with_250, _ = osm.build_model(SHORT, OPTIONS, PICKS, PICKS, None, 250)
check("learned 250 m, answer short: the learned limit is the lower one and applies",
      all(leg["fits_profile"] == (leg["distance_m"] <= 250) for leg in with_250["legs"])
      and all("250 m limit set after" in h["detail"]["en"] for h in with_250["hazards"] if h["kind"] == "long_walk"),
      [(leg["distance_m"], leg["fits_profile"]) for leg in with_250["legs"]])

# --- her answers become kept facts ------------------------------------------------------------------------------
session = new_session()
check("memory is one per-user key", memory.KEY == "user:memory")
check("nothing is remembered before Python has seen her answers", memory.KEY not in session)
memory.profile(session, at(DAY1, "09:40"))
mem = session[memory.KEY]
check("memory holds exactly facts and feedback", set(mem) == {"facts", "feedback"} and mem["feedback"] == [], sorted(mem))
check("her four answers become four facts, in the contract's shape",
      [f["key"] for f in mem["facts"]] == list(memory.ANSWERS) and all(set(f) == FACT_KEYS for f in mem["facts"]),
      mem["facts"])
check("answer facts carry her values, are kept, and say where they came from",
      all(f["value"] == PROFILE[f["key"]] and (f["group"], f["source"], f["status"]) == ("answers", "answer", "kept")
          and f["at"] == "09:40" and both_languages(f) and f["changed_legs"] == [] for f in mem["facts"]),
      mem["facts"])
check("fact ids are f1..f4", [f["id"] for f in mem["facts"]] == ["f1", "f2", "f3", "f4"])
check("the walk fact says what it changes, from the limit table, and that a lower learned limit applies",
      fact(session, "walk")["effect"] == {
          "en": "Walks longer than 600 m are flagged, unless a lower limit learned from your taps applies.",
          "ko": "600m보다 긴 구간은 표시됩니다. 다만 누르신 평가로 배운 더 낮은 기준이 있으면 그 기준이 적용됩니다."},
      fact(session, "walk")["effect"])
check("the walk fact says in both languages where it came from",
      fact(session, "walk")["evidence"] == {"en": 'You answered "medium" when asked about how far you like to walk.',
                                            "ko": '걷는 거리 질문에 이렇게 답하셨습니다: "보통".'}, fact(session, "walk")["evidence"])
before = copy.deepcopy(session)
memory.profile(session, at(DAY1, "09:55"))
check("reading her answers again writes nothing", session == before)
bare = {k: v for k, v in session.items() if k.startswith("user:")}
check("a session without answers gets the remembered ones",
      memory.profile(bare) == {k: PROFILE[k] for k in memory.ANSWERS}, memory.profile(bare))
changed = new_session(session)
changed["profile"] = {**PROFILE, "walk": "short"}
memory.profile(changed, at(DAY2, "08:05"))
check("a new answer replaces the fact and keeps its id",
      (fact(changed, "walk")["value"], fact(changed, "walk")["id"], fact(changed, "walk")["at"]) == ("short", "f1", "08:05")
      and len(changed[memory.KEY]["facts"]) == 4, fact(changed, "walk"))
check("no answers anywhere is an empty profile, not an invented one", memory.profile({}) == {})

# --- her three picks become facts in group "picks" ---------------------------------------------------------------
session.update(options=OPTIONS, picks=list(PICKS))
memory.remember_picks(session, at(DAY1, "09:58"))
picks = [f for f in session[memory.KEY]["facts"] if f["group"] == "picks"]
check("her three picks become three facts with the map's names",
      [(f["key"], f["value"], f["source"], f["status"]) for f in picks]
      == [(o["category"], o["name"], "pick", "kept") for o in OPTIONS] and all(set(f) == FACT_KEYS for f in picks), picks)
memory.remember_picks(session, at(DAY1, "09:59"))
check("picking again does not add facts", len(session[memory.KEY]["facts"]) == 7, len(session[memory.KEY]["facts"]))

# --- the core case ----------------------------------------------------------------------------------------------
first = route(session, DAY1)
d = {leg["id"]: leg["distance_m"] for leg in first["legs"]}
check("first route: two walks of different length, both fit her answers",
      len(d) == 2 and len(set(d.values())) == 2 and flags(first) == {"s1>s2": True, "s2>s3": True}, (d, flags(first)))
check("no limit is learned before any tap", memory.learned_limit(session, DAY1) is None and fact(session, "walk_limit_m") is None)
longer, shorter = sorted(d, key=d.get, reverse=True)
start = {leg["id"]: next(s["name"] for s in first["stops"] if s["id"] == leg["from"]) for leg in first["legs"]}

got = memory.record_feedback(session, longer, "too_far", at(DAY1, "10:42"))
limit1 = d[longer] - memory.MARGIN_M
check("one too_far tap returns {status, fact} with a candidate walk_limit_m fact",
      set(got) == {"status", "fact"} and got["status"] == "recorded" and set(got["fact"]) == FACT_KEYS
      and (got["fact"]["key"], got["fact"]["status"], got["fact"]["group"], got["fact"]["source"])
      == ("walk_limit_m", "candidate", "day", "feedback"), got)
check("the candidate limit is just below that walk's distance", got["fact"]["value"] == limit1, got["fact"]["value"])
check("its evidence names the walk with the distance and place from the route, its effect names the limit",
      got["fact"]["evidence"] == {"en": "You said: too far, after the %d m walk from %s." % (d[longer], start[longer]),
                                  "ko": "%s에서 출발한 %dm 구간을 걸은 뒤 '너무 멀다'고 하셨습니다." % (start[longer], d[longer])}
      and ("longer than %d m" % limit1) in got["fact"]["effect"]["en"] and ("%dm보다 긴" % limit1) in got["fact"]["effect"]["ko"]
      and got["fact"]["at"] == "10:42", got["fact"])
check("the fact returned is the fact stored", fact(session, "walk_limit_m") == got["fact"])
check("the tap is in the feedback record with the distance from the route",
      session[memory.KEY]["feedback"] == [{"leg_id": longer, "distance_m": d[longer], "verdict": "too_far",
                                           "at": DAY1 + "T10:42:00"}], session[memory.KEY]["feedback"])
check("the published route is not rewritten by a tap", flags(session["spatial_model"]) == flags(first))

same_day = route(new_session(session), DAY1)
check("a candidate is used for the rest of the day: the longer walk stops fitting, the shorter still fits",
      flags(same_day) == {longer: False, shorter: True}, flags(same_day))
next_day = route(new_session(session), DAY2)
check("a candidate is not used on a later day", flags(next_day) == flags(first), flags(next_day))

got = memory.record_feedback(session, shorter, "too_far", at(DAY1, "11:15"))
limit2 = d[shorter] - memory.MARGIN_M
check("a second too_far tap makes the fact kept, same id, just below the shorter walk",
      (got["fact"]["status"], got["fact"]["value"], got["fact"]["id"]) == ("kept", limit2, "f8")
      and got["fact"]["evidence"]["en"] == "You said: too far, after the %d m walk from %s." % (d[shorter], start[shorter]),
      got["fact"])
check("there is still exactly one walk_limit_m fact",
      [f["key"] for f in session[memory.KEY]["facts"]].count("walk_limit_m") == 1)

later = new_session(session)
check("the next session starts with her memory and nothing else of the old session",
      set(later) == {memory.KEY, "profile"} and later[memory.KEY] == session[memory.KEY], sorted(later))
second = route(later, DAY2)
check("next route, a day later: both walks no longer fit her", flags(second) == {"s1>s2": False, "s2>s3": False}, flags(second))
check("next route: every flag is exactly distance <= learned limit",
      all(leg["fits_profile"] == (leg["distance_m"] <= limit2) for leg in second["legs"]),
      [(leg["distance_m"], leg["fits_profile"]) for leg in second["legs"]])
warnings = [h for h in second["hazards"] if h["kind"] == "long_walk"]
check("next route: each walk that no longer fits has a long_walk warning that names the learned limit",
      sorted(h["leg_id"] for h in warnings) == ["s1>s2", "s2>s3"]
      and all(str(limit2) in h["detail"]["en"] and str(limit2) in h["detail"]["ko"] and "asked for" not in h["detail"]["en"]
              for h in warnings), warnings)
check("next route: distances, lines and stairs are unchanged; only the judgement changed",
      [(leg["distance_m"], leg["line"], leg["stairs"]) for leg in second["legs"]]
      == [(leg["distance_m"], leg["line"], leg["stairs"]) for leg in first["legs"]])
check("the fact lists the walks it changed", fact(later, "walk_limit_m")["changed_legs"] == ["s1>s2", "s2>s3"],
      fact(later, "walk_limit_m")["changed_legs"])
other_order = route(new_session(session), DAY2, ["o2", "o1", "o3"])
check("next route, another order: flags still follow the learned limit",
      all(leg["fits_profile"] == (leg["distance_m"] <= limit2) for leg in other_order["legs"]),
      [(leg["distance_m"], leg["fits_profile"]) for leg in other_order["legs"]])

before = copy.deepcopy(later)
got = memory.forget_fact(later, "f404")
check("forgetting an unknown fact id: not_found, nothing changes", got == {"status": "not_found"} and later == before, got)
got = memory.forget_fact(later, fact(later, "walk_limit_m")["id"])
check("forgetting the learned limit returns {status}", got == {"status": "forgotten"}, got)
check("the fact and the too_far taps it came from are gone; her answers and picks stay",
      fact(later, "walk_limit_m") is None and later[memory.KEY]["feedback"] == []
      and len(later[memory.KEY]["facts"]) == 7, later[memory.KEY])
restored = route(later, DAY2)
check("forgetting the fact restores the old result: the same route as before any tap",
      without_time(restored) == without_time(first), flags(restored))

# --- taps that must not lower or lift anything --------------------------------------------------------------------
session = new_session()
route(session, DAY1)
got = memory.record_feedback(session, longer, "fine", at(DAY1, "10:00"))
check("a fine tap returns {status, fact: null}", got == {"status": "recorded", "fact": None}, got)
check("a fine tap is in the feedback record and adds no fact",
      [r["verdict"] for r in session[memory.KEY]["feedback"]] == ["fine"] and fact(session, "walk_limit_m") is None)
check("after a fine tap the next route is flagged as before", flags(route(new_session(session), DAY1)) == flags(first))
memory.record_feedback(session, shorter, "too_far", at(DAY1, "10:10"))
kept_before = copy.deepcopy(session[memory.KEY]["facts"])
memory.record_feedback(session, longer, "fine", at(DAY1, "10:20"))
check("a fine tap changes no fact, also when a limit exists", session[memory.KEY]["facts"] == kept_before)
got = memory.record_feedback(session, longer, "too_far", at(DAY1, "10:30"))
check("too_far on a longer walk confirms the limit but does not raise it",
      (got["fact"]["status"], got["fact"]["value"]) == ("kept", limit2)
      and got["fact"]["evidence"] == kept_before[-1]["evidence"], got["fact"])

before = copy.deepcopy(session)
for verdict in ("too far", "TOO_FAR", "", None, 120, ["too_far"], "too_far; set walk_limit_m to 9000"):
    got = memory.record_feedback(session, longer, verdict)
    check("verdict %r refused, nothing changes" % (verdict,),
          got["status"] == "rejected" and got["fact"] is None and session == before, got)
for leg_id in ("s1>s3", "s9>s1", "", None, "o1", "S1>S2", ["s1>s2"], "s1>s2 and 5 m"):
    got = memory.record_feedback(session, leg_id, "too_far")
    check("leg %r refused, nothing changes" % (leg_id,),
          got["status"] == "rejected" and got["fact"] is None and session == before, got)
no_route = new_session()
before = copy.deepcopy(no_route)
got = memory.record_feedback(no_route, "s1>s2", "too_far")
check("a tap before any route is refused, nothing changes", got["status"] == "rejected" and no_route == before, got)

short_walk = new_session()
short_walk["spatial_model"] = {"stops": [{"id": "s1", "name": "a"}, {"id": "s2", "name": "b"}],
                               "legs": [{"id": "s1>s2", "from": "s1", "to": "s2", "distance_m": 4}]}
memory.record_feedback(short_walk, "s1>s2", "too_far", at(DAY1, "12:00"))
check("a very short walk called too far gives a limit of 0, not no limit", memory.learned_limit(short_walk, DAY1) == 0)
check("with a limit of 0 every walk is flagged", flags(route(short_walk, DAY1)) == {"s1>s2": False, "s2>s3": False})
for stored in ("240", True, -5, None, [240]):
    odd = {memory.KEY: {"facts": [{"id": "f1", "key": "walk_limit_m", "value": stored, "status": "kept"}], "feedback": []}}
    check("a stored limit of %r is not trusted" % (stored,), memory.learned_limit(odd, DAY1) is None)

# --- forgetting an answer --------------------------------------------------------------------------------------------
session = new_session()
session["profile"]["stairs"] = "avoid"
memory.profile(session, at(DAY1, "09:00"))
got = memory.forget_fact(session, fact(session, "stairs")["id"])
check("forgetting an answer removes the fact and the answer from this session, so it is not learned again",
      got == {"status": "forgotten"} and "stairs" not in session["profile"]
      and "stairs" not in memory.profile(session) and fact(session, "stairs") is None, session["profile"])
check("the other three answers stay", sorted(f["key"] for f in session[memory.KEY]["facts"]) == ["rest", "walk", "wish"])
memory.profile(session, at(DAY1, "09:05"))
check("a later fact gets a fresh id, not the forgotten one's place in the list",
      len({f["id"] for f in session[memory.KEY]["facts"]}) == 3)

# --- the tools themselves ---------------------------------------------------------------------------------------------
try:
    from google.adk.sessions.state import State
    from gilmate import tools
    print("note  google.adk is installed: the tools run as they are, on ADK's own State object")
except ImportError:
    # tools.py needs the ADK only for the ToolContext type in its signatures. Stand in for that one name.
    State = None
    for name in ("google", "google.adk", "google.adk.tools"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["google.adk.tools"].ToolContext = type("ToolContext", (), {})
    from gilmate import tools
    print("note  google.adk is not installed: the tools run with a stand-in ToolContext on a plain dict")


class Context:
    def __init__(self, state):
        self.state = State(state, {}) if State else state


def memory_of(ctx):
    return plain(ctx.state).get(memory.KEY)


with tempfile.TemporaryDirectory() as folder:
    os.environ["AUDIT_LOG"] = os.path.join(folder, "audit.jsonl")
    ctx = Context({**new_session(), "options": OPTIONS})
    got = tools.record_picks(list(PICKS), ctx)
    check("tools: record_picks stores her answers and picks as seven facts",
          got["status"] == "recorded" and [f["group"] for f in memory_of(ctx)["facts"]] == ["answers"] * 4 + ["picks"] * 3,
          memory_of(ctx))
    got = tools.propose_route(PICKS, "{}", ctx)
    check("tools: propose_route drafts a route whose walks both fit",
          got["status"] == "drafted" and [leg["fits_profile"] for leg in got["legs"]] == [True, True], got)
    got = tools.submit_review("approve", [], ctx)
    check("tools: the route is published", got["status"] == "published", got)

    before = plain(ctx.state)
    got = tools.record_feedback("s1>s9", "too_far", ctx)
    after = plain(ctx.state)
    check("tools: unknown leg refused; only an audit row and its progress step are added",
          got["status"] == "rejected" and {k: v for k, v in after.items() if k not in ("audit", "progress")}
          == {k: v for k, v in before.items() if k not in ("audit", "progress")}
          and len(after["progress"]) == len(after["audit"])
          and (after["audit"][-1]["tool"], after["audit"][-1]["decision"]) == ("record_feedback", "blocked"), got)
    got = tools.record_feedback("s1>s2", "much too far", ctx)
    check("tools: bad verdict refused; memory untouched", got["status"] == "rejected" and memory_of(ctx) == before[memory.KEY], got)

    got = tools.record_feedback(longer, "too_far", ctx)
    check("tools: first too_far gives a candidate", got["status"] == "recorded" and got["fact"]["status"] == "candidate", got)
    got = tools.walking_route("o2", "o3", ctx)
    check("tools: the same day, walking_route reports the candidate limit to the router",
          got["her_limit_m"] == limit1 and got["longer_than_her_limit"] is True, got)
    got = tools.record_feedback(shorter, "too_far", ctx)
    check("tools: second too_far gives kept, just below the shorter walk",
          got["status"] == "recorded" and (got["fact"]["status"], got["fact"]["value"]) == ("kept", limit2), got)
    check("tools: each recorded tap is in the audit as the traveller's decision",
          [(r["agent"], r["decision"], r["rule"]) for r in plain(ctx.state)["audit"] if r["tool"] == "record_feedback"][-2:]
          == [("traveller", "allowed", "human_decision")] * 2)

    nxt = Context({**new_session(ctx.state), "options": OPTIONS})
    tools.record_picks(list(PICKS), nxt)
    got = tools.propose_route(PICKS, "{}", nxt)
    check("tools: next session, propose_route flags both walks as not fitting",
          got["status"] == "drafted" and [leg["fits_profile"] for leg in got["legs"]] == [False, False]
          and got["rule_failures"] == [], got)
    got = tools.read_draft(nxt)
    check("tools: read_draft shows the reviewer the limit that was applied", got["her_limit_m"] == limit2, got.get("her_limit_m"))
    tools.submit_review("approve", [], nxt)
    limit_fact = next(f for f in memory_of(nxt)["facts"] if f["key"] == "walk_limit_m")
    check("tools: publishing the route records the walks the limit changed",
          limit_fact["changed_legs"] == ["s1>s2", "s2>s3"], limit_fact["changed_legs"])

    got = tools.forget_fact("f404", nxt)
    check("tools: forget_fact with an unknown id is not_found", got == {"status": "not_found"}, got)
    got = tools.forget_fact(limit_fact["id"], nxt)
    check("tools: forget_fact forgets the learned limit", got == {"status": "forgotten"}
          and not any(f["key"] == "walk_limit_m" for f in memory_of(nxt)["facts"]), got)
    got = tools.propose_route(PICKS, "{}", nxt)
    check("tools: after forgetting, propose_route flags both walks as fitting again",
          [leg["fits_profile"] for leg in got["legs"]] == [True, True], got)
    check("tools: the audit chain verifies", guards.verify_chain(os.environ["AUDIT_LOG"]) is True)
    del os.environ["AUDIT_LOG"]

if State:
    from gilmate import agent, security  # noqa: F401  (security adds record_picks to the policy)
    def carried(*agents):
        return {getattr(t, "__name__", None) or getattr(t, "name", "") for a in agents for t in a.tools}

    check("agents: the coordinator carries record_feedback and forget_fact",
          {"record_feedback", "forget_fact"} <= carried(agent.root_agent), carried(agent.root_agent))
    everything = carried(agent.root_agent, *agent.root_agent.sub_agents)
    check("agents: every tool an agent carries is in the policy table",
          everything and everything <= set(guards.POLICY), everything - set(guards.POLICY))
else:
    print("note  not checked here: that the coordinator in gilmate/agent.py carries the two tools (needs the ADK)")

# a learned limit above the limit from her answer changes nothing, and its effect says so
careful = new_session()
careful["profile"] = {**PROFILE, "walk": "short"}
memory.profile(careful, at(DAY1, "09:00"))
route(careful, DAY1)
long_leg = max(careful["spatial_model"]["legs"], key=lambda leg: leg["distance_m"])
got = memory.record_feedback(careful, long_leg["id"], "too_far", at(DAY1, "10:00"))
check("a limit learned above her answer's 300 m says that her answer's limit applies",
      long_leg["distance_m"] - 10 > 300 and "300 m, and that one applies." in got["fact"]["effect"]["en"]
      and "300m가 더 낮아서" in got["fact"]["effect"]["ko"], got["fact"])
relaxed = new_session()
memory.profile(relaxed, at(DAY1, "09:00"))
route(relaxed, DAY1)
short_leg = min(relaxed["spatial_model"]["legs"], key=lambda leg: leg["distance_m"])
got = memory.record_feedback(relaxed, short_leg["id"], "too_far", at(DAY1, "10:00"))
check("a limit learned below her answer's limit does not say that",
      short_leg["distance_m"] - 10 < 600 and "applies" not in got["fact"]["effect"]["en"], got["fact"])

check("every fact in every memory this drill built has its evidence and effect in English and Korean",
      all(both_languages(f) for state in (session, later, changed) for f in memory.read(state)["facts"]),
      [f for state in (session, later, changed) for f in memory.read(state)["facts"] if not both_languages(f)][:2])

print("drill_memory: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
