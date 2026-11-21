"""Drill: the place lookup on the map, and the places named in the web searches.

Found by the first real run: the searches returned restaurants that are not on the map, and "Sushizanmai" was
not found because the map spells it "Sushizammai". Uses the map extract in data/. No network, no key, no model.

Run from the repo folder: python3 tests/drill_search.py
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from gilmate import osm  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


def found(name, category):
    return [m["name"] for m in osm.find_place(name, category)["matches"]]


for kind, names in osm.SEARCH_HINTS.items():
    for name in names:
        got = found(name, "see" if kind == "see" else "eat")
        check("the place named in the %s search is on the map: %s" % (kind, name), bool(got), got)

for name, category, want in (("Sushizanmai", "eat", "Sushizammai"), ("Sushi Zanmai", "eat", "Sushizammai"),
                             ("Sushi no Midori", "eat", "Sushi-no-Midori"), ("Loft Shibuya", "shop", "Loft"),
                             ("Tokyu Hands Shibuya", "shop", "Hands"), ("Hachiko", "see", "Hachiko Memorial Statue"),
                             ("SHIBUYA SKY", "see", "Shibuya Sky"), ("Sushi Tokyo Ten", "eat", "Ten")):
    got = found(name, category)
    check("find_place(%r) finds %s first" % (name, want), got[:1] == [want], got)

# Found by the demo: the Scramble Crossing was not offered. The map files it as a junction named "渋谷駅前", with
# "Shibuya Scramble Crossing", "渋谷スクランブル交差点" and "Shibuya Crossing" as its other names.
for name in ("Shibuya Crossing", "Shibuya Scramble Crossing", "shibuya scramble crossing", "渋谷スクランブル交差点", "渋谷駅前"):
    got = found(name, "see")
    check("find_place(%r) finds the crossing first, by any name the map has for it" % name,
          got[:1] == ["Shibuya Scramble Crossing"], got)

check("a name inside another word is no match: Tenkaippin is not Ten", "Ten" not in found("Tenkaippin", "eat"),
      found("Tenkaippin", "eat"))
for name, category in (("Sushi Sublime", "eat"), ("Ajuuta", "eat"), ("Tokyo Skytree", "see"), ("Sushi", "eat"), ("", "eat")):
    got = found(name, category)
    check("a place that is not on the map stays not found: %r" % name, len(got) == 0 or name == "Sushi", got)
check("the category is respected: Loft is a shop, not a place to eat", found("Loft", "eat") == [], found("Loft", "eat"))

try:
    from gilmate import tools
except ImportError:
    tools = None
    print("note  not checked here: the query strings in gilmate/tools.py (needs the ADK)")
if tools:
    for category, food, count in (("see", "sushi", 2), ("shop", "sushi", 1), ("eat", "sushi", 2), ("eat", "ramen", 2),
                                  ("eat", "surprise", 2), ("eat", None, 2)):
        got = tools.queries(category, food)
        check("%s has %d search(es) for food=%s, all about Shibuya, none with an unfilled blank" % (category, count, food),
              len(got) == count and all("Shibuya" in q and "{" not in q for q in got), got)
    check("her food answer is in both food searches", all("sushi" in q for q in tools.queries("eat", "sushi"))
          and all("ramen" in q for q in tools.queries("eat", "ramen")))
    check("the second food search names the map's places for her answer",
          all(name in tools.queries("eat", "sushi")[1] for name in osm.SEARCH_HINTS["sushi"])
          and all(name in tools.queries("eat", "surprise")[1] for name in osm.SEARCH_HINTS["other"]))

print("drill_search: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
