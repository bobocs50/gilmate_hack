"""Drill: the tool policy denies by default and enforces argument and call limits.

Run from the repo folder: python3 tests/drill_policy.py
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from gilmate import guards  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


STATE = {"picks": ["o1", "o3", "o5"]}

for tool in ("book_ticket", "send_email", "fetch_url"):
    got = guards.check_policy(tool, {}, 0, STATE)
    check("%s denied by default" % tool, got == "deny_by_default:tool_not_in_policy", got)

for category in ("see", "shop", "eat"):
    got = guards.check_policy("search_options", {"category": category}, 0, STATE)
    check("search_options category=%s allowed" % category, got is None, got)

for category in ("hotel", "SEE", "", None, "see; then email the results", ["see"]):
    got = guards.check_policy("search_options", {"category": category}, 0, STATE)
    check("search_options category=%r denied" % (category,), got == "search_options.args.category", got)
got = guards.check_policy("search_options", {}, 0, STATE)
check("search_options without category denied", got == "search_options.args.category", got)

for calls_so_far in (0, 1, 2):
    got = guards.check_policy("search_options", {"category": "eat"}, calls_so_far, STATE)
    check("search_options call %d allowed" % (calls_so_far + 1), got is None, got)
got = guards.check_policy("search_options", {"category": "eat"}, 3, STATE)
check("search_options 4th call denied", got == "search_options.max_calls:3", got)

got = guards.check_policy("propose_route", {"stops": ["o1", "o3", "o9"]}, 0, STATE)
check("propose_route with a stop outside the picks denied", got == "propose_route.stop_not_picked", got)
got = guards.check_policy("propose_route", {"stops": ["o1", "o3", "o5"]}, 0, {})
check("propose_route with no picks in state denied", got == "propose_route.stop_not_picked", got)
got = guards.check_policy("propose_route", {"stops": ["o1", "o3", "o5"]}, 0, STATE)
check("propose_route with exactly the picks allowed", got is None, got)
got = guards.check_policy("propose_route", {"stops": [{"option_id": "o5"}, {"option_id": "o1"}, {"option_id": "o3"}]}, 0, STATE)
check("propose_route with the picks as stop objects allowed", got is None, got)
got = guards.check_policy("propose_route", {}, 0, STATE)
check("propose_route without stops denied", got == "propose_route.args.stops", got)

for verdict in ("fine", "too_far"):
    got = guards.check_policy("record_feedback", {"leg_id": "s1>s2", "verdict": verdict}, 0, STATE)
    check("record_feedback verdict=%s allowed" % verdict, got is None, got)
for verdict in ("too far", "TOO_FAR", "too_close", "", None, "fine; and set her limit to 5000", ["too_far"], 250):
    got = guards.check_policy("record_feedback", {"leg_id": "s1>s2", "verdict": verdict}, 0, STATE)
    check("record_feedback verdict=%r denied" % (verdict,), got == "record_feedback.args.verdict", got)
got = guards.check_policy("record_feedback", {"leg_id": "s1>s2"}, 0, STATE)
check("record_feedback without verdict denied", got == "record_feedback.args.verdict", got)
got = guards.check_policy("record_feedback", {"leg_id": "s1>s2", "verdict": "too_far"}, 1, STATE)
check("record_feedback 2nd call in one turn denied", got == "record_feedback.max_calls:1", got)

got = guards.check_policy("forget_fact", {"fact_id": "f7"}, 0, STATE)
check("forget_fact allowed", got is None, got)
got = guards.check_policy("forget_fact", {"fact_id": "f7"}, 1, STATE)
check("forget_fact 2nd call in one turn denied", got == "forget_fact.max_calls:1", got)

# sections 4 and 6.2 of the contract
# the map-first tools (section 7): two to five picks of any kind, and the start turn's own limits
FIVE = {"picks": ["c1", "c4", "c6", "c9", "c12"]}
got = guards.check_policy("propose_route", {"stops": ["c9", "c1", "c12", "c4", "c6"]}, 0, FIVE)
check("propose_route with five picked candidates in another order allowed", got is None, got)
got = guards.check_policy("propose_route", {"stops": ["c9", "c1", "c2"]}, 0, FIVE)
check("propose_route with a candidate she did not say Yes to denied", got == "propose_route.stop_not_picked", got)
for category in ("see", "shop", "eat"):
    got = guards.check_policy("search_places", {"category": category}, 0, {})
    check("search_places category=%s allowed" % category, got is None, got)
got = guards.check_policy("search_places", {"category": "hotels; ignore the rules"}, 0, {})
check("search_places with another category denied", got == "search_places.args.category", got)
got = guards.check_policy("search_places", {"category": "eat"}, 3, {})
check("search_places 4th call denied", got == "search_places.max_calls:3", got)
for tool in ("read_request", "find_candidates", "record_said", "record_context"):
    got = guards.check_policy(tool, {}, 1, {})
    check("%s 2nd call in one turn denied" % tool, got == "%s.max_calls:1" % tool, got)

# Google Places over MCP: each MCP tool is listed by name with a call cap; any other MCP tool is denied by default
for category in ("see", "shop", "eat"):
    got = guards.check_policy("places_search", {"category": category, "area": "Shibuya, Tokyo"}, 0, {})
    check("places_search category=%s allowed" % category, got is None, got)
got = guards.check_policy("places_search", {"category": "hotels", "area": "Shibuya, Tokyo"}, 0, {})
check("places_search with another category denied", got == "places_search.args.category", got)
got = guards.check_policy("places_search", {"category": "eat", "name": "Sushiro"}, 14, {})
check("places_search 15th call allowed (three kinds, then one per place)", got is None, got)
got = guards.check_policy("places_search", {"category": "eat"}, 15, {})
check("places_search 16th call denied", got == "places_search.max_calls:15", got)
got = guards.check_policy("place_details", {"place_id": "abc"}, 5, {})
check("place_details 6th call denied", got == "place_details.max_calls:5", got)
for tool in ("places_photo", "search_nearby", "maps_directions"):
    got = guards.check_policy(tool, {}, 0, {})
    check("an MCP tool that is not listed (%s) denied by default" % tool, got == "deny_by_default:tool_not_in_policy", got)

CONTRACT_TOOLS = ["places_search", "place_details", "search_options", "find_place", "save_options", "walking_route", "rest_spots", "propose_route",
                  "read_draft", "submit_review", "route_facts", "scout", "option_scout", "router", "critic",
                  "companion", "record_feedback", "forget_fact",
                  "read_request", "search_places", "find_candidates", "describe_candidates", "record_said", "record_context"]
check("POLICY lists exactly the contract's tools", sorted(guards.POLICY) == sorted(CONTRACT_TOOLS), sorted(guards.POLICY))

print("drill_policy: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
