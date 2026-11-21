"""The places offered on the map (CONTRACT.md section 7). Pure Python: no model, no ADK.

Python chooses 8 to 12 places from the OpenStreetMap extract, mixed across see / shop / eat, by a fixed score:
a place counts for more when it has its own Wikidata entry, when a saved web search result names it, and when the
map knows its access. Name, coordinates and access are the map's. What a place is (`kind`) comes from its map tags
through a fixed table; its description is copied from a cited page (Wikipedia, Wikidata, the map's own note).
A model may add a description, a rating or facts later, but only through check_addition below.
"""
import hashlib
import json
import os
import re

from . import areas, guards, memory, osm, photos

HERE = os.path.dirname(os.path.abspath(__file__))
PER_CATEGORY = 4                     # 3 categories: 12 places at most
AT_LEAST = 8
LOOKED_UP_FOR_PHOTOS = 8             # per category, the best places by the other points
APART_M = 40                         # two candidates are never the same spot (shops on floors of one building)
OSM_URL = "https://www.openstreetmap.org/"
START_WORDS = areas.AREAS["shibuya"]["words"]      # what asks for Shibuya; the other areas: areas.which

KIND = {   # map tag value -> what the card calls the place, English and Korean
    "attraction": ("Sight", "명소"), "viewpoint": ("Viewpoint", "전망대"), "artwork": ("Artwork", "예술 작품"),
    "museum": ("Museum", "박물관"), "gallery": ("Gallery", "갤러리"),
    "statue": ("Statue", "동상"), "mural": ("Mural", "벽화"), "sculpture": ("Sculpture", "조각상"),
    "mosaic": ("Mosaic", "모자이크 작품"),
    "restaurant": ("Restaurant", "식당"), "fast_food": ("Quick meal", "간편 식당"), "cafe": ("Café", "카페"),
    "sushi": ("Sushi restaurant", "초밥집"), "ramen": ("Ramen restaurant", "라멘집"), "soba": ("Soba restaurant", "소바집"),
    "udon": ("Udon restaurant", "우동집"), "tempura": ("Tempura restaurant", "튀김 요리점"),
    "yakiniku": ("Grilled meat restaurant", "야키니쿠 식당"), "tonkatsu": ("Pork cutlet restaurant", "돈가스 식당"),
    "beef_bowl": ("Beef bowl restaurant", "규동집"), "curry": ("Curry restaurant", "카레 식당"),
    "japanese": ("Japanese restaurant", "일식당"), "noodle": ("Noodle restaurant", "국수집"),
    "coffee_shop": ("Coffee shop", "커피숍"), "burger": ("Burger restaurant", "햄버거 가게"),
    "mall": ("Shopping centre", "쇼핑몰"), "department_store": ("Department store", "백화점"),
    "variety_store": ("Variety store", "잡화점"), "gift": ("Souvenir shop", "기념품 가게"),
    "books": ("Bookshop", "서점"), "toys": ("Toy shop", "장난감 가게"), "anime": ("Anime and character shop", "애니메이션·캐릭터 매장"),
    "video_games": ("Video game shop", "게임 매장"), "supermarket": ("Supermarket", "슈퍼마켓"),
    "electronics": ("Electronics shop", "전자제품 매장"), "clothes": ("Clothes shop", "옷 가게"),
    "stationery": ("Stationery shop", "문구점"), "confectionery": ("Sweets shop", "과자 가게"),
    "tea": ("Tea shop", "차 가게"), "musical_instrument": ("Musical instrument shop", "악기점"),
    "cosmetics": ("Cosmetics shop", "화장품 가게"), "shoes": ("Shoe shop", "신발 가게"), "art": ("Art shop", "미술품 가게"),
    "craft": ("Craft shop", "공예품 가게"), "shop": ("Shop", "가게"),
    "crossing": ("Crossing", "교차로"),
}
KIND.update({   # kinds that only Hongdae's row names (areas.py): Korean kitchens
    "korean": ("Korean restaurant", "한식당"), "barbecue": ("Korean barbecue restaurant", "고깃집"),
    "chicken": ("Fried chicken restaurant", "치킨집"), "dumplings": ("Dumpling restaurant", "만두집"),
    "seafood": ("Seafood restaurant", "해산물 식당"),
})
# Per area (gilmate/areas.py), Shibuya unless areas.use() chose another:
# SPECIFIC_FOOD  cuisine tags that give a place to eat its own kind.
# LOCAL_FOOD     places to eat are offered for the food of the place you are visiting: in Shibuya Japanese kitchens
#                and plain restaurants, not cafés and burger chains, however often a web page names them. A product
#                choice, made in the open.
# QUERIES, RATED the web searches, below.
SPECIFIC_FOOD = LOCAL_FOOD = QUERIES = RATED = None
SOUVENIR_SHOPS = {"mall", "department_store", "variety_store", "gift", "books", "toys", "anime", "video_games",
                  "supermarket", "stationery", "confectionery", "tea", "art", "craft"}
