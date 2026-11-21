"""Map facts from the cached OpenStreetMap extract. Pure Python: no network, no model, no ADK.

Every coordinate, distance, stair and bench the page shows comes from this file, never from the model.
Missing data is reported as "unknown"; it is never turned into "accessible".
"""
import difflib
import heapq
import json
import math
import os
import re
import time

from . import areas

HERE = os.path.dirname(os.path.abspath(__file__))
M_LAT = 111320.0
# The area these map facts are about. Shibuya unless areas.use() chose another (gilmate/areas.py holds the table):
# EXTRACT the saved extract, AREA {name, bbox}, LAT0 / LON0 the origin of the metres, SEARCH_HINTS as below.
EXTRACT = AREA = LAT0 = LON0 = M_LON = SEARCH_HINTS = None

# Product choices, not measurements: how long one walk may be for each answer.
WALK_LIMIT_M = {"short": 300, "medium": 600, "long": None}
BENCHES_SHOWN = {"often": 3, "sometimes": 2}      # per walk, by her answer about resting; otherwise 1
SEE = {"attraction", "viewpoint", "artwork", "museum", "gallery"}
EAT = {"restaurant", "fast_food", "cafe"}
NOT_A_SHOP = {"vacant", "no"}
ROADS_WITHOUT_PAVEMENT_DATA = {"trunk", "trunk_link", "motorway", "motorway_link", "busway"}
OVERCLAIM = re.compile(
    r"(?<!mapped )\b(no stairs|step[- ]free|stair[- ]free|fully accessible|wheelchair[- ]accessible|barrier[- ]free)\b(?! mapped)",
    re.I)

# A text for the page speaks to the person as "you"; advice that talks about her is replaced by Python's sentence.
ABOUT_HER = re.compile(r"\b(her|hers|she|mom|mother|elderly|older)\b", re.I)
_MAP_SAYS_BEFORE = re.compile(r"\bmap (shows|has|lists|records|marks|knows( of)?)( that there (are|is))?\s*$", re.I)
_MAP_SAYS_AFTER = re.compile(r"^\s*(are |is |were )?(mapped|marked|recorded|(on|in) the map)\b", re.I)


def overclaims(text):
    """True when the text promises no stairs or full access, instead of saying what the map shows.

    "No stairs on this path." is a promise. "The map shows no stairs on this path." and "No stairs are mapped."
    say what the map shows and are fine.
    """
    for sentence in re.split(r"(?<=[.!?;:])\s+", str(text or "")):
        for found in OVERCLAIM.finditer(sentence):
            if not _MAP_SAYS_BEFORE.search(sentence[:found.start()]) and not _MAP_SAYS_AFTER.search(sentence[found.end():]):
                return True
    return False


# SEARCH_HINTS: well-known places that are in the map extract, named in a second web search per kind so that its
# results are about places that can be offered at all (only places on the map can). They are in the area's row in
# gilmate/areas.py; tests/drill_search.py checks each name of Shibuya's, tests/drill_areas.py those of Hongdae.

_caches = {}        # area key -> what load() read from that area's extract
_cache = {}


def apply_area(area):
    """Point every map fact at one area (called by areas.use, and once below for Shibuya)."""
    global EXTRACT, AREA, LAT0, LON0, M_LON, SEARCH_HINTS, _cache
    EXTRACT = area["extract"]
    AREA = {"name": area["name"], "bbox": area["bbox"]}
    LAT0, LON0 = area["origin"]
    M_LON = 111320.0 * math.cos(math.radians(LAT0))
    SEARCH_HINTS = area["hints"]
    _cache = _caches.setdefault(area["key"], {})


apply_area(areas.current())


def _metres(lat, lon):
    return ((lon - LON0) * M_LON, (lat - LAT0) * M_LAT)


def _dist(a, b):
    return math.dist(_metres(*a), _metres(*b))


def _centre(e):
    if "lat" in e:
        return e["lat"], e["lon"]
    if "bounds" in e:
        b = e["bounds"]
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    g = e.get("geometry") or []
    return sum(p["lat"] for p in g) / len(g), sum(p["lon"] for p in g) / len(g)


def access_from_tags(tags):
    """yes / limited / no only when the map says so. A missing tag is "unknown"."""
    v = tags.get("wheelchair")
    return v if v in ("yes", "limited", "no") else "unknown"


def _category(tags):
    if tags.get("tourism") in SEE:
        return "see"
    if tags.get("amenity") in EAT:
        return "eat"
    if "shop" in tags and tags["shop"] not in NOT_A_SHOP:
        return "shop"
    if tags.get("junction") and tags.get("wikidata"):
        return "see"        # a named crossing with its own Wikidata entry is a sight: the Shibuya Scramble Crossing
    return None


