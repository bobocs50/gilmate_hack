"""Drill: the route note says every fact of the spatial model once, in both languages, and nothing else.

A model with every state (each access value, a routed walk with and without stairs, a leg with no mapped path,
benches, warnings, each review status) must give exactly the expected sentences. No number may appear that the
model does not hold, nothing a model wrote (a walk's advice, a stop's background, the critic's open points) may
appear, and what is missing must be said as unknown, never as safe. No network, no key, no model.

Run from the repo folder: python3 tests/drill_note.py
"""
import copy
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from gilmate import note, osm  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


def stop(i, name, access, category="see"):
    return {"id": "s%d" % i, "option_id": "c%d" % i, "order": i, "category": category, "name": name,
            "lat": 35.66, "lon": 139.70, "access": access,
            "background": {"en": "BACKGROUND-WORDS 4242 written by a model.", "ko": "모델이쓴배경 4242"}, "sources": []}


def leg(a, b, metres, kind, stairs, fits=True):
    return {"id": "s%d>s%d" % (a, b), "from": "s%d" % a, "to": "s%d" % b, "distance_m": metres, "line": [],
            "kind": kind, "stairs": stairs, "fits_profile": fits,
            "note": {"en": "ADVICE-WORDS 9191 written by the router.", "ko": "모델이쓴조언 9191"}}


def hazard(i, kind, en, ko, leg_id=None, stop_id=None):
    return {"id": "h%d" % i, "leg_id": leg_id, "stop_id": stop_id, "kind": kind, "lat": 35.66, "lon": 139.70,
            "detail": {"en": en, "ko": ko}, "source": "computed"}


def bench(i, leg_id, off):
    return {"id": "b%d" % i, "leg_id": leg_id, "lat": 35.66, "lon": 139.70, "off_route_m": off, "source": "osm:node/1"}


FULL = {
    "area": {"name": "Shibuya, Tokyo", "bbox": [35.657, 139.6975, 35.6632, 139.705]},
    # given out of order on purpose: the note follows `order`
    "stops": [stop(3, "Ten", "no", "eat"), stop(1, "Loft", "yes", "shop"), stop(2, "Shibuya Sky", "limited"),
              stop(4, "Hachiko", "unknown"), stop(5, "Miyashita Park", "unknown")],
    "legs": [leg(1, 2, 736, "routed", "none_mapped", fits=False), leg(2, 3, 297, "routed", "some", fits=False),
             leg(3, 4, 412, "straight_line", "unknown"), leg(4, 5, 158, "routed", "unknown")],
    "hazards": [
        hazard(1, "unknown_access", "The map has no accessibility information for the entrance of Hachiko.",
               "Hachiko 입구의 접근성 정보가 지도에 없습니다.", stop_id="s4"),
        hazard(2, "long_walk", "This walk is 736 m, longer than the 600 m you asked for.",
               "이 구간은 736m로, 원하신 600m보다 깁니다.", leg_id="s1>s2"),
        hazard(3, "steps", "Stairs on this path, 12 steps.", "이 길에 계단이 있습니다, 12계단.", leg_id="s2>s3"),
        hazard(4, "steps", "Stairs on this path, number of steps not recorded.",
               "이 길에 계단이 있습니다, 계단 수는 기록되어 있지 않습니다.", leg_id="s2>s3"),
        hazard(5, "unknown_access", "No mapped path. The distance is a straight line and stairs are unknown.",
               "지도에 길이 없습니다. 거리는 직선 거리이며 계단 여부는 알 수 없습니다.", leg_id="s3>s4"),
    ],
    "benches": [bench(1, "s1>s2", 31), bench(2, "s1>s2", 8), bench(3, "s3>s4", 22)],
    "review": {"status": "partly_unverified", "rounds": 2,
               "removed": [{"what": "CRITIC-WORDS 7373 the second walk looks risky", "why": "not confirmed within two rounds"}]},
    "generated_at": "2026-11-21T11:03:11",
}

