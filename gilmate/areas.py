"""The areas Gilmate has map data for: one row per area, and everything that is tied to a place is in its row.

Pure Python: no network, no model, no ADK. gilmate/osm.py, candidates.py and photos.py work on one area at a time;
`use(key)` switches all three. Each tool calls it with the area of its session (state["area"]["key"]) before it
reads the map, so one server can hold a session for Shibuya and one for Hongdae. A session without an area is
Shibuya, as before.

A row:
  key, name        "hongdae", "Hongdae, Seoul" (the name is what the page and the audit show)
  bbox             [south, west, north, east]; a place, a bench or a photo outside it is never offered
  origin           (lat, lon) of the point that is 0, 0 in the map drawing
  extract          the saved OpenStreetMap extract (scripts/fetch_osm.py writes it)
  page             the folder below frontend/ with this area's files: map.json, candidates.json, run.json, photos/
  photo_cache      where the answers of Wikimedia Commons and Mapillary are saved (committed)
  words            a request that holds one of these asks for this area (lower case)
  local_words      a photo without coordinates must say one of these to count as a photo from here
  search_word      the area's name in a photo search on Wikimedia Commons
  area_photo       the Commons category the front page photo is taken from, and the file its small copy is saved as
  hints            well-known places that are in the extract, named in the web searches (see osm.SEARCH_HINTS):
                   "see" the sights, "other" the places to eat, "shop" the shops (Shibuya's shops stand in its
                   query itself, and it has "sushi" and "ramen" for the older page's food answers)
  queries, rated   the exact web searches per category; {places} and {shops} are filled from hints. A saved search
                   is found by its exact words, so changing a query costs a new search
  specific_food    cuisine tags that give a place to eat its own kind ("Sushi restaurant")
  local_food       the kinds of places to eat that are offered: the food of the place you are visiting
  landmarks        building names drawn as landmarks on the map
  bearing_deg      how far the map drawing is turned
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
DEFAULT = "shibuya"

AREAS = {
    "shibuya": {
        "key": "shibuya", "name": "Shibuya, Tokyo", "bbox": [35.6570, 139.6975, 35.6632, 139.7050],
        "origin": (35.6601, 139.70125),
        "extract": os.path.join(DATA, "shibuya_osm.json"),
        "page": "data",
        "photo_cache": os.environ.get("GILMATE_PHOTO_CACHE") or os.path.join(DATA, "cache", "photos"),
        "words": ("shibuya", "渋谷", "시부야"),
        "local_words": ("shibuya", "渋谷", "시부야"),
        "search_word": "Shibuya",
        "area_photo": {"name": "Shibuya", "category": "Category:Shibuya Crossing", "file": "area_shibuya.jpg"},
        "hints": {
            "see": ["Hachiko statue", "Shibuya Sky", "Myth of Tomorrow", "Miyashita Park"],
            "sushi": ["Uobei", "Sushiro", "Kura Sushi", "Sushi no Midori", "Sushizanmai"],
            "ramen": ["Ichiran", "Mouko Tanmen Nakamoto", "Tenkaippin", "Izobachi Miso Ramen"],
            "other": ["Ootoya", "Gyukatsu Motomura", "Tempura Tentora", "Fuji Soba"],
        },
        "queries": {
            "see": ["Shibuya Tokyo best sights to visit observation deck landmark opening hours price",
                    "Shibuya Tokyo what to see {places} what to know before visiting"],
            "shop": ["Shibuya Tokyo best shopping souvenirs department store variety store what to buy"],
            "eat": ["Shibuya Tokyo best {food} restaurant recommended price lunch",
                    "Shibuya station {kind} {places} price what to order"],
        },
        "rated": {
            "see": "Shibuya {places} visitor rating reviews stars",
            "shop": "Shibuya souvenir shopping Shibuya Parco, Shibuya 109, Shibuya Hikarie, Loft, Mega Don Quijote rating reviews",
            "eat": "Shibuya top rated restaurants {places} rating out of 5 reviews",
        },
        "specific_food": ("sushi", "ramen", "soba", "udon", "tempura", "yakiniku", "tonkatsu", "beef_bowl", "curry",
                          "noodle", "burger", "coffee_shop", "japanese"),
        "local_food": {"sushi", "ramen", "soba", "udon", "tempura", "yakiniku", "tonkatsu", "beef_bowl", "curry",
                       "noodle", "japanese", "restaurant"},
        "landmarks": r"Scramble Square|スクランブルスクエア|Hikarie|ヒカリエ|109|PARCO|パルコ|MIYASHITA|ミヤシタ",
        "bearing_deg": 24,
    },
    "hongdae": {
        "key": "hongdae", "name": "Hongdae, Seoul", "bbox": [37.5506, 126.9196, 37.5576, 126.9274],
        "origin": (37.5541, 126.9235),
        "extract": os.path.join(DATA, "hongdae_osm.json"),
        "page": "data/hongdae",
        "photo_cache": os.path.join(DATA, "cache", "hongdae", "photos"),
        "words": ("hongdae", "hong-dae", "hong dae", "hongik", "홍대", "홍익대", "弘大", "ホンデ"),
        "local_words": ("hongdae", "hongik", "홍대", "홍익", "seogyo", "서교", "mapo", "마포"),
        "search_word": "Hongdae",
        "area_photo": {"name": "Hongdae", "category": "Category:Hongdae", "file": "area_hongdae.jpg"},
        "hints": {
            "see": ["Trick Eye Museum", "Hongdae Mural Street", "Red Road", "Hongdae Street", "Love Museum"],
            "other": ["Hongdae Dakgalbi", "Mimine", "Kong Bul", "Hongik Sutbul Galbi", "KyoChon"],
            "shop": ["Kakao Friends Store", "Pop Mart", "Artbox", "Olive Young", "K-Pop Square"],
        },
        "queries": {
            "see": ["Hongdae Seoul best sights to visit street art landmark opening hours price",
                    "Hongdae Seoul what to see {places} what to know before visiting"],
            "shop": ["Hongdae Seoul best shopping souvenirs K-pop stationery character shops what to buy"],
            "eat": ["Hongdae Seoul best Korean restaurant recommended price lunch",
                    "Hongik University station Korean restaurants {places} price what to order"],
        },
        "rated": {
            "see": "Hongdae {places} visitor rating reviews stars",
            "shop": "Hongdae souvenir shopping {shops} rating reviews",
            "eat": "Hongdae top rated restaurants {places} rating out of 5 reviews",
        },
        "specific_food": ("korean", "barbecue", "chicken", "noodle", "dumplings", "seafood", "burger", "coffee_shop",
                          "japanese"),
        "local_food": {"korean", "barbecue", "chicken", "noodle", "dumplings", "seafood", "restaurant"},
        "landmarks": r"Hongik|홍익|AK ?Plaza|AK플라자|Sangsang|상상마당|KT&G",
        "bearing_deg": 0,
    },
}

_current = [DEFAULT]


def which(text):
    """The key of the area the words ask for, or None. Python decides this, not the model.

    When the words name two areas, the one named first counts.
    """
    folded = str(text or "").casefold()
    found = [(folded.find(word), key) for key, area in AREAS.items() for word in area["words"] if word in folded]
    return min(found)[1] if found else None


def page_file(area, name):
    """A file of this area as the page sees it: "data/map.json" for Shibuya, "data/hongdae/map.json" for Hongdae."""
    return "%s/%s" % (area["page"], name)


def names():
    return [area["name"] for area in AREAS.values()]


def current():
    return AREAS[_current[0]]


def use(key=None):
    """Switch the map, the searches and the photo caches to one area. An unknown or missing key is Shibuya."""
    area = AREAS.get(key) or AREAS[DEFAULT]
    if area["key"] != _current[0]:
        from . import candidates, osm, photos
        _current[0] = area["key"]
        for module in (osm, candidates, photos):
            module.apply_area(area)
    return area


def of_state(state):
    """Switch to the area of a session and return it. A session that has no supported area yet is Shibuya."""
    held = state.get("area") or {}
    return use(held.get("key") if held.get("supported") else DEFAULT)