NOT_FOR_VISITORS = {"hairdresser", "beauty", "massage", "laundry", "dry_cleaning", "mobile_phone", "tobacco",
                    "estate_agent", "ticket", "lottery", "travel_agency", "optician", "chemist", "car", "car_repair",
                    "bicycle", "pawnbroker", "money_lender", "funeral_directors", "copyshop", "locksmith", "tattoo",
                    "e-cigarette", "erotic", "psychic"}
NOT_FOR_VISITORS_BY_NAME = re.compile(r"\b(vape|tobacco|cigar\w*)\b", re.I)     # whatever kind the map files it under
LABELS = {"opening_hours": "Opening hours", "level": "Floor", "website": "Website"}

# QUERIES: each category is searched with every query in its list; results are saved on disk per query.
# RATED: the start turn also asks what visitors rate well, naming places the map has. A rating is only ever shown
# with the page and the quote it came from (guards.ground_rating). The exact strings are in the area's row.


def apply_area(area):
    """Point the searches and the food table at one area (called by areas.use, and once below for Shibuya)."""
    global SPECIFIC_FOOD, LOCAL_FOOD, QUERIES, RATED
    SPECIFIC_FOOD, LOCAL_FOOD = area["specific_food"], area["local_food"]
    QUERIES, RATED = area["queries"], area["rated"]


apply_area(areas.current())


def queries(category, food_answer=None):
    """The web searches for one category, as exact strings. food_answer: the older page's answer about food."""
    food = memory.FOOD_SEARCH.get(food_answer, memory.FOOD_SEARCH_OTHERWISE)
    hints = osm.SEARCH_HINTS["see" if category == "see" else food_answer if food_answer in osm.SEARCH_HINTS else "other"]
    kind_of_food = food_answer if food_answer in memory.FOOD_SEARCH else "Japanese restaurants"
    return [q.format(food=food, kind=kind_of_food, places=", ".join(hints)) for q in QUERIES[category]]


WISH_WORDS = {"omakase": "sushi"}      # a word she may type that is no kind on the map -> the kind it belongs to
MOST_WISHED = 3                        # of the places to eat, this many may be of the kind she asked for


def food_wish(text):
    """What she asked to eat, read from her typed words against fixed lists: {"kind", "words"} or None.

    Only words of the area's own food list and of WISH_WORDS come out; nothing else of her text does."""
    found = set(re.findall(r"[a-z]+", str(text or "").casefold()[:600]))
    kinds = [k for k in SPECIFIC_FOOD if k in LOCAL_FOOD and k in found]
    extra = [w for w in sorted(WISH_WORDS) if w in found and WISH_WORDS[w] in LOCAL_FOOD]
    kind_asked = kinds[0] if kinds else WISH_WORDS[extra[0]] if extra else None
    return {"kind": kind_asked, "words": extra + [kind_asked]} if kind_asked else None


def wish_queries(wish):
    """The extra web searches for what she asked to eat, as exact strings built from the fixed lists only."""
    if not isinstance(wish, dict) or wish.get("kind") not in LOCAL_FOOD:
        return []
    words = [w for w in wish.get("words") or [] if w in WISH_WORDS or w in SPECIFIC_FOOD]
    area_words = QUERIES["eat"][0].split(" best ")[0]          # "Shibuya Tokyo", as the area's own queries say it
    return ["%s best %s restaurant rating reviews" % (area_words, " ".join(words))]


def start_queries(category):
    """The web searches of the start turn for one category: the usual ones, and one that asks for ratings."""
    hints = osm.SEARCH_HINTS["see"] if category == "see" \
        else osm.SEARCH_HINTS["other"] + osm.SEARCH_HINTS.get("sushi", [])[:2]
    return queries(category) + [RATED[category].format(places=", ".join(hints),
                                                       shops=", ".join(osm.SEARCH_HINTS.get("shop", [])))]