EXPECTED_EN = [
    "Your route, in this order: Loft, Shibuya Sky, Ten, Hachiko, Miyashita Park.",
    "Loft: the map lists wheelchair access at the entrance.",
    "Loft to Shibuya Sky: 736 m on foot, no stairs mapped.",
    "This walk is 736 m, longer than the 600 m you asked for.",
    "Benches mapped near this walk, off the path by: 8 m, 31 m.",
    "Shibuya Sky: the map lists only limited wheelchair access at the entrance.",
    "Shibuya Sky to Ten: 297 m on foot.",
    "Stairs on this path, 12 steps.",
    "Stairs on this path, number of steps not recorded.",
    "No bench is mapped near this walk.",
    "Ten: the map lists no wheelchair access at the entrance.",
    "Ten to Hachiko: not routed, the map has no path between them.",
    "The straight-line distance is 412 m and stairs are unknown.",
    "Benches mapped near the two places, away by: 22 m.",
    "The map has no accessibility information for the entrance of Hachiko.",
    "Hachiko to Miyashita Park: 158 m on foot, stairs unknown.",
    "No bench is mapped near this walk.",
    "The map has no accessibility information for the entrance of Miyashita Park.",
    "The checker did not confirm every point of this route.",
]
EXPECTED_KO = [
    "경로는 이 순서입니다: Loft, Shibuya Sky, Ten, Hachiko, Miyashita Park.",
    "Loft: 지도에 입구가 휠체어로 들어갈 수 있다고 표시되어 있습니다.",
    "Loft에서 Shibuya Sky까지: 걸어서 736m, 지도에 표시된 계단은 없습니다.",
    "이 구간은 736m로, 원하신 600m보다 깁니다.",
    "이 길 가까이 지도에 표시된 벤치가 있습니다. 길에서 떨어진 거리: 8m, 31m.",
    "Shibuya Sky: 지도에 입구가 휠체어로는 일부만 들어갈 수 있다고 표시되어 있습니다.",
    "Shibuya Sky에서 Ten까지: 걸어서 297m.",
    "이 길에 계단이 있습니다, 12계단.",
    "이 길에 계단이 있습니다, 계단 수는 기록되어 있지 않습니다.",
    "이 길 가까이에는 지도에 표시된 벤치가 없습니다.",
    "Ten: 지도에 입구가 휠체어로 들어갈 수 없다고 표시되어 있습니다.",
    "Ten에서 Hachiko까지: 지도에 길이 없어 경로를 찾지 못했습니다.",
    "직선 거리는 412m이고 계단 여부는 알 수 없습니다.",
    "두 장소 가까이 지도에 표시된 벤치가 있습니다. 떨어진 거리: 22m.",
    "Hachiko 입구의 접근성 정보가 지도에 없습니다.",
    "Hachiko에서 Miyashita Park까지: 걸어서 158m, 계단 여부는 알 수 없습니다.",
    "이 길 가까이에는 지도에 표시된 벤치가 없습니다.",
    "Miyashita Park 입구의 접근성 정보가 지도에 없습니다.",
    "검토자가 이 경로의 모든 내용을 확인하지는 못했습니다.",
]


def numbers(text):
    return set(re.findall(r"\d+", text))


def held(model):
    """Every number the note may use: distances, bench distances, and the warnings Python wrote into the model."""
    out = set()
    for row in model.get("legs", []):
        out |= numbers(str(row.get("distance_m")))
    for row in model.get("benches", []):
        out |= numbers(str(row.get("off_route_m")))
    for row in model.get("hazards", []):
        out |= numbers(json.dumps(row.get("detail"), ensure_ascii=False))
    for row in model.get("stops", []):
        out |= numbers(str(row.get("name")))
    return out


# --- every state, exactly ---------------------------------------------------------------------------------
before = copy.deepcopy(FULL)
got = note.route_note(FULL)
check("the model is not changed by writing the note", FULL == before)
check("the note is {en, ko}, nothing else", sorted(got) == ["en", "ko"], sorted(got))
en, ko = got["en"].split("\n"), got["ko"].split("\n")
check("English: exactly the expected sentences, in order, nothing else", en == EXPECTED_EN,
      [x for x in en if x not in EXPECTED_EN] + [x for x in EXPECTED_EN if x not in en])
