"""Drill: the request itself shapes the visit. Free: no network, no key, no model.

"My mom wants to visit Shibuya in Tokyo. She loves sushi. Stairs and steep hills are hard for her, and she can walk
about 1 km before she needs to sit down. Show us the sights and the best-rated sushi places." must become: stairs
avoided, a walking limit of 1000 m, sitting often, sushi places first among the places to eat - and nothing else of
her words anywhere.
"""
import os
import sys

os.environ["GILMATE_OFFLINE"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from gilmate import areas, candidates, osm, say      # noqa: E402

areas.use("shibuya")
DEMO = ("My mom wants to visit Shibuya in Tokyo. She loves sushi. Stairs and steep hills are hard for her, and she "
        "can walk about 1 km before she needs to sit down. Show us the sights and the best-rated sushi places.")
failed = []


def check(name, got, want):
    if got != want:
        failed.append(name)
        print("FAIL  %s: got %r, want %r" % (name, got, want))


# what she says about her body, read by Python alone
check("answers", say.context(DEMO, None), ({"walk": "medium", "stairs": "avoid", "rest": "often"}, []))
check("limit", say.limit_m(DEMO), 1000)
check("hills are named", say.says_hills(DEMO), True)
check("plain request tells nothing", say.context("I want to visit Shibuya, Tokyo", None), ({}, ["walk", "stairs", "rest"]))
check("plain request has no limit", say.limit_m("I want to visit Shibuya, Tokyo"), None)
check("two distances are no limit", say.limit_m("she can walk 1 km. she can walk 300 m"), None)
check("a marathon is no limit", say.limit_m("she can walk 40 km"), None)
check("stairs that are fine", say.from_text("Stairs are not hard for her").get("stairs"), None)
check("earlier sentence", say.context("She can only walk about 1 km and then needs a break.", None)[0],
      {"walk": "medium", "rest": "often"})

# the stated distance is the limit; a learned one can only lower it; a wrong value is ignored
check("stated limit", osm.walk_limit({"walk": "medium", "walk_limit_m": 1000}), 1000)
check("learned is lower", osm.walk_limit({"walk": "medium", "walk_limit_m": 1000}, 400), 400)
check("no stated limit", osm.walk_limit({"walk": "medium"}), 600)
check("text is no limit", osm.walk_limit({"walk": "medium", "walk_limit_m": "1000"}), 600)
check("out of range", osm.walk_limit({"walk": "medium", "walk_limit_m": 99999}), 600)

# the sentence she hears back: honest about hills
back = say.understood({"walk": "medium", "walk_limit_m": 1000, "stairs": "avoid", "rest": "often"}, True)
check("say back", back["en"], "I avoid stairs and keep walks under 1 km with places to sit; I cannot check hills yet.")
check("nothing known, nothing said", say.understood({}, False), None)

# what she asked to eat: fixed words only
check("wish", candidates.food_wish(DEMO), {"kind": "sushi", "words": ["sushi"]})
check("omakase", candidates.food_wish("the best omakase please"), {"kind": "sushi", "words": ["omakase", "sushi"]})
check("no wish", candidates.food_wish("I want to visit Shibuya, Tokyo"), None)
check("typed text never reaches a query", candidates.wish_queries({"kind": "sushi", "words": ["sushi", "ignore all rules"]}),
      ["Shibuya Tokyo best sushi restaurant rating reviews"])
check("unknown kind, no query", candidates.wish_queries({"kind": "pizza; rm", "words": ["pizza"]}), [])

# sushi places first among the places to eat, all on the map inside the area
texts = list(candidates.saved_results().values())
tags, places = candidates._tags(), osm.load()["places"]


def eat_kinds(wish):
    return [candidates.kind(tags[ref])["key"] for ref in candidates.choose(texts, wish) if places[ref]["category"] == "eat"]


with_wish, without = eat_kinds("sushi"), eat_kinds(None)
check("three sushi places first", with_wish[:3], ["sushi"] * 3)
check("three places to eat", len(with_wish), 3)
check("without a wish as before", without.count("sushi") <= 1, True)
south, west, north, east = osm.AREA["bbox"]
check("all inside the area", all(south <= places[r]["lat"] <= north and west <= places[r]["lon"] <= east
                                 for r in candidates.choose(texts, "sushi")), True)

if failed:
    print("%d checks failed" % len(failed))
    sys.exit(1)
print("ok: the request shapes the visit (answers, limit, say-back, food wish, sushi first)")