def cache_name(query):
    """The file a query's results are saved in."""
    return hashlib.sha256(query.encode()).hexdigest()[:16] + ".json"


_cache = {}


def _tags():
    if osm.EXTRACT not in _cache:           # one table per area's extract
        with open(osm.EXTRACT, encoding="utf-8") as handle:
            _cache[osm.EXTRACT] = {"%s/%s" % (e["type"], e["id"]): e.get("tags", {}) for e in json.load(handle)["elements"]}
    return _cache[osm.EXTRACT]


def asks_for_shibuya(text):
    """True when the words name Shibuya. Which area a request means is decided by areas.which, not by the model."""
    return any(word in str(text or "").casefold() for word in START_WORDS)


def area(supported=True):
    """What the session state holds as `area` (CONTRACT.md 7.2): the area in use, or the unsupported shape."""
    if not supported:
        return {"name": None, "bbox": None, "supported": False, "photo": None}
    now = areas.current()
    return {"name": now["name"], "bbox": list(now["bbox"]), "supported": True, "photo": photos.for_area(),
            "key": now["key"], "map": areas.page_file(now, "map.json")}


def kind(tags):
    """What the place is, in both languages, from its map tags."""
    if tags.get("tourism") in KIND:
        key = tags.get("artwork_type") if tags.get("artwork_type") in KIND else tags["tourism"]
    elif tags.get("amenity") in osm.EAT:
        food = [c.strip() for c in str(tags.get("cuisine", "")).split(";")]
        key = next((c for c in SPECIFIC_FOOD if c in food), tags["amenity"])
    elif tags.get("junction") and "shop" not in tags:
        key = "crossing"
    else:
        key = tags.get("shop") if tags.get("shop") in KIND else "shop"
    return {"key": key, "en": KIND[key][0], "ko": KIND[key][1]}


def saved_results(folder=None):
    """The saved results of the start turn's searches that pass the screening: {url: title and text}.

    Only the searches the start turn runs count, so the places Python chooses here are the ones a real start turn
    chooses from the same saved searches.
    """
    folder = folder or os.environ.get("GILMATE_SEARCH_CACHE") or os.path.join(HERE, "..", "data", "cache", "tavily")
    results = []
    for category in ("see", "shop", "eat"):
        for query in start_queries(category):
            path = os.path.join(folder, cache_name(query))
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    results += json.load(handle).get("results", [])
    return {r["url"]: "%s\n%s" % (r.get("title", ""), r.get("content", ""))
            for r in guards.screen_results(results)["passed"] if r.get("url")}


def _named_in(name, texts, longer=()):
    """How many saved results name the place exactly as the map writes it ("Uobei", not any "scramble").

    longer: names of other places that contain this one ("Kura Sushi" for "Kura"); a text naming those does not count.
    """
    if len(name) < 4:
        return 0
    word = re.compile(r"(?<!\w)%s(?!\w)" % re.escape(name))
    count = 0
    for text in texts:
        for other in longer:
            text = text.replace(other, " ")
        count += bool(word.search(text))
    return count


def named(place, texts, longer=()):
    """How many saved results name the place by any name the map has for it: English, local or alternative
    ("Shibuya Scramble Crossing", "Shibuya Crossing"). Each name counts only as the map writes it."""
    words = [re.compile(r"(?<!\w)%s(?!\w)" % re.escape(n)) for n in place.get("names") or [place["name"]] if len(n) >= 4]
    count = 0
    for text in texts:
        for other in longer:
            text = text.replace(other, " ")
        count += any(word.search(text) for word in words)
    return count


def _longer(place, all_names):
    """Names of other places that contain one of this place's names ("Kura Sushi" for "Kura", "Watch Shibuya
    Crossing" for "Shibuya Crossing"): a text that names those does not name this place."""
    mine = place.get("names") or [place["name"]]
    return [n for n in all_names if n not in mine and any(m in n for m in mine)]


def score(place, tags, texts, longer=(), has_photo=False):
    named = globals()["named"](place, texts, longer)
    return (3 * ("wikidata" in tags) + 2 * (named > 0) + (named > 1) + (place["access"] in ("yes", "limited"))
            + ("name:ko" in tags) + ("opening_hours" in tags) + 2 * bool(has_photo)
            + (place["category"] == "shop" and place["kind"] in SOUVENIR_SHOPS))