# Every name the map has for a place, the one shown first. A web page or a request may use any of them:
# the map's "Shibuya Scramble Crossing" is also "渋谷駅前", "渋谷スクランブル交差点" and "Shibuya Crossing".
NAME_KEYS = ("name:en", "name", "name:ja", "name:ko", "alt_name:en", "alt_name", "alt_name:ja", "official_name:en",
             "official_name", "short_name:en", "short_name")


def names_of(tags):
    out = []
    for key in NAME_KEYS:
        for name in str(tags.get(key) or "").split(";"):
            if name.strip() and name.strip() not in out:
                out.append(name.strip())
    return out


def _on_the_surface(tags):
    if tags.get("tunnel") or tags.get("indoor") or tags.get("highway") in ("elevator", "corridor", "platform"):
        return False
    return tags.get("level") in (None, "0") and not str(tags.get("layer", "0")).startswith("-")


def load():
    if _cache:
        return _cache
    elements = json.load(open(EXTRACT, encoding="utf-8"))["elements"]
    places, benches, graph, pos = {}, [], {}, {}
    for e in elements:
        tags = e.get("tags", {})
        ref = f"{e['type']}/{e['id']}"
        name = tags.get("name:en") or tags.get("name")
        cat = _category(tags)
        if name and cat:
            lat, lon = _centre(e)
            places[ref] = {"osm_id": ref, "name": name, "name_local": tags.get("name", name), "category": cat,
                           "names": names_of(tags),
                           "lat": round(lat, 6), "lon": round(lon, 6), "access": access_from_tags(tags),
                           "kind": tags.get("tourism") or tags.get("amenity") or tags.get("shop")
                           or ("crossing" if tags.get("junction") else None),
                           "cuisine": tags.get("cuisine", "")}
        if tags.get("amenity") == "bench" and "lat" in e:
            benches.append({"id": ref, "lat": e["lat"], "lon": e["lon"], "source": f"osm:{ref}"})
        if e["type"] == "way" and "highway" in tags and _on_the_surface(tags) \
                and tags["highway"] not in ROADS_WITHOUT_PAVEMENT_DATA:
            steps = tags["highway"] == "steps"
            count = tags.get("step_count")
            pts = [(round(p["lat"], 7), round(p["lon"], 7)) for p in e["geometry"]]
            for a, b in zip(pts, pts[1:]):
                edge = (_dist(a, b), steps, ref, int(count) if count and count.isdigit() else None)
                graph.setdefault(a, []).append((b,) + edge)
                graph.setdefault(b, []).append((a,) + edge)
                pos[a] = pos[b] = True
    # keep the largest connected part, so a place never snaps to an island of the street network
    seen, best = set(), set()
    for start in graph:
        if start in seen:
            continue
        part, stack = {start}, [start]
        while stack:
            for nxt in graph[stack.pop()]:
                if nxt[0] not in part:
                    part.add(nxt[0])
                    stack.append(nxt[0])
        seen |= part
        if len(part) > len(best):
            best = part
    _cache.update(places=places, benches=benches, graph={n: graph[n] for n in best}, nodes=list(best))
    return _cache


def _fold(s):
    return re.sub(r"[^\w]+", " ", s.casefold()).strip()


def _has_words(text, words):
    """True when the words stand in the text as whole words: "ten" is in "sushi tokyo ten", not in "tenkaippin"."""
    return " %s " % words in " %s " % text


def _spelled_alike(a, b):
    a, b = a.replace(" ", ""), b.replace(" ", "")
    return abs(len(a) - len(b)) <= 2 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.88


def find_place(name, category=""):
    """Places in the map data one of whose names matches (English, local, alternative). Best first, at most five."""
    q, d = _fold(name), load()
    hits = []
    for p in d["places"].values():
        if category and p["category"] != category:
            continue
        names = {_fold(n) for n in p["names"]}
        score = 0
        if q in names:
            score = 3
        elif any(q and (_has_words(n, q) or _has_words(q, n)) for n in names if n):
            score = 2
        else:
            qt = set(q.split())
            if qt and max(len(qt & set(n.split())) / len(qt) for n in names) >= 0.6:
                score = 1
            elif len(q) >= 6 and any(_spelled_alike(q, n) for n in names if n):
                score = 1       # another romanisation: "Sushizanmai" for the map's "Sushizammai"
        if score:
            hits.append((score, p))
    hits.sort(key=lambda t: (-t[0], len(t[1]["name"])))
    return {"status": "ok" if hits else "not_found", "total_matches": len(hits),
            "matches": [p for _, p in hits[:5]]}


