"""Drill: every fact of an option must be backed by a quote from a result that was seen.

Run from the repo folder: python3 tests/drill_grounding.py
"""
import copy
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


URL = "https://visit.example/shibuya-sky"
SEEN = {URL: "Shibuya Sky is an observation deck on the 46th floor.\n  Adults pay 2,200 yen.   Open 10:00 to 22:30, last entry 21:20."}

GOOD = {
    "id": "o1", "category": "see", "name": "Shibuya Sky",
    "facts": [
        {"label": "price", "value": "2200 yen", "source_url": URL, "quote": "adults pay 2,200 yen."},
        {"label": "hours", "value": "10:00-22:30", "source_url": URL, "quote": "Open 10:00 to 22:30"},
        {"label": "kind", "value": "observation deck", "source_url": URL, "quote": "Shibuya Sky is an observation deck"},
    ],
}

got = guards.ground_option(GOOD, SEEN)
check("correct option passes (case, whitespace and 2,200 vs 2200 folded)", got == [], got)

bad = copy.deepcopy(GOOD)
bad["facts"][0]["source_url"] = "https://never-searched.example/"
got = guards.ground_option(bad, SEEN)
check("unseen source url fails", len(got) == 1 and got[0].startswith("source_not_seen:"), got)

bad = copy.deepcopy(GOOD)
bad["facts"][0]["quote"] = "Adults pay 1,800 yen."
bad["facts"][0]["value"] = "1800 yen"
got = guards.ground_option(bad, SEEN)
check("quote not in the source fails", len(got) == 1 and got[0].startswith("quote_not_found:"), got)

bad = copy.deepcopy(GOOD)
bad["facts"][0]["value"] = "1800 yen"
got = guards.ground_option(bad, SEEN)
check("price whose digits are not in the quote fails", len(got) == 1 and got[0].startswith("value_not_in_quote:"), got)

bad = copy.deepcopy(GOOD)
bad["facts"][0]["quote"] = ""
got = guards.ground_option(bad, SEEN)
check("empty quote fails", len(got) == 1 and got[0].startswith("quote_not_found:"), got)

for tags, want in (({}, "unknown"), ({"wheelchair": "yes"}, "yes"), ({"wheelchair": "limited"}, "limited"),
                   ({"wheelchair": "no"}, "no"), ({"wheelchair": "designated"}, "unknown"), (None, "unknown")):
    got = guards.access_label(tags)
    check("access_label(%r) == %r" % (tags, want), got == want, got)

print("drill_grounding: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
