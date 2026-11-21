"""Drill: the area is a parameter (gilmate/areas.py). Two areas have map data: Shibuya, Tokyo and Hongdae, Seoul.

Python decides from the typed words which area is meant, or that none is supported; every tool then works on the
area of its session, and a session without one is Shibuya, as before.
No network, no key, no model: GILMATE_OFFLINE is set, so nothing is fetched.

Run from the repo folder: python3 tests/drill_areas.py
"""
import os
import sys
import tempfile
import types

os.environ["GILMATE_OFFLINE"] = "1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ["AUDIT_LOG"] = os.path.join(tempfile.mkdtemp(prefix="gilmate-drill-"), "audit.jsonl")

from gilmate import areas, candidates, osm, photos  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


def sides_m(bbox):
    south, west, north, east = bbox
    return (north - south) * 111320.0, (east - west) * 111320.0 * osm.math.cos(osm.math.radians(south))


# --- the table ------------------------------------------------------------------------------------------------------
FIELDS = {"key", "name", "bbox", "origin", "extract", "page", "photo_cache", "words", "local_words", "search_word",
          "area_photo", "hints", "queries", "rated", "specific_food", "local_food", "landmarks", "bearing_deg"}
check("two areas, Shibuya first and the default", list(areas.AREAS) == ["shibuya", "hongdae"] and areas.DEFAULT == "shibuya")
check("every row has exactly the fields the modules read",
      all(set(row) == FIELDS and row["key"] == key for key, row in areas.AREAS.items()),
      [sorted(set(row) ^ FIELDS) for row in areas.AREAS.values()])
check("every box is south, west, north, east and holds its origin",
      all(row["bbox"][0] < row["origin"][0] < row["bbox"][2] and row["bbox"][1] < row["origin"][1] < row["bbox"][3]
          for row in areas.AREAS.values()))
tall, wide = sides_m(areas.AREAS["hongdae"]["bbox"])
tall0, wide0 = sides_m(areas.AREAS["shibuya"]["bbox"])
check("Hongdae's box is about the size of Shibuya's", 0.8 < tall / tall0 < 1.3 and 0.8 < wide / wide0 < 1.3,
      (round(tall), round(wide), round(tall0), round(wide0)))
check("no two areas share an extract, a photo cache or a page folder",
      all(len({row[k] for row in areas.AREAS.values()}) == len(areas.AREAS) for k in ("extract", "photo_cache", "page")))
check("Shibuya keeps its files where they were",
      os.path.normpath(areas.AREAS["shibuya"]["extract"]) == os.path.join(REPO, "data", "shibuya_osm.json")
      and areas.AREAS["shibuya"]["page"] == "data" and osm.AREA == {"name": "Shibuya, Tokyo", "bbox": [35.6570, 139.6975, 35.6632, 139.7050]}
      and photos.THUMBS_URL == "data/photos" and (osm.LAT0, osm.LON0) == (35.6601, 139.70125))

# --- which area the words mean ------------------------------------------------------------------------------------------
for text, want in (("I want to visit Shibuya in Tokyo", "shibuya"), ("시부야에 가고 싶어요", "shibuya"), ("渋谷に行きたい", "shibuya"),
                   ("I want to visit Hongdae in Seoul", "hongdae"), ("Take me to the Hongik University area", "hongdae"),
                   ("홍대에 가고 싶어요", "hongdae"), ("홍익대학교 근처를 걷고 싶어요", "hongdae"), ("HONGDAE", "hongdae"),
                   ("Hong-dae, Seoul", "hongdae"), ("Hongdae first, then Shibuya", "hongdae"),
                   ("Shibuya, not Hongdae", "shibuya"), ("I want to visit Paris", None), ("Seoul", None), ("Tokyo", None),
                   ("", None), (None, None)):
    check("%r asks for %s" % (text, want), areas.which(text) == want, areas.which(text))

# --- the searches -------------------------------------------------------------------------------------------------------
saved = os.path.join(REPO, "data", "cache", "tavily")
for key, word in (("shibuya", "Shibuya"), ("hongdae", "Hong")):
    areas.use(key)
    asked = [q for category in ("see", "shop", "eat") for q in candidates.start_queries(category)]
    check("%s: eight start searches, all about the area, none with an unfilled blank" % key,
          len(asked) == len(set(asked)) == 8 and all(word in q and "{" not in q for q in asked), asked)
    if key == "shibuya":
        check("shibuya: the searches are word for word the saved ones, so a start turn still costs no search",
              all(os.path.exists(os.path.join(saved, candidates.cache_name(q))) for q in asked), asked)
