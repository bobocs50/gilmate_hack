"""Real photos and cited texts for places, from sources that state author and licence. No key needed.

- Photos of a place: Wikimedia Commons, found by the place's own map tags (wikimedia_commons, wikidata) or by a
  search whose hit names the place. A photo without a stated author or licence is never returned.
- Street photos: Mapillary when MAPILLARY_TOKEN is set when the program runs, otherwise photos on Wikimedia
  Commons that carry coordinates inside the area.
- What a place is: its Wikidata entry and the first sentences of its Wikipedia pages (English, Korean).

Every answer is saved on disk (data/cache/photos, data/cache/wiki) and the folders are committed, so a place asked
for a second time costs no request and a demo needs no network. With GILMATE_OFFLINE=1 nothing is ever fetched:
what is not saved is "not found". No model, no ADK.
"""
import html
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import areas

HERE = os.path.dirname(os.path.abspath(__file__))
WIKI_CACHE = os.environ.get("GILMATE_WIKI_CACHE") or os.path.join(HERE, "..", "data", "cache", "wiki")
# Per area (gilmate/areas.py), Shibuya unless areas.use() chose another:
# PHOTO_CACHE  the saved answers of Commons and Mapillary (data/cache/photos; Hongdae: data/cache/hongdae/photos)
# THUMBS       small copies of the place photos, shown by the page without network (frontend/data/photos)
# THUMBS_URL   the same folder as the page sees it ("data/photos"; Hongdae: "data/hongdae/photos")
# LOCAL_WORDS  what a photo without coordinates must say to count as taken here; SEARCH_WORD, AREA_PHOTO: see areas.py
PHOTO_CACHE = THUMBS = THUMBS_URL = LOCAL_WORDS = SEARCH_WORD = AREA_PHOTO = None
COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
AGENT = "gilmate-hackathon/0.1 (place photo lookup; python-urllib)"   # a generic client name, no personal details
PER_PLACE = 4
THUMB_WIDTH = 500                  # one of Wikimedia's standard thumbnail widths
INFO = {"prop": "imageinfo|coordinates", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(THUMB_WIDTH),
        "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|DateTimeOriginal|ImageDescription|Categories",
        "coprop": "type", "colimit": "50"}


def apply_area(area):
    """Point the photo caches and the small copies at one area (called by areas.use, and once below for Shibuya)."""
    global PHOTO_CACHE, THUMBS, THUMBS_URL, LOCAL_WORDS, SEARCH_WORD, AREA_PHOTO
    PHOTO_CACHE = area["photo_cache"]
    THUMBS_URL = areas.page_file(area, "photos")
    THUMBS = os.path.join(HERE, "..", "frontend", *THUMBS_URL.split("/"))
    LOCAL_WORDS, SEARCH_WORD, AREA_PHOTO = area["local_words"], area["search_word"], area["area_photo"]


apply_area(areas.current())


def offline():
    return bool(os.environ.get("GILMATE_OFFLINE"))


def _get(url, params=None, raw=False):
    if params:
        url += "?" + urllib.parse.urlencode(dict(params, format="json"))
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for attempt in range(6):                          # "too many requests": wait as long as asked, then ask again
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                body = answer.read()
            break
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(min(60, int(error.headers.get("Retry-After") or 10) + 2))
    time.sleep(1.0)                                   # be a polite client
    return body if raw else json.loads(body)