def choose(texts, wish=None):
    """The osm ids of the places to offer, best first within see, shop, eat in turn. Fixed rules, no model.

    wish: the kind of food she asked for ("sushi"); places of that kind come first among the places to eat."""
    d, tags = osm.load(), _tags()
    south, west, north, east = osm.AREA["bbox"]
    ranked = {"see": [], "shop": [], "eat": []}
    all_names = {n for p in d["places"].values() for n in p["names"]}
    for ref, place in d["places"].items():
        if not (south <= place["lat"] <= north and west <= place["lon"] <= east):
            continue
        if place["kind"] in NOT_FOR_VISITORS or not re.search(r"[A-Za-z]", place["name"]) \
                or NOT_FOR_VISITORS_BY_NAME.search(place["name"]):
            continue                                   # you must be able to read the name
        if place["category"] == "eat" and kind(tags[ref])["key"] not in LOCAL_FOOD:
            continue
        longer = _longer(place, all_names)
        s = score(place, tags[ref], texts, longer)
        asked_for = bool(wish) and place["category"] == "eat" and kind(tags[ref])["key"] == wish
        if s >= (1 if asked_for else 2):       # the kind she asked for needs less to be offered; it is on the map
            # Sights: the ones most search results name come first, whatever else they score. The best-known
            # sight of an area is the one every page names; it is looked up first and offered first.
            most_named = -named(place, texts, longer) if place["category"] == "see" else 0
            ranked[place["category"]].append((most_named, -s, ref, longer))
    for category, rows in ranked.items():              # a place with a real photo of it counts for more
        rows.sort()
        for i, (most_named, s, ref, longer) in enumerate(rows):
            near_top = i < LOOKED_UP_FOR_PHOTOS
            has_photo = bool(photos.for_place(d["places"][ref], tags[ref], photos.about(tags[ref]))) if near_top else False
            rows[i] = (most_named, -score(d["places"][ref], tags[ref], texts, longer, has_photo), ref)
    chosen = []
    for category, most_alike in (("see", 2), ("shop", 2), ("eat", 1)):
        taken = []
        rows = sorted(ranked[category])
        if category == "eat" and wish:
            rows.sort(key=lambda row: kind(tags[row[2]])["key"] != wish)      # stable: the wished kind first
        for _, _, ref in rows:
            place, what = d["places"][ref], kind(tags[ref])["key"]
            most = MOST_WISHED if category == "eat" and wish and what == wish else most_alike
            near = any(osm._dist((place["lat"], place["lon"]), (o["lat"], o["lon"])) < APART_M
                       for o in (d["places"][c] for c in chosen + taken))
            same_name = any(d["places"][c]["name"] == place["name"] for c in chosen + taken)
            alike = sum(1 for c in taken if kind(tags[c])["key"] == what)
            if not near and not same_name and alike < most:
                taken.append(ref)
            if len(taken) == PER_CATEGORY:
                break
        chosen += taken
    return chosen


def own_sources(ref, tags, about):
    """The pages Python itself read about a place: {url: text}. Facts and descriptions are checked against these."""
    out = {OSM_URL + ref: "\n".join("%s=%s" % (k, v) for k, v in sorted(tags.items()))}
    if about:
        out[about["url"]] = "\n".join(about.get("descriptions", {}).values())
        for extract in about.get("extracts", {}).values():
            out[extract["url"]] = extract["text"]
    return out


def _capital(text):
    text = text.strip()
    text = text[:1].upper() + text[1:]
    return text if text[-1:] in ".!?。다" else text + "."


def describe(ref, tags, about):
    """(description {en, ko}, description_source) copied from a cited page, or (None, None). ko may be ""."""
    extracts = (about or {}).get("extracts", {})
    said = (about or {}).get("descriptions", {})
    if extracts.get("en"):
        text, source = extracts["en"]["first"], {"url": extracts["en"]["url"], "quote": extracts["en"]["first"]}
    elif said.get("en"):
        text, source = _capital(said["en"]), {"url": about["url"], "quote": said["en"]}
    elif tags.get("description") and re.search(r"[A-Za-z]{3}", tags["description"]):
        text, source = _capital(tags["description"]), {"url": OSM_URL + ref, "quote": tags["description"]}
    else:
        return None, None
    korean = ""
    if extracts.get("ko"):
        korean = extracts["ko"]["first"]
        source["ko"] = {"url": extracts["ko"]["url"], "quote": korean}
    elif said.get("ko"):
        korean = _capital(said["ko"])
        source["ko"] = {"url": about["url"], "quote": said["ko"]}
    return {"en": text, "ko": korean}, source