def _snap(point):
    d = load()
    return min(d["nodes"], key=lambda n: _dist(n, point))


def _path(start, goal, stairs_factor):
    graph = load()["graph"]
    queue, best, prev = [(0.0, start)], {start: 0.0}, {}
    while queue:
        cost, node = heapq.heappop(queue)
        if node == goal:
            break
        if cost > best[node]:
            continue
        for nxt, metres, steps, way, count in graph[node]:
            if steps and stairs_factor is None:
                continue
            c = cost + metres * (stairs_factor if steps else 1)
            if c < best.get(nxt, 1e18):
                best[nxt] = c
                prev[nxt] = (node, metres, steps, way, count)
                heapq.heappush(queue, (c, nxt))
    if goal not in prev and goal != start:
        return None
    out, node = [], goal
    while node != start:
        p = prev[node]
        out.append((node,) + p[1:])
        node = p[0]
    return [(start, 0.0, False, None, None)] + out[::-1]


def walking_route(from_id, to_id, stairs="ok"):
    """One walking leg between two places, along mapped streets and paths.

    stairs: "avoid" looks for a way without stairs first; "few" prefers one; "ok" takes the shortest.
    """
    d = load()
    a, b = d["places"].get(from_id), d["places"].get(to_id)
    if not a or not b:
        return {"status": "error", "error_message": "unknown place id; use ids returned by find_place"}
    pa, pb = (a["lat"], a["lon"]), (b["lat"], b["lon"])
    sa, sb = _snap(pa), _snap(pb)
    path = _path(sa, sb, {"avoid": None, "few": 4.0}.get(stairs, 1.0))
    avoided = True
    if path is None and stairs == "avoid":
        path, avoided = _path(sa, sb, 1.0), False
    if path is None:
        return {"status": "ok", "kind": "straight_line", "from": from_id, "to": to_id,
                "distance_m": round(_dist(pa, pb)), "line": [[pa[1], pa[0]], [pb[1], pb[0]]],
                "stairs": "unknown", "steps": [], "stairs_avoided": False,
                "note": "No mapped path found. Straight-line distance only; stairs unknown."}
    metres, steps, seen = _dist(pa, sa), [], set()
    for node, m, is_steps, way, count in path:
        metres += m
        if is_steps and way not in seen:
            seen.add(way)
            steps.append({"way": way, "step_count": count, "lat": node[0], "lon": node[1], "at_m": round(metres)})
    metres += _dist(sb, pb)
    line = [[pa[1], pa[0]]] + [[n[1], n[0]] for n, *_ in path] + [[pb[1], pb[0]]]
    return {"status": "ok", "kind": "routed", "from": from_id, "to": to_id, "distance_m": round(metres),
            "line": line, "stairs": "some" if steps else "none_mapped", "steps": steps,
            "stairs_avoided": avoided if stairs == "avoid" else None}


def rest_spots(line, max_off_m=45):
    """Benches in the map data near a leg."""
    pts = [(lat, lon) for lon, lat in line]
    out = []
    for bench in load()["benches"]:
        off = min(_dist((bench["lat"], bench["lon"]), p) for p in pts)
        if off <= max_off_m:
            out.append({**bench, "off_route_m": round(off)})
    return sorted(out, key=lambda x: x["off_route_m"])


T = {
    "steps": ("Stairs on this path{count}.", "이 길에 계단이 있습니다{count}."),
    "count": (", {n} steps", ", {n}계단"),
    "count_unknown": (", number of steps not recorded", ", 계단 수는 기록되어 있지 않습니다"),
    "long_walk": ("This walk is {m} m, longer than the {limit} m you asked for.",
                  "이 구간은 {m}m로, 원하신 {limit}m보다 깁니다."),
    "long_walk_learned": ("This walk is {m} m, longer than the {limit} m limit set after you said a walk was too far.",
                          "이 구간은 {m}m로, 전에 너무 멀다고 하신 뒤 정한 기준 {limit}m보다 깁니다."),
    "unknown_access": ("The map has no accessibility information for the entrance of {name}.",
                       "{name} 입구의 접근성 정보가 지도에 없습니다."),
    "unknown_path": ("No mapped path. The distance is a straight line and stairs are unknown.",
                     "지도에 길이 없습니다. 거리는 직선 거리이며 계단 여부는 알 수 없습니다."),
    "leg": ("{m} m on foot. {stairs}", "걸어서 {m}m. {stairs}"),
    "none_mapped": ("No stairs mapped on this path.", "이 길에는 지도에 표시된 계단이 없습니다."),
    "some": ("There are stairs on this path.", "이 길에 계단이 있습니다."),
    "unknown": ("Stairs unknown.", "계단 여부는 알 수 없습니다."),
}


