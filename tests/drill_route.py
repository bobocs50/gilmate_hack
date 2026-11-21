"""Drill: the route draft keeps the router's advice, counts reviews, and tells a promise from what the map shows.

Found by the first real run: advice keyed with option ids ("o3>o1") was dropped without a word, "The map shows
no stairs on this path" was refused as a promise, and the page said the checker went over the route three times
when it had reviewed it twice. Uses the map extract in data/. No network, no key, no model.

Run from the repo folder: python3 tests/drill_route.py
"""
import json
import os
import sys
import tempfile
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ["AUDIT_LOG"] = os.path.join(tempfile.mkdtemp(prefix="gilmate-drill-"), "audit.jsonl")

from gilmate import osm  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


for text in ("No stairs on this path.", "An easy walk with no stairs.", "This way is step-free.", "Fully accessible.",
             "The map is good. The path is step-free.", "It is wheelchair accessible, the map aside."):
    check("a promise is refused: %r" % text, osm.overclaims(text) is True)
for text in ("No stairs mapped on this path.", "The map shows no stairs on this path (none mapped).",
             "297 m. Stairs on the path: none mapped.", "No stairs are mapped here.", "The map lists no stairs.",
             "There are stairs on this path.", "", None):
    check("what the map shows is accepted: %r" % (text,), osm.overclaims(text) is False)

try:
    from gilmate import tools
except ImportError:
    tools = None
    print("note  not checked here: propose_route and submit_review in gilmate/tools.py (need the ADK)")
if tools:
    ON_MAP = osm.load()["places"]
    PLACES = [("o1", "see", "node/597685675"), ("o2", "shop", "node/11034183301"), ("o3", "eat", "node/4360904389")]
    options = [{"id": oid, "category": cat, "name": ON_MAP[ref]["name"], "summary": {"en": "", "ko": ""}, "facts": [],
                "place": {k: ON_MAP[ref][k] for k in ("lat", "lon", "osm_id", "access")}} for oid, cat, ref in PLACES]
    state = {"profile": {"walk": "medium", "stairs": "ok", "rest": "sometimes", "food": "sushi", "wish": None, "language": "ko"},
             "options": options, "picks": ["o1", "o2", "o3"], "rounds": 0}
    context = types.SimpleNamespace(state=state)
    mine = {"en": "A short walk; the map shows no stairs.", "ko": "짧은 길입니다."}

    got = tools.propose_route(["o2", "o1", "o3"], json.dumps({"o2>o1": mine, "s2>s3": mine, "o9>o1": mine, "s1>s2x": "text"}), context)
    notes = {leg["id"]: leg["note"] for leg in state["draft"]["legs"]}
    check("advice keyed with option ids lands on the walk between those stops", notes["s1>s2"] == mine, notes)
    check("advice keyed with walk ids is kept, and honest words about the map are no rule failure",
          notes["s2>s3"] == mine and got["rule_failures"] == [], got)
    check("advice that fits no walk is reported back, not dropped silently", sorted(got["notes_not_used"]) == ["o9>o1", "s1>s2x"], got)
    got = tools.propose_route(["o2", "o1", "o3"], "{}", context)
    check("without advice the system writes it and says so", got["notes_written_by_the_system_for"] == ["s1>s2", "s2>s3"]
          and all("m on foot" in leg["note"]["en"] for leg in state["draft"]["legs"]), got)
    got = tools.propose_route(["o2", "o1", "o3"], json.dumps({"s1>s2": {"en": "No stairs here.", "ko": "계단 없음"}}), context)
    check("a promise in the advice is a rule failure and the system's words replace it",
          got["rule_failures"] == ["note.overclaims:s1>s2", ][:1] and "No stairs here" not in state["draft"]["legs"][0]["note"]["en"], got)

    got = tools.propose_route(["o3", "o1", "o2"], "{}", context)
    check("the meal as the first stop is a rule failure when the reverse order is as short",
          [f.split(":")[0] for f in got["rule_failures"]] == ["order.food_first"], got)
    got = tools.propose_route(["o2", "o1", "o3"], "{}", context)
    check("the same stops ending with the meal pass", got["rule_failures"] == [], got)
    got = tools.propose_route(["o1", "o3", "o2"], "{}", context)
    check("the meal in the middle passes", got["rule_failures"] == [], got)
    tools.propose_route(["o2", "o1", "o3"], json.dumps({"s1>s2": {"en": "No stairs here.", "ko": "계단 없음"}}), context)

    check("many drafts are still review round 1: drafting does not count as a review", got["review_round"] == 1, got)
    got = tools.submit_review("approve", [], context)
    check("a draft with a rule failure cannot be approved; it goes back after review 1", got["status"] == "sent_back" and got["round"] == 1, got)
    tools.propose_route(["o2", "o1", "o3"], "{}", context)
    tools.propose_route(["o2", "o1", "o3"], "{}", context)
    got = tools.submit_review("approve", [], context)
    check("the second review publishes the route as verified and counts 2 reviews, however many drafts there were",
          got == {"status": "published", "review": {"status": "verified", "rounds": 2, "removed": []}}
          and state["spatial_model"]["review"]["rounds"] == 2, got)
    state["rounds"] = 0
    tools.propose_route(["o2", "o1", "o3"], "{}", context)
    tools.submit_review("revise", ["a"], context)
    tools.propose_route(["o2", "o1", "o3"], "{}", context)
    got = tools.submit_review("revise", ["b"], context)
    check("a second 'revise' publishes as partly unverified with the open point listed",
          got["status"] == "published" and got["review"]["status"] == "partly_unverified" and got["review"]["rounds"] == 2
          and [r["what"] for r in got["review"]["removed"]] == ["b"], got)

print("drill_route: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