def map_facts(ref, tags):
    return [{"label": LABELS[key], "value": tags[key], "source_url": OSM_URL + ref, "quote": "%s=%s" % (key, tags[key])}
            for key in ("opening_hours", "level", "website") if tags.get(key)]


STREET_SHOWN = 400                   # photo dots in the session state; the count says how many were found


def rest_spots(taken):
    """Every bench the map has inside the area: [{id, lat, lon, kind, source, photos}]. photos: taken within 60 m."""
    south, west, north, east = osm.AREA["bbox"]
    return [{"id": "r%d" % (i + 1), "lat": b["lat"], "lon": b["lon"], "kind": "bench", "source": b["source"],
             "photos": photos.near(b["lat"], b["lon"], taken, most=2)}
            for i, b in enumerate(sorted((b for b in osm.load()["benches"]
                                          if south <= b["lat"] <= north and west <= b["lon"] <= east),
                                         key=lambda b: b["id"]))]


def build(texts=None, wish=None):
    """Everything the start turn writes, without the model:
    {area, candidates, street_photos, rest_spots, counts, sources, own}.

    texts: the search results to choose from, {url: text}; the whole search cache when not given.
    sources: {url: text} of the pages Python read about the candidates, for the grounding checks; not for the page.
    own: {candidate id: [urls of its own pages]}.
    """
    texts = saved_results() if texts is None else texts
    d, tags = osm.load(), _tags()
    taken = photos.street(osm.AREA["bbox"])            # first: the places look for their name in these too
    refs = choose(list(texts.values()), wish)
    out, sources, own = [], {}, {}
    for i, ref in enumerate(refs):
        place, t = d["places"][ref], tags[ref]
        about = photos.about(t)
        description, source = describe(ref, t, about)
        mine = own_sources(ref, t, about)
        sources.update(mine)
        own["c%d" % (i + 1)] = sorted(mine)
        k = kind(t)
        out.append({"id": "c%d" % (i + 1), "category": place["category"], "name": place["name"],
                    "kind": {"en": k["en"], "ko": k["ko"]}, "description": description, "description_source": source,
                    "rating": None, "facts": map_facts(ref, t),
                    "place": {key: place[key] for key in ("lat", "lon", "osm_id", "access")},
                    "photos": photos.for_place(place, t, about),
                    "near_photos": photos.near(place["lat"], place["lon"], taken, most=3)})
    south, west, north, east = osm.AREA["bbox"]
    on_map = sum(1 for p in d["places"].values() if south <= p["lat"] <= north and west <= p["lon"] <= east)
    by_source = {}
    for p in taken:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
    shown = [p for p in taken if p["source"] in photos.STREET_LEVEL]
    shown += [p for p in taken if p["source"] not in photos.STREET_LEVEL][:max(0, STREET_SHOWN - len(shown))]
    counts = {"places_on_map": on_map, "places_shown": len(out),
              "photos_found": sum(len(c["photos"]) for c in out) + len(taken), "street_photos": len(taken),
              "photo_sources": by_source, "rest_spots": 0}
    spots = rest_spots(taken)
    counts["rest_spots"] = len(spots)
    return {"area": area(True), "candidates": out, "street_photos": shown[:STREET_SHOWN], "rest_spots": spots,
            "counts": counts, "sources": sources, "own": own}


def attach_photos(model):
    """Real photos taken near each stop, along each walk and near each bench of a route, and how many have none.

    Adds `photos` to every stop, leg and bench, and `photo_counts` to the model. Nothing farther than 60 m.
    """
    taken = photos.street(osm.AREA["bbox"])
    for stop in model["stops"]:
        stop["photos"] = photos.near(stop["lat"], stop["lon"], taken, most=3)
    for leg in model["legs"]:
        leg["photos"] = photos.along(leg["line"], taken, most=6)
    for bench in model["benches"]:
        bench["photos"] = photos.near(bench["lat"], bench["lon"], taken, most=2)
    model["photo_counts"] = {
        name: {"with": sum(1 for x in model[key] if x["photos"]), "without": sum(1 for x in model[key] if not x["photos"])}
        for name, key in (("stops", "stops"), ("walks", "legs"), ("benches", "benches"))}
    return model