check("the two areas never ask the same search",
      not {q for c in ("see", "shop", "eat") for q in candidates.start_queries(c)}
      & {q for c in ("see", "shop", "eat") for q in (areas.use("shibuya") and candidates.start_queries(c))})

# --- switching ----------------------------------------------------------------------------------------------------------
areas.use("hongdae")
check("use('hongdae') switches the map, the photo cache and the small copies",
      osm.AREA["name"] == "Hongdae, Seoul" and osm.EXTRACT.endswith("hongdae_osm.json")
      and photos.THUMBS_URL == "data/hongdae/photos" and photos.PHOTO_CACHE.endswith(os.path.join("hongdae", "photos"))
      and "korean" in candidates.LOCAL_FOOD and areas.current()["key"] == "hongdae")
check("the area in the state names its key and its map drawing file",
      {k: v for k, v in candidates.area(True).items() if k != "photo"}
      == {"name": "Hongdae, Seoul", "bbox": [37.5506, 126.9196, 37.5576, 126.9274], "supported": True,
          "key": "hongdae", "map": "data/hongdae/map.json"}, candidates.area(True))
areas.use("nowhere")
check("an unknown key is Shibuya", areas.current()["key"] == "shibuya" and osm.AREA["name"] == "Shibuya, Tokyo"
      and candidates.area(True)["key"] == "shibuya" and candidates.area(True)["map"] == "data/map.json"
      and "korean" not in candidates.LOCAL_FOOD and "sushi" in candidates.LOCAL_FOOD)
check("an unsupported area keeps its shape", candidates.area(False) == {"name": None, "bbox": None, "supported": False, "photo": None})

# --- the tools ----------------------------------------------------------------------------------------------------------
try:
    from google.adk.sessions.state import State
    from gilmate import tools