def _both(key, **kw):
    en, ko = T[key]
    return {"en": en.format(**kw), "ko": ko.format(**kw)}


def walk_limit(profile, learned_limit_m=None):
    """How long one walk may be, in metres, or None for no limit.

    Her answer about walking sets it. A limit learned from her feedback counts alone when her answer sets none.
    When both exist the lower one applies, so a learned limit never lifts the limit she asked for.
    """
    own = profile.get("walk_limit_m")        # a distance she stated herself ("about 1 km"), checked where it was read
    stated = own if isinstance(own, int) and not isinstance(own, bool) and 100 <= own <= 5000 else None
    if learned_limit_m is None:
        return stated if stated is not None else WALK_LIMIT_M.get(profile.get("walk", "medium"))
    asked = stated if stated is not None else WALK_LIMIT_M.get(profile.get("walk"))
    return learned_limit_m if asked is None else min(asked, learned_limit_m)


def benches_shown(profile):
    return BENCHES_SHOWN.get(profile.get("rest"), 1)


def legs_changed_by_limit(model, profile, learned_limit_m):
    """Ids of the walks judged differently with the learned limit than by her answer about walking alone."""
    asked, applied = walk_limit(profile), walk_limit(profile, learned_limit_m)
    return [leg["id"] for leg in model["legs"]
            if (asked is not None and leg["distance_m"] > asked) != (leg["distance_m"] > applied)]


def _background(o):
    """What the stop card says about the place: the option's summary, or the candidate's description, or its kind."""
    said = o.get("summary") or o.get("description") or o.get("kind") or {}
    en = said.get("en") or (o.get("kind") or {}).get("en") or ""
    return {"en": en, "ko": said.get("ko") or (o.get("kind") or {}).get("ko") or en}