def thin(candidate):
    """True when the description is only Wikidata's few words ("Observation deck in Japan."): the scout may
    replace it with a fuller one from a search result, under the same checks."""
    source = candidate.get("description_source") or {}
    return bool(candidate.get("description")) and str(source.get("url", "")).startswith("https://www.wikidata.org/")


def names_of(candidate):
    place = osm.load()["places"].get(candidate["place"]["osm_id"], {})
    return [candidate["name"], place.get("name_local")] + list(place.get("names") or [])


def check(candidate, seen):
    """Problems with one candidate as it stands; an empty list means everything shown has a source. See guards."""
    problems = guards.ground_option(candidate, seen)
    problems += guards.ground_description(candidate, seen)
    problems += guards.ground_rating(candidate, seen, names_of(candidate))
    problems += ["photo_without_credit:%s" % p.get("source_url", "") for p in candidate.get("photos", [])
                 if not photos.has_credit(p)]
    place = osm.load()["places"].get(candidate["place"]["osm_id"])
    if not place or candidate["name"] != place["name"]:
        problems.append("name_not_the_maps")
    elif any(candidate["place"][k] != place[k] for k in ("lat", "lon", "access")):
        problems.append("place_changed")
    return problems


def check_addition(candidate, item, seen, own):
    """What a model may add to a candidate. Returns (changes, problems): only checked additions are in changes.

    item: {description_en, description_ko, source_url, quote, rating_value, rating_source_url, rating_quote, facts}.
    seen: the screened pages of this session {url: text}. own: the urls of the candidate's own pages.
    A page from the web search must name the place, or what it says is not about this place.
    """
    names, changes, problems = names_of(candidate), {}, []

    def about_this_place(url):
        return url in own or photos.names_place(seen.get(url, ""), names)

    old = candidate.get("description")
    en, ko = str(item.get("description_en") or "").strip(), str(item.get("description_ko") or "").strip()
    replace = thin(candidate) and bool(en) and bool(item.get("source_url"))
    if old and old.get("en") and not old.get("ko") and ko and not replace:   # only the Korean is missing
        trial = dict(candidate, description={"en": old["en"], "ko": ko})
        failed = guards.ground_description(trial, seen)
        if failed:
            problems += failed
        else:
            changes["description"] = trial["description"]
    elif (not old or replace) and en:
        source = {"url": item.get("source_url") or "", "quote": str(item.get("quote") or "")}
        trial = dict(candidate, description={"en": en, "ko": ko}, description_source=source)
        failed = guards.ground_description(trial, seen)
        if not failed and not about_this_place(source["url"]):
            failed = ["description_source_does_not_name_the_place"]
        if not failed and osm.overclaims(en):
            failed = ["description.overclaims"]
        if not failed:        # sentence by sentence: what the page does not support is cut, not shown
            supported, dropped = guards.ground_written_description(trial["description"], seen[source["url"]])
            problems += ["description_sentence_not_in_source:%s" % d[:60] for d in dropped]
            if supported is None:
                failed = ["description_not_supported_by_its_source"]
            else:
                trial["description"] = supported
                if old and not supported["ko"] and old.get("ko"):       # keep the Korean copied from its own page
                    trial["description"]["ko"] = old["ko"]
                    source["ko"] = (candidate.get("description_source") or {}).get("ko") \
                        or {k: candidate["description_source"][k] for k in ("url", "quote")}
        if failed:
            problems += failed
        else:
            changes.update(description=trial["description"], description_source=source)
    if item.get("rating_value") and not candidate.get("rating"):
        rating = {"value": str(item["rating_value"]), "source_url": item.get("rating_source_url") or "",
                  "quote": str(item.get("rating_quote") or "")}
        failed = guards.ground_rating({"rating": rating}, seen, names)
        if failed:
            problems += failed
        else:
            changes["rating"] = rating
    facts = []
    for fact in item.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        failed = guards.ground_option({"facts": [fact]}, seen)
        if not failed and not about_this_place(fact.get("source_url")):
            failed = ["fact_source_does_not_name_the_place:%s" % fact.get("label", "")]
        if failed:
            problems += failed
        else:
            facts.append({k: str(fact.get(k) or "") for k in ("label", "value", "source_url", "quote")})
    if facts:
        changes["facts"] = candidate.get("facts", []) + facts[:4]
    return changes, problems