check("Korean: exactly the expected sentences, in order, nothing else", ko == EXPECTED_KO,
      [x for x in ko if x not in EXPECTED_KO] + [x for x in EXPECTED_KO if x not in ko])
check("each walk's distance is said once", all(sum(1 for x in en if x.startswith(a) and (" %d m" % m) in x) == 1
      for a, m in (("Loft to", 736), ("Shibuya Sky to", 297), ("The straight-line", 412), ("Hachiko to", 158))), en)
check("each warning is said once", all(en.count(h["detail"]["en"]) == 1 for h in FULL["hazards"][:4]), en)
check("the leg with no mapped path is worded as not routed, and its 'no mapped path' warning is not said again",
      sum("not routed" in x for x in en) == 1 and not any("No mapped path" in x for x in en), en)
check("stairs on a walk are said by the stairs warnings alone, not twice", not any("with stairs" in x for x in en), en)
check("no number that the model does not hold (English)", numbers(got["en"]) <= held(FULL), numbers(got["en"]) - held(FULL))
check("no number that the model does not hold (Korean)", numbers(got["ko"]) <= held(FULL), numbers(got["ko"]) - held(FULL))
check("the same numbers in both languages", numbers(got["en"]) == numbers(got["ko"]), numbers(got["en"]) ^ numbers(got["ko"]))
for words in ("ADVICE-WORDS", "9191", "BACKGROUND-WORDS", "4242", "CRITIC-WORDS", "7373", "risky", "모델이쓴"):
    check("nothing a model wrote is in the note: %s" % words, words not in got["en"] and words not in got["ko"])
check("no sentence promises no stairs or full access", not any(osm.OVERCLAIM.search(x) for x in en),
      [x for x in en if osm.OVERCLAIM.search(x)])
rows = note.lines(FULL)
check("every sentence says what it is about: the route, a stop, a walk or the review",
      all(r["about"] in {"route", "review"} | {s["id"] for s in FULL["stops"]} | {x["id"] for x in FULL["legs"]} for r in rows),
      [r["about"] for r in rows])
check("the note is the lines joined, one sentence per line",
      got["en"] == "\n".join(r["en"] for r in rows) and got["ko"] == "\n".join(r["ko"] for r in rows))

# --- review status ----------------------------------------------------------------------------------------
for status, words in (("verified", "The checker confirmed this route."),
                      ("partly_unverified", "The checker did not confirm every point of this route."),
                      (None, "This route has not been checked."), ("approved by me", "This route has not been checked.")):
    m = copy.deepcopy(FULL)
    m["review"] = {"status": status, "rounds": 1, "removed": []} if status else {}
    last = note.route_note(m)["en"].split("\n")[-1]
    check("review %r is said as %r" % (status, words), last == words, last)
m = copy.deepcopy(FULL)
del m["review"]
check("a model without a review is said as not checked", note.route_note(m)["en"].endswith("This route has not been checked."))

# --- unknown stays unknown --------------------------------------------------------------------------------
m = {"stops": [stop(1, "Loft", None), stop(2, "Ten", "probably fine")],
     "legs": [{"id": "s1>s2", "from": "s1", "to": "s2", "kind": "routed"}]}
en = note.route_note(m)["en"].split("\n")
check("a missing or made-up access value is said as no information, never as accessible",
      en[1] == "The map has no accessibility information for the entrance of Loft."
      and en[-2] == "The map has no accessibility information for the entrance of Ten.", en)
check("a walk without a distance or a stairs value says both are unknown",
      "Loft to Ten: the distance is unknown, stairs unknown." in en, en)
m["legs"][0].update(distance_m=250, stairs="none")
en = note.route_note(m)["en"].split("\n")
check("a stairs value the contract does not know is unknown, not 'no stairs'",
      "Loft to Ten: 250 m on foot, stairs unknown." in en, en)