except ImportError:
    State = None
    for name in ("google", "google.adk", "google.adk.tools"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["google.adk.tools"].ToolContext = type("ToolContext", (), {})
    from gilmate import tools
    print("note  google.adk is not installed: the tools run with a stand-in ToolContext on a plain dict")


class Context:
    agent_name = "scout"

    def __init__(self, state):
        self.state = State(state, {}) if State else state


def plain(state):
    return state.to_dict() if hasattr(state, "to_dict") else dict(state)


for text, want in (("I want to visit Hongdae in Seoul", "hongdae"), ("홍대에 가고 싶어요", "hongdae"),
                   ("the Hongik University area, please", "hongdae"), ("I want to visit Shibuya in Tokyo", "shibuya")):
    ctx = Context({})
    got = tools.read_request(text, ctx)
    state = plain(ctx.state)
    check("read_request(%r) is supported and the session holds %s" % (text, want),
          got["status"] == "ok" and state["area"]["supported"] and state["area"]["key"] == want
          and state["area"]["name"] == areas.AREAS[want]["name"] == got["area"]
          and state["audit"][-1]["rule"] == "area_supported" and state["audit"][-1]["detail"] == "area=" + state["area"]["name"],
          (got, state.get("area")))
ctx = Context({})
got = tools.read_request("Take me to Paris", ctx)
check("read_request for another city is not supported, names both areas, and no place is offered",
      got["status"] == "area_not_supported" and "Shibuya, Tokyo and Hongdae, Seoul" in got["message"]
      and plain(ctx.state)["area"] == {"name": None, "bbox": None, "supported": False, "photo": None}
      and not plain(ctx.state).get("candidates"), got)
areas.use("hongdae")
check("a session without an area is Shibuya, whatever the session before it was",
      areas.of_state({})["key"] == "shibuya" and areas.of_state({"area": {"supported": False, "key": "hongdae"}})["key"] == "shibuya"
      and osm.AREA["name"] == "Shibuya, Tokyo")
check("a session of Hongdae switches back to Hongdae",
      areas.of_state({"area": {"supported": True, "key": "hongdae"}})["key"] == "hongdae" and osm.AREA["name"] == "Hongdae, Seoul")
areas.use("shibuya")

# --- Hongdae's saved extract: the places, the hints of the searches, and the route builder -----------------------------
row = areas.use("hongdae")
south, west, north, east = row["bbox"]
there = osm.load()
inside = [p for p in there["places"].values() if south <= p["lat"] <= north and west <= p["lon"] <= east]
check("Hongdae's extract holds sights, shops and places to eat inside the box, benches and a street network",
      all(sum(1 for p in inside if p["category"] == cat) >= 10 for cat in ("see", "shop", "eat"))
      and len(there["benches"]) >= 10 and len(there["nodes"]) > 500,
      ({cat: sum(1 for p in inside if p["category"] == cat) for cat in ("see", "shop", "eat")}, len(there["benches"]), len(there["nodes"])))
for kind, category in (("see", "see"), ("other", "eat"), ("shop", "shop")):
    for name in row["hints"][kind]:
        got = [m["name"] for m in osm.find_place(name, category)["matches"]]
        check("the place named in Hongdae's %s search is on its map: %s" % (category, name), bool(got), got)
check("a place of Shibuya is not on Hongdae's map", osm.find_place("Shibuya Sky", "see")["status"] == "not_found")


def on_map(name, category):
    return there["places"][osm.find_place(name, category)["matches"][0]["osm_id"]]


PICKED = [("c1", on_map("Trick Eye Museum", "see")), ("c2", on_map("Pop Mart", "shop")),
          ("c3", on_map("Hongdae Dakgalbi", "eat")), ("c4", on_map("Red Road", "see"))]
places = [{"id": cid, "category": p["category"], "name": p["name"], "kind": {"en": "Place", "ko": "장소"}, "facts": [],
           "place": {k: p[k] for k in ("lat", "lon", "osm_id", "access")}} for cid, p in PICKED]
PROFILE = {"walk": "short", "stairs": "avoid", "rest": "often", "wish": None, "language": "en"}
ORDER = ["c4", "c1", "c2", "c3"]
model, problems = osm.build_model(PROFILE, places, [c["id"] for c in places], ORDER)
check("the route builder works on Hongdae's extract: every walk follows mapped streets and has a distance",
      problems == [] and model["area"] == {"name": "Hongdae, Seoul", "bbox": row["bbox"]} and len(model["legs"]) == 3
      and all(leg["kind"] == "routed" and 0 < leg["distance_m"] < 1500 and len(leg["line"]) > 2
              and leg["stairs"] in ("none_mapped", "some") for leg in model["legs"]),
      [(leg["id"], leg["kind"], leg["distance_m"], leg["stairs"]) for leg in (model or {}).get("legs", [])])
check("its stops are the map's places inside Hongdae's box, and the rule checks pass",
      [s["name"] for s in model["stops"]] == ["Red Road", "Trick Eye Museum", "POP MART", "Hongdae Dakgalbi"]
      and all(south <= s["lat"] <= north and west <= s["lon"] <= east for s in model["stops"])
      and osm.check_model(model, places, [c["id"] for c in places], PROFILE) == [],
      osm.check_model(model, places, [c["id"] for c in places], PROFILE))
check("a walk longer than the limit you asked for is flagged in Hongdae as in Shibuya, and unknown access stays unknown",
      [leg["fits_profile"] for leg in model["legs"]] == [leg["distance_m"] <= 300 for leg in model["legs"]]
      and sum(1 for h in model["hazards"] if h["kind"] == "long_walk") == sum(1 for leg in model["legs"] if leg["distance_m"] > 300)
      and all(s["access"] == "unknown" for s in model["stops"] if s["name"] != "POP MART")
      and sum(1 for h in model["hazards"] if h["kind"] == "unknown_access") == 3, model["hazards"])
areas.use("shibuya")        # another session was Shibuya in between: the tool must switch back by the session's area
state = {"area": {"supported": True, "key": "hongdae", "name": "Hongdae, Seoul"}, "candidates": places,
         "picks": [c["id"] for c in places], "profile": PROFILE, "rounds": 0}
ctx = Context(state)
got = tools.propose_route(ORDER, "{}", ctx)
draft = plain(ctx.state).get("draft") or {}
check("propose_route builds a Hongdae session's route on Hongdae's map, whatever area was in use before",
      got["status"] == "drafted" and got["rule_failures"] == [] and draft["area"]["name"] == "Hongdae, Seoul"
      and [leg["distance_m"] for leg in draft["legs"]] == [leg["distance_m"] for leg in model["legs"]]
      and "photo_counts" in draft, got)
areas.use("shibuya")

print("drill_areas: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