def _plain(text):
    """Text of an HTML snippet from the photo's page, on one line."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(text or ""))).split())


def _fold(text):
    return re.sub(r"[^\w]+", " ", str(text or "").casefold()).strip()


def _meta(info, key):
    return _plain((info.get("extmetadata") or {}).get(key, {}).get("value"))


def photo_from_page(page):
    """One Commons file page as a photo, or None when it states no author or no licence, or is not a photograph."""
    info = (page.get("imageinfo") or [{}])[0]
    credit, licence = _meta(info, "Artist")[:120], _meta(info, "LicenseShortName")
    if info.get("mime") != "image/jpeg" or not credit or not licence or not info.get("descriptionurl"):
        return None
    if info.get("width", 0) < 640 or not info.get("thumburl"):
        return None
    taken = re.match(r"\d{4}(-\d{2}(-\d{2})?)?", _meta(info, "DateTimeOriginal"))
    where = next((c for c in page.get("coordinates") or [] if c.get("type") in (None, "camera")), None)
    return {"url": info["url"].split("?")[0], "thumb_url": info["thumburl"].split("?")[0],
            "width": info["width"], "height": info["height"], "credit": credit, "licence": licence,
            "licence_url": _meta(info, "LicenseUrl") or None, "source_url": info["descriptionurl"],
            "taken_at": taken.group(0) if taken and not taken.group(0).startswith("0000") else None,
            "title": page.get("title", ""),
            "named": " ".join([page.get("title", ""), _meta(info, "ImageDescription")])[:400],
            "about": " ".join([page.get("title", ""), _meta(info, "ImageDescription"), _meta(info, "Categories")])[:600],
            "lat": where["lat"] if where else None, "lon": where["lon"] if where else None}


def _pages(params):
    answer = _get(COMMONS, dict(INFO, action="query", **params))
    pages = list((answer.get("query") or {}).get("pages", {}).values())
    return sorted(pages, key=lambda p: p.get("index", 0))


def names_place(text, names):
    """True when the text names the place: one of its names stands in it as whole words."""
    folded = " %s " % _fold(text)
    return any(len(_fold(n)) >= 3 and " %s " % _fold(n) in folded for n in names if n)


def is_local(text):
    return any(word in str(text).casefold() for word in LOCAL_WORDS)


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _file_name(osm_id):
    return osm_id.replace("/", "_")


def _keep_thumb(photo, name):
    """Save the small copy next to the page and point thumb_url at it. The full picture stays at the source."""
    os.makedirs(THUMBS, exist_ok=True)
    path = os.path.join(THUMBS, name)
    if not os.path.exists(path):
        with open(path, "wb") as handle:
            handle.write(_get(photo["thumb_url"], raw=True))
    photo["thumb_source_url"] = photo["thumb_url"]
    photo["thumb_url"] = "%s/%s" % (THUMBS_URL, name)


def public(photo):
    """The keys of a photo that the session state carries (CONTRACT.md 7.2)."""
    return {k: photo.get(k) for k in ("url", "thumb_url", "width", "height", "credit", "licence", "source_url", "taken_at")}


def has_credit(photo):
    return bool(photo.get("credit") and photo.get("licence") and photo.get("source_url") and photo.get("url"))


def _metres_apart(a_lat, a_lon, b_lat, b_lon):
    return math.hypot((a_lat - b_lat) * 111320.0, (a_lon - b_lon) * 111320.0 * math.cos(math.radians(a_lat)))


def of_this_place(photo, place, names, how):
    """Whether a photo found at the source may be shown as a photo of this place. Fails closed.

    how: "depicts" (the picture Wikidata names for the place), "category" (filed under the place's own Commons
    category), "search" or "nearby" (found by name or by where it was taken).
    - A photo with coordinates must have been taken within 300 m of the place (150 m for "search" and "nearby").
    - Without coordinates, a "depicts" or "category" photo must say the area's name (Shibuya) in its title, description or
      categories (a place that moved, or a chain, has pictures from elsewhere). A "search" or "nearby" photo
      without coordinates is never taken.
    - A "search" or "nearby" photo must also name the place in its title or description.
    """
    if re.search(r"\blogo\b", photo.get("title", ""), re.I):
        return False
    by_name = how in ("search", "nearby")
    if photo.get("lat") is not None:
        if _metres_apart(photo["lat"], photo["lon"], place["lat"], place["lon"]) > (150 if by_name else 300):
            return False
    elif by_name or not is_local(photo.get("about", "")):
        return False
    return not by_name or names_place(photo.get("named", photo.get("about", "")), names)


def for_place(place, tags, about=None):
    """Up to four photos of one place: [{url, thumb_url, width, height, credit, licence, source_url, taken_at}].

    place: the map's entry (osm_id, name, name_local, lat, lon). tags: its map tags. about: its saved Wikidata
    entry, if any. Which photos count is decided by of_this_place.
    """
    path = os.path.join(PHOTO_CACHE, _file_name(place["osm_id"]) + ".json")
    if os.path.exists(path):
        return [public(p) for p in _read(path)["photos"] if has_credit(p)]
    if offline():
        return []
    names = [place["name"], place.get("name_local")] + list(place.get("names") or [])
    found, asked = [], []

    def take(photos_found, how):
        for photo in photos_found:
            if photo and of_this_place(photo, place, names, how) \
                    and photo["source_url"] not in {f["source_url"] for f in found}:
                found.append(dict(photo, found_by=how))

    category = tags.get("wikimedia_commons") or ""
    if not category.startswith("Category:") and (about or {}).get("commons_category"):
        category = "Category:" + about["commons_category"]
    if (about or {}).get("image"):
        asked.append("File:" + about["image"])
        take(map(photo_from_page, _pages({"titles": "File:" + about["image"]})), "depicts")
    if category.startswith("Category:"):
        asked.append(category)
        take(map(photo_from_page, _pages({"generator": "categorymembers", "gcmtitle": category, "gcmtype": "file",
                                         "gcmlimit": "50"})), "category")
    if len(found) < PER_PLACE:
        asked.append("photos taken within 150 m that name the place")
        take(_street_saved(), "nearby")
    if len(found) < 2 and len(place["name"]) >= 5:
        query = '"%s" %s' % (place["name"], SEARCH_WORD)
        asked.append("search: " + query)
        take(map(photo_from_page, _pages({"generator": "search", "gsrsearch": query, "gsrnamespace": "6",
                                         "gsrlimit": "20"})), "search")
    first, rest = found[:1], found[1:]
    rest.sort(key=lambda p: (not names_place(p["title"], names), not 1.2 <= p["width"] / p["height"] <= 1.9,
                             -(int((p["taken_at"] or "0")[:4]))))
    chosen = (first + rest)[:PER_PLACE]
    for i, photo in enumerate(chosen):
        _keep_thumb(photo, "%s_%d.jpg" % (_file_name(place["osm_id"]), i + 1))
    _save(path, {"place": place["osm_id"], "name": place["name"], "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "source": "Wikimedia Commons", "asked": asked, "photos": chosen})
    return [public(p) for p in chosen]


def _street_saved():
    """The saved Commons photos with coordinates, as whole photos (for_place looks for the place's name in them)."""
    path = os.path.join(PHOTO_CACHE, "street_commons.json")
    return _read(path).get("whole", []) if os.path.exists(path) else []


def for_area(name=None, category=None):
    """One real photo of the area for the front page: {url, thumb_url, width, height, credit, licence, source_url,
    taken_at}, or None. The newest landscape photo in the area's Commons category (for Shibuya the crossing's) that
    names the area."""
    name, category = name or AREA_PHOTO["name"], category or AREA_PHOTO["category"]
    path = os.path.join(PHOTO_CACHE, "area.json")
    if os.path.exists(path):
        saved = _read(path)["photos"]
        return public(saved[0]) if saved and has_credit(saved[0]) else None
    if offline():
        return None
    found = [p for p in map(photo_from_page, _pages({"generator": "categorymembers", "gcmtitle": category,
                                                     "gcmtype": "file", "gcmlimit": "50"}))
             if p and is_local(p["about"]) and 1.3 <= p["width"] / p["height"] <= 1.9]
    found.sort(key=lambda p: (-(int((p["taken_at"] or "0")[:4])), p["title"]))
    chosen = found[:1]
    for photo in chosen:
        _keep_thumb(photo, AREA_PHOTO["file"])
    _save(path, {"place": "area", "name": name, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "source": "Wikimedia Commons", "asked": [category], "photos": chosen})
    return public(chosen[0]) if chosen else None


def _inside(lat, lon, bbox):
    south, west, north, east = bbox
    return lat is not None and south <= lat <= north and west <= lon <= east


STREET_LEVEL = ("mapillary", "kartaview")      # taken from the street; a Commons photo is never called street view
NEAR_M = 60                                    # nothing farther than this is attached to a bench, a stop or a walk


def _grid(bbox, n):
    south, west, north, east = bbox
    return [(south + (north - south) * (i + 0.5) / n, west + (east - west) * (j + 0.5) / n)
            for i in range(n) for j in range(n)]


def _thin(found, apart_m=12):
    """Frames of one drive are a metre apart; keep one about every apart_m metres."""
    kept = []
    for photo in sorted(found, key=lambda p: p["id"]):
        if all(_metres_apart(photo["lat"], photo["lon"], k["lat"], k["lon"]) >= apart_m for k in kept):
            kept.append(photo)
    return kept


def _mapillary(bbox, token):
    """Street photos from Mapillary's Graph API, asked for in nine parts of the area so no part is cut short."""
    south, west, north, east = bbox
    found = {}
    for i in range(3):
        for j in range(3):
            part = (west + (east - west) * j / 3, south + (north - south) * i / 3,
                    west + (east - west) * (j + 1) / 3, south + (north - south) * (i + 1) / 3)
            answer = _get("https://graph.mapillary.com/images", {
                "access_token": token, "fields": "id,geometry,captured_at,thumb_256_url,thumb_1024_url,creator",
                "bbox": "%f,%f,%f,%f" % part, "limit": "2000"})
            for item in answer.get("data", []):
                lon, lat = item["geometry"]["coordinates"]
                if item.get("thumb_256_url") and _inside(lat, lon, bbox):
                    found[item["id"]] = {
                        "id": "m%s" % item["id"], "lat": round(lat, 6), "lon": round(lon, 6),
                        "thumb_url": item["thumb_256_url"], "url": item.get("thumb_1024_url") or item["thumb_256_url"],
                        "credit": "Mapillary contributors", "licence": "CC BY-SA 4.0",
                        "creator": (item.get("creator") or {}).get("username"),
                        "source_url": "https://www.mapillary.com/app/?pKey=%s" % item["id"],
                        "taken_at": time.strftime("%Y-%m-%d", time.gmtime(item["captured_at"] / 1000))
                        if item.get("captured_at") else None, "source": "mapillary"}
    newest_first = sorted(found.values(), key=lambda p: (p["taken_at"] or "", p["id"]), reverse=True)
    kept = []
    for photo in newest_first:                        # one about every 12 m, the newest of each spot
        if all(_metres_apart(photo["lat"], photo["lon"], k["lat"], k["lon"]) >= 12 for k in kept):
            kept.append(photo)
    return sorted(kept, key=lambda p: p["id"])


def _kartaview(bbox):
    """Street-level photos from KartaView's public API (no key). Each names its contributor; CC BY-SA 4.0."""
    found = {}
    for lat, lon in _grid(bbox, 5):
        answer = {}
        for size in ("100", "40", "15"):            # its server fails on some large answers: ask for less
            try:
                answer = _get("https://api.kartaview.org/2.0/photo/", {
                    "lat": "%f" % lat, "lng": "%f" % lon, "radius": "100", "itemsPerPage": size, "join": "user"})
                break
            except (urllib.error.URLError, ValueError):
                continue                             # a cell that never answers has no street photos: fewer, not wrong
        for item in (answer.get("result") or {}).get("data") or []:
            user = (item.get("user") or {}).get("username")
            plat, plon = float(item.get("lat") or 0), float(item.get("lng") or 0)
            if not user or not item.get("imageThUrl") or item.get("visibility") != "public" \
                    or not _inside(plat, plon, bbox):
                continue
            found[item["id"]] = {
                "id": "k%s" % item["id"], "lat": round(plat, 6), "lon": round(plon, 6),
                "thumb_url": item["imageThUrl"], "url": item.get("imageProcUrl") or item["imageLthUrl"],
                "credit": "%s, KartaView" % user, "licence": "CC BY-SA 4.0",
                "source_url": "https://kartaview.org/details/%s/%s" % (item["sequenceId"], item["sequenceIndex"]),
                "taken_at": str(item.get("shotDate") or "")[:10] or None, "source": "kartaview"}
    return _thin(list(found.values()))


def _commons_with_coordinates(bbox):
    out, whole, seen = [], [], set()
    for lat, lon in _grid(bbox, 5):                  # points whose circles cover the area
        for page in _pages({"generator": "geosearch", "ggscoord": "%f|%f" % (lat, lon), "ggsradius": "110",
                            "ggsnamespace": "6", "ggslimit": "50"}):
            photo = photo_from_page(page)
            if photo and photo["source_url"] not in seen and _inside(photo["lat"], photo["lon"], bbox):
                seen.add(photo["source_url"])
                whole.append(photo)
                out.append({"id": "w%d" % page["pageid"], "lat": round(photo["lat"], 6),
                            "lon": round(photo["lon"], 6), "thumb_url": photo["thumb_url"], "url": photo["url"],
                            "credit": photo["credit"], "licence": photo["licence"],
                            "source_url": photo["source_url"], "taken_at": photo["taken_at"], "source": "commons"})
    return sorted(out, key=lambda p: p["id"]), whole


def street(bbox):
    """Every saved photo that was taken inside the area and says where: the pictures of where to go.

    [{id, lat, lon, thumb_url, url, credit, licence, source_url, taken_at, source}]. Street-level photos come from
    Mapillary when MAPILLARY_TOKEN is set when the program runs, otherwise from KartaView, which needs no key.
    Photos on Wikimedia Commons that carry coordinates are added (source "commons": not street view). Each source
    is asked once and saved in its own file.
    """
    token = os.environ.get("MAPILLARY_TOKEN")
    out = []
    for source in (("mapillary",) if token or os.path.exists(os.path.join(PHOTO_CACHE, "street_mapillary.json"))
                   else ("kartaview",)) + ("commons",):
        path = os.path.join(PHOTO_CACHE, "street_%s.json" % source)
        if os.path.exists(path):
            out += _read(path)["photos"]
            continue
        if offline() or (source == "mapillary" and not token):
            continue
        whole = []
        if source == "mapillary":
            found = _mapillary(bbox, token)
        elif source == "kartaview":
            found = _kartaview(bbox)
        else:
            found, whole = _commons_with_coordinates(bbox)
        _save(path, {"source": source, "bbox": bbox, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "photos": found, "whole": whole})
        out += found
    return out


def near(lat, lon, taken, most=3, within_m=NEAR_M):
    """The photos taken near a point, each with distance_m from it: street-level ones first, then the nearest."""
    out = []
    for photo in taken:
        off = _metres_apart(lat, lon, photo["lat"], photo["lon"])
        if off <= within_m:
            out.append(dict(photo, distance_m=round(off)))
    out.sort(key=lambda p: (p["source"] not in STREET_LEVEL, p["distance_m"], p["id"]))
    return out[:most]


def along(line, taken, most=6, within_m=NEAR_M):
    """Photos taken along a walk, in walking order. line: [[lon, lat]]. distance_m is to the nearest point of the line."""
    out = []
    for photo in taken:
        offs = [(_metres_apart(lat, lon, photo["lat"], photo["lon"]), i) for i, (lon, lat) in enumerate(line)]
        off, at = min(offs)
        if off <= within_m:
            out.append((at, off, dict(photo, distance_m=round(off))))
    from_the_street = [t for t in out if t[2]["source"] in STREET_LEVEL]
    if len(from_the_street) >= 2:                     # street photos show the way; others only where there are none
        out = from_the_street
    out.sort(key=lambda t: (t[0], t[1]))
    if len(out) > most:                               # spread over the walk instead of the first few metres
        out = [out[round(i * (len(out) - 1) / (most - 1))] for i in range(most)]
    return [photo for _, _, photo in out]


def _sentences(text, n=2, most=320):
    parts = re.split(r"(?<=[.!?。다])\s+", " ".join(str(text or "").split()))
    out = ""
    for part in parts[:n]:
        if out and len(out) + len(part) > most:
            break
        out = (out + " " + part).strip()
    return out


def about(tags):
    """What Wikidata and Wikipedia say about a place that carries a wikidata map tag, or None.

    {id, url, labels: {en, ko}, descriptions: {en, ko}, extracts: {en|ko: {url, text}}, image, commons_category}
    """
    qid = tags.get("wikidata") or ""
    if not re.fullmatch(r"Q\d+", qid):
        return None
    path = os.path.join(WIKI_CACHE, qid + ".json")
    if os.path.exists(path):
        return _read(path)
    if offline():
        return None
    entity = _get(WIKIDATA, {"action": "wbgetentities", "ids": qid, "props": "labels|descriptions|sitelinks|claims",
                             "languages": "en|ko", "sitefilter": "enwiki|kowiki"})["entities"][qid]

    def claim(prop):
        for c in entity.get("claims", {}).get(prop, []):
            value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, str):
                return value
        return None

    out = {"id": qid, "url": "https://www.wikidata.org/wiki/" + qid, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "labels": {k: v["value"] for k, v in entity.get("labels", {}).items()},
           "descriptions": {k: v["value"] for k, v in entity.get("descriptions", {}).items()},
           "extracts": {}, "image": claim("P18"), "commons_category": claim("P373")}
    for lang in ("en", "ko"):
        title = entity.get("sitelinks", {}).get(lang + "wiki", {}).get("title")
        if title:
            page = _get("https://%s.wikipedia.org/api/rest_v1/page/summary/%s"
                        % (lang, urllib.parse.quote(title.replace(" ", "_"), safe="")))
            if page.get("extract"):
                out["extracts"][lang] = {
                    "url": page.get("content_urls", {}).get("desktop", {}).get("page")
                    or "https://%s.wikipedia.org/wiki/%s" % (lang, urllib.parse.quote(title.replace(" ", "_"))),
                    "text": page["extract"], "first": _sentences(page["extract"])}
    _save(path, out)
    return out
