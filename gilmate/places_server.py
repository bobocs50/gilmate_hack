"""Google Places as a small MCP server of our own, standard MCP over stdio.

    python3 -m gilmate.places_server          started by the scout's MCP toolset (gilmate/places.py), not by hand

It wraps two calls of the Places API (New) over HTTPS with the key from the environment variable GOOGLE_API_KEY:

    places_search(category, area, name)   Text Search inside the area's bounding box; the query is built here:
                                          the kind of place, or one place by its name
    place_details(place_id)               Place Details for one place a search returned

Both only read. Nothing is booked, paid, sent or written outside the cache folder. The key is sent to
places.googleapis.com only and is never printed, returned or saved. An answer is always a JSON object with
"status": "ok", "unavailable" (no key, offline, timeout, an error of the API) or "refused" (a category, an area or
a place id this server does not serve). Records are screened here and again in the agent's process.

A response is saved per query in data/cache/places (GILMATE_PLACES_CACHE points at another folder), so a query
costs a call only the first time. That folder is not committed: Google's terms do not allow keeping Places
content in a public repository. With GILMATE_OFFLINE set nothing is fetched: what is not saved is "unavailable".
"""
import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request

from . import places

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://places.googleapis.com/v1/places"
TIMEOUT_S = 8
# Only these fields are asked for. rating, userRatingCount and regularOpeningHours are billed as the Enterprise SKU.
FIELDS = ("id", "displayName", "businessStatus", "primaryType", "primaryTypeDisplayName", "rating", "userRatingCount",
          "formattedAddress", "location", "regularOpeningHours.weekdayDescriptions", "accessibilityOptions",
          "googleMapsUri")
QUERIES = {"see": "tourist attractions in %s", "shop": "souvenir and gift shops in %s", "eat": "restaurants in %s"}
_PLACE_ID = re.compile(r"[A-Za-z0-9_-]{10,200}\Z")


def cache_dir():
    return os.environ.get("GILMATE_PLACES_CACHE") or os.path.join(HERE, "..", "data", "cache", "places")


def _slug(words):
    return re.sub(r"[^a-z0-9]+", "-", str(words).lower()).strip("-")


def _unavailable(reason):
    return {"status": "unavailable", "source": places.SOURCE, "reason": reason}


def _fetch(url, mask, body=None):
    """One HTTPS call to the Places API. Returns (json, None) or (None, reason). The key never leaves this function."""
    key = os.environ.get(places.ENV, "").strip()
    if not key:
        return None, "no_key"
    if os.environ.get("GILMATE_OFFLINE"):
        return None, "offline"
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode("utf-8"), method="GET" if body is None else "POST",
        headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": mask, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
            data = json.loads(answer.read().decode("utf-8"))
        return (data, None) if isinstance(data, dict) else (None, "bad_response")
    except urllib.error.HTTPError as error:               # the API's own status word only, never its message
        try:
            word = json.loads(error.read().decode("utf-8"))["error"]["status"]
        except Exception:
            word = ""
        return None, "http_%d%s" % (error.code, ":" + re.sub(r"[^A-Z_]", "", str(word))[:40] if word else "")
    except (socket.timeout, TimeoutError):
        return None, "timeout"
    except (urllib.error.URLError, OSError):
        return None, "network"
    except ValueError:
        return None, "bad_response"


def _saved(name):
    path = os.path.join(cache_dir(), name)
    if not os.path.exists(path):
        return None
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("response"), dict) else None
    except (OSError, ValueError):
        return None