m["legs"][0].update(stairs="none_mapped")
m["hazards"] = [{"id": "h1", "leg_id": "s1>s2", "stop_id": None, "kind": "steps"}]
en = note.route_note(m)["en"].split("\n")
check("a stairs warning wins over 'none_mapped', and a warning without words gets the fixed sentence for its kind",
      "Loft to Ten: 250 m on foot." in en and "There are stairs on this walk." in en
      and not any("no stairs mapped" in x for x in en), en)
m["legs"][0].update(stairs="some")
m["hazards"] = []
en = note.route_note(m)["en"].split("\n")
check("stairs without a stairs warning are still said", "Loft to Ten: 250 m on foot, with stairs." in en, en)
m["legs"][0].update(kind="guessed", distance_m=None)
en = note.route_note(m)["en"].split("\n")
check("a leg of an unknown kind is not routed, and without a distance nothing is made up",
      "Loft to Ten: not routed, the map has no path between them." in en
      and "The distance and the stairs are unknown." in en, en)
m["benches"] = [{"id": "b1", "leg_id": "s1>s2"}]
en = note.route_note(m)["en"].split("\n")
check("a bench without a distance is said without one", "A bench is mapped near this walk." in en, en)
m["hazards"] = [{"id": "h9", "leg_id": "s7>s8", "stop_id": None, "kind": "long_walk",
                 "detail": {"en": "This walk is 900 m, longer than the 600 m you asked for."}}]
got = note.route_note(m)
check("a warning tied to no known walk is still said, in English where there is no Korean",
      "This walk is 900 m, longer than the 600 m you asked for." in got["en"].split("\n")
      and "This walk is 900 m, longer than the 600 m you asked for." in got["ko"].split("\n"), got)

# --- nothing to say ---------------------------------------------------------------------------------------
for empty in (None, {}, {"stops": [], "legs": []}, "not a model", {"stops": "x", "legs": None, "review": "ok"}):
    got = note.route_note(empty)
    check("no route %r: says so and makes nothing up" % (empty,),
          got["en"] == "This route has no stops.\nThis route has not been checked.", got)

# --- the saved real run, when it is in the repo -----------------------------------------------------------
RUN = os.path.join(REPO, "frontend", "data", "run.json")
if os.path.exists(RUN):
    model = json.load(open(RUN, encoding="utf-8"))["spatial_model"]
    got = note.route_note(model)
    en = got["en"].split("\n")
    check("saved run: the note starts with its stops in order",
          en[0] == "Your route, in this order: %s." % ", ".join(s["name"] for s in sorted(model["stops"], key=lambda s: s["order"])), en[0])
    by_id = {s["id"]: s["name"] for s in model["stops"]}
    for row in model["legs"]:
        start = "%s to %s: " % (by_id[row["from"]], by_id[row["to"]])
        check("saved run: walk %s is said once with its distance of %s m" % (row["id"], row["distance_m"]),
              sum(1 for x in en if x.startswith(start)) == 1
              and ("%d m" % row["distance_m"] in next(x for x in en if x.startswith(start)) or row["kind"] != "routed"), en)
    check("saved run: every warning is in the note", all(h["detail"]["en"] in en for h in model["hazards"]), en)
    check("saved run: no number that the model does not hold", numbers(got["en"]) <= held(model) and numbers(got["ko"]) <= held(model),
          (numbers(got["en"]) | numbers(got["ko"])) - held(model))
    check("saved run: none of the router's advice or the background texts is in the note",
          not any(t and t in got[lang] for lang in ("en", "ko")
                  for t in [row["note"].get(lang) for row in model["legs"]] + [s["background"].get(lang) for s in model["stops"]]))
    check("saved run: the review is said as it is", en[-1] == {"verified": "The checker confirmed this route.",
          "partly_unverified": "The checker did not confirm every point of this route."}[model["review"]["status"]], en[-1])
else:
    print("note  not checked here: the saved real run (frontend/data/run.json is not in this checkout)")

print()
print("%d failed" % len(FAILED) if FAILED else "all passed")
sys.exit(1 if FAILED else 0)