def build_model(profile, options, picks, order, leg_notes=None, learned_limit_m=None):
    """Assemble the spatial model for the picked options in the given order. Returns (model, problems).

    learned_limit_m: her walking limit learned from feedback, when there is one. Without it the profile alone decides.
    """
    by_id = {o["id"]: o for o in options}
    problems = []
    if sorted(order) != sorted(picks):
        return None, ["order must contain exactly the picked options"]
    limit = walk_limit(profile, learned_limit_m)
    # the warning names the learned limit only when that is the one that applies
    learned_applies = learned_limit_m is not None and limit == learned_limit_m and limit != walk_limit(profile)
    long_walk_text = "long_walk_learned" if learned_applies else "long_walk"
    stops, legs, hazards, benches = [], [], [], []
    for i, oid in enumerate(order):
        o = by_id[oid]
        stops.append({"id": f"s{i + 1}", "option_id": oid, "order": i + 1, "category": o["category"], "name": o["name"],
                      "lat": o["place"]["lat"], "lon": o["place"]["lon"], "access": o["place"]["access"],
                      "background": _background(o),
                      "sources": sorted({f["source_url"] for f in o.get("facts", [])}
                                        | {(o.get("description_source") or {}).get("url") or ""} - {""})})
        if o["place"]["access"] == "unknown":
            hazards.append({"id": f"h{len(hazards) + 1}", "leg_id": None, "stop_id": f"s{i + 1}", "kind": "unknown_access",
                            "lat": o["place"]["lat"], "lon": o["place"]["lon"],
                            "detail": _both("unknown_access", name=o["name"]), "source": f"osm:{o['place']['osm_id']}"})
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        r = walking_route(by_id[a["option_id"]]["place"]["osm_id"], by_id[b["option_id"]]["place"]["osm_id"],
                          profile.get("stairs", "ok"))
        leg_id = f"{a['id']}>{b['id']}"
        too_long = limit is not None and r["distance_m"] > limit
        fits = not too_long and not (profile.get("stairs") == "avoid" and r["stairs"] != "none_mapped")
        note = (leg_notes or {}).get(leg_id)
        about_her = isinstance(note, dict) and bool(ABOUT_HER.search(str(note.get("en") or "")))
        if not isinstance(note, dict) or not note.get("en") or overclaims(note["en"]) or about_her:
            if about_her:
                problems.append(f"note.not_addressed_to_you:{leg_id}")
            elif isinstance(note, dict) and note.get("en"):
                problems.append(f"note.overclaims:{leg_id}")
            stairs_text = _both(r["stairs"] if r["kind"] == "routed" else "unknown")
            note = {k: T["leg"][j].format(m=r["distance_m"], stairs=stairs_text[k]) for j, k in enumerate(("en", "ko"))}
        legs.append({"id": leg_id, "from": a["id"], "to": b["id"], "distance_m": r["distance_m"], "line": r["line"],
                     "kind": r["kind"], "stairs": r["stairs"], "fits_profile": fits, "note": note})
        for s in r["steps"]:
            count = _both("count", n=s["step_count"]) if s["step_count"] else _both("count_unknown")
            hazards.append({"id": f"h{len(hazards) + 1}", "leg_id": leg_id, "stop_id": None, "kind": "steps",
                            "lat": s["lat"], "lon": s["lon"],
                            "detail": {k: T["steps"][j].format(count=count[k]) for j, k in enumerate(("en", "ko"))},
                            "source": f"osm:{s['way']}"})
        if r["kind"] == "straight_line":
            hazards.append({"id": f"h{len(hazards) + 1}", "leg_id": leg_id, "stop_id": None, "kind": "unknown_access",
                            "lat": a["lat"], "lon": a["lon"], "detail": _both("unknown_path"), "source": "computed"})
        if too_long:
            mid = r["line"][len(r["line"]) // 2]
            hazards.append({"id": f"h{len(hazards) + 1}", "leg_id": leg_id, "stop_id": None, "kind": "long_walk",
                            "lat": mid[1], "lon": mid[0], "detail": _both(long_walk_text, m=r["distance_m"], limit=limit),
                            "source": "computed"})
        for bench in rest_spots(r["line"])[:benches_shown(profile)]:
            benches.append({"id": f"b{len(benches) + 1}", "leg_id": leg_id, "lat": bench["lat"], "lon": bench["lon"],
                            "off_route_m": bench["off_route_m"], "source": bench["source"]})
    model = {"area": AREA, "stops": stops, "legs": legs, "hazards": hazards, "benches": benches,
             "review": {"status": "partly_unverified", "rounds": 0, "removed": []},
             "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return model, problems


def check_model(model, options, picks, profile):
    """The rule checks no sentence can talk its way past. Returns a list of failed rules."""
    failed = []
    by_id = {o["id"]: o for o in options}
    if sorted(s["option_id"] for s in model["stops"]) != sorted(picks):
        failed.append("stops.not_the_picks")
    south, west, north, east = AREA["bbox"]
    for s in model["stops"]:
        o = by_id.get(s["option_id"])
        if not o or (s["lat"], s["lon"]) != (o["place"]["lat"], o["place"]["lon"]):
            failed.append(f"stop.coordinates_changed:{s['id']}")
        if not (south <= s["lat"] <= north and west <= s["lon"] <= east):
            failed.append(f"stop.outside_area:{s['id']}")
        if s["access"] != o["place"]["access"]:
            failed.append(f"stop.access_changed:{s['id']}")
    stop_option = {s["id"]: s["option_id"] for s in model["stops"]}
    for leg in model["legs"]:
        again = walking_route(by_id[stop_option[leg["from"]]]["place"]["osm_id"],
                              by_id[stop_option[leg["to"]]]["place"]["osm_id"], profile.get("stairs", "ok"))
        if again["distance_m"] != leg["distance_m"] or again["stairs"] != leg["stairs"]:
            failed.append(f"leg.not_reproducible:{leg['id']}")
        if overclaims(leg["note"].get("en", "")):
            failed.append(f"note.overclaims:{leg['id']}")
    # the day does not start with the meal when walking the same stops the other way round is as short
    ordered = sorted(model["stops"], key=lambda s: s["order"])
    if len(ordered) > 1 and ordered[0]["category"] == "eat" and ordered[-1]["category"] != "eat":
        back = [walking_route(by_id[b["option_id"]]["place"]["osm_id"], by_id[a["option_id"]]["place"]["osm_id"],
                              profile.get("stairs", "ok"))["distance_m"] for a, b in zip(ordered, ordered[1:])]
        if sum(back) <= sum(leg["distance_m"] for leg in model["legs"]):
            failed.append("order.food_first: the same stops in reverse order are as short and end with the meal")
    for s in model["stops"]:
        if overclaims(s["background"].get("en", "")) and s["access"] != "yes":
            failed.append(f"background.overclaims:{s['id']}")
    return failed