def _save(name, record):
    try:
        os.makedirs(cache_dir(), exist_ok=True)
        json.dump(record, open(os.path.join(cache_dir(), name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass                                              # an unsaved answer is still an answer


def search(category, area="", name=""):
    """Text Search inside the bounding box of an area that has map data: one kind of place, or one place by name."""
    if category not in QUERIES:
        return {"status": "refused", "reason": "category must be see, shop or eat"}
    where = places.area_of(area)
    if not where:
        return {"status": "refused", "reason": "no map data for this area"}
    asked = " ".join(str(name or "").split())[:80]
    if asked and places.guards.screen_text(asked):
        return {"status": "refused", "reason": "name reads like an instruction"}
    name = "search_%s_%s%s.json" % (_slug(where["name"]), category, "_%s-%s" % (
        _slug(asked)[:40], hashlib.sha1(asked.casefold().encode("utf-8")).hexdigest()[:8]) if asked else "")
    saved, source = _saved(name), "saved"
    if saved is None:
        south, west, north, east = where["bbox"]
        query = "%s, %s" % (asked, where["name"]) if asked else QUERIES[category] % where["name"]
        data, problem = _fetch(API + ":searchText", ",".join("places." + f for f in FIELDS), {
            "textQuery": query, "languageCode": "en", "pageSize": 5 if asked else 20,
            "locationRestriction": {"rectangle": {"low": {"latitude": south, "longitude": west},
                                                  "high": {"latitude": north, "longitude": east}}}})
        if problem:
            return _unavailable(problem)
        saved, source = {"query": query, "area": where["name"], "bbox": where["bbox"],
                         "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "response": data}, "fresh"
        _save(name, saved)
    found = saved["response"].get("places")
    records = [places.normalise(raw) for raw in (found if isinstance(found, list) else [])]
    screened = places.screen([r for r in records if r], where["bbox"])
    return {"status": "ok", "source": source, "fixture": bool(saved.get("fixture")), "category": category,
            "area": where["name"], "fetched_at": saved.get("fetched_at", ""),
            "not_a_place": sum(1 for r in records if not r),
            "places": screened["passed"], "withheld": screened["withheld"]}


def _known_ids():
    """The place ids the saved searches returned. Details are given for these only."""
    ids = set()
    try:
        names = sorted(os.listdir(cache_dir()))
    except OSError:
        return ids
    for name in names:
        saved = _saved(name) if name.startswith("search_") and name.endswith(".json") else None
        for raw in (saved or {}).get("response", {}).get("places") or []:
            if isinstance(raw, dict) and isinstance(raw.get("id"), str):
                ids.add(raw["id"])
    return ids


def details(place_id):
    """Place Details for one place that a search of this server returned."""
    if not isinstance(place_id, str) or not _PLACE_ID.match(place_id) or place_id not in _known_ids():
        return {"status": "refused", "reason": "unknown place id: only a place a search returned"}
    name = "details_%s.json" % place_id
    saved, source = _saved(name), "saved"
    if saved is None:
        data, problem = _fetch("%s/%s?languageCode=en" % (API, place_id), ",".join(FIELDS))
        if problem:
            return _unavailable(problem)
        saved, source = {"place_id": place_id, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "response": data}, "fresh"
        _save(name, saved)
    record = places.normalise(saved["response"])
    screened = places.screen([record] if record else [])
    return {"status": "ok", "source": source, "fixture": bool(saved.get("fixture")),
            "fetched_at": saved.get("fetched_at", ""), "not_a_place": 0 if record else 1,
            "places": screened["passed"], "withheld": screened["withheld"]}


def main():
    try:
        from mcp.server.mcpserver import MCPServer as Server          # mcp 2.x
    except ImportError:
        from mcp.server.fastmcp import FastMCP as Server              # mcp 1.x
    server = Server("gilmate-places")

    @server.tool(name="places_search", description=(
        "Lists what Google Maps says about places of one kind in an area that has map data: name, type, rating "
        "with its number of ratings, address, coordinates, opening hours, the wheelchair-accessible-entrance flag "
        "where Google has it, and each place's Google Maps link. The query is built for you. "
        "category: exactly one of \"see\", \"shop\", \"eat\". area: the area's name, e.g. \"Shibuya, Tokyo\". "
        "name: leave empty for the best-known places of that kind, or give one place's name to look that place up."))
    def places_search(category: str, area: str = "", name: str = "") -> str:
        return json.dumps(search(category, area, name), ensure_ascii=False)

    @server.tool(name="place_details", description=(
        "The same facts for one place again. place_id: the place_id of a place that places_search returned."))
    def place_details(place_id: str) -> str:
        return json.dumps(details(place_id), ensure_ascii=False)

    server.run("stdio")


if __name__ == "__main__":
    main()
