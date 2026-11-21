"""Drill: the page reads its areas from frontend/data/areas.json and no longer knows one area by fixed path.

Free: no network, no key, no model, no browser. It reads the data and the page's source as text.
The page itself is walked in a real browser by frontend/dev/check_page.py.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")
failed = []


def check(ok, what):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        failed.append(what)


def read(path):
    with open(os.path.join(FRONTEND, path), encoding="utf-8") as source:
        return source.read()


areas = json.loads(read("data/areas.json"))
entries = areas["areas"]
check(any(entry["key"] == areas["default"] for entry in entries), "the default area is one of the areas")
check(len({entry["key"] for entry in entries}) == len(entries), "every area has its own key")

for entry in entries:
    key = entry["key"]
    for part in ("map", "candidates", "run"):
        path = entry.get(part)
        if part == "run" and path is None:
            continue    # an area without a saved run gets no card
        # the page fetches a file of an area only when its path looks like this (frontend/js/api.js, dataPath)
        check(isinstance(path, str) and re.fullmatch(r"data/[\w./-]+\.json", path) and ".." not in path, f"{key}: {part} is a file below the page's data folder ({path})")
        check(isinstance(path, str) and os.path.exists(os.path.join(FRONTEND, path)), f"{key}: {part} is there ({path})")
    if entry.get("run"):
        run = json.loads(read(entry["run"]))
        check((run.get("area") or {}).get("key", "shibuya") == key, f"{key}: its saved run is a run of this area")
        check((run.get("area") or {}).get("name") == entry["name"], f"{key}: the run and the list say the same name ({entry['name']})")
        check(bool((run.get("spatial_model") or {}).get("stops")), f"{key}: its saved run holds a route")
    drawn = json.loads(read(entry["map"]))
    check(isinstance(drawn.get("origin"), dict) and isinstance(drawn.get("ways"), list), f"{key}: its map file has its own origin and streets")
    photo = entry.get("photo")
    if photo and photo.get("thumb_url"):
        check(os.path.exists(os.path.join(FRONTEND, photo["thumb_url"])), f"{key}: the picture of its card is there ({photo['thumb_url']})")
    check(all(word == word.lower() for word in entry.get("words", [])) and entry.get("words"), f"{key}: its words are lower-case, as the page compares them")
    check(any(word in entry["example"].lower() for word in entry["words"]), f"{key}: its example sentence names it")

origins = {json.dumps(json.loads(read(entry["map"]))["origin"], sort_keys=True) for entry in entries}
check(len(origins) == len(entries), "no two areas share a map origin, so a map file must not stay loaded for another area")

api = read("js/api.js")
main = read("js/main.js")
plan = read("js/plan.js")
walk = read("js/walk/main.js")
check("data/areas.json" in api and "data/areas.json" in walk, "the page and the phone page read data/areas.json")
check("asksForShibuya" not in main and "onlyShibuya" not in main, "the page no longer decides by the one word Shibuya")
check(not re.search(r't\("(Shibuya|Tokyo, Japan|Photo of Shibuya)"\)', main + plan), "no screen writes the name Shibuya by hand")
check(not re.search(r'readJson\("data/(run|candidates|map)\.json"\)', walk), "the phone page reads the files of the area, not three fixed paths")
check('get("area")' in walk and "?area=" in read("js/handoff.js"), "the phone link names the area and the phone page reads it")
check("ready-credit" not in plan and "credit" not in plan.split("function renderLanding")[1].split("function ")[0], "a card under Last runs shows no credit line")

if failed:
    print(f"{len(failed)} check(s) failed")
    sys.exit(1)
print("all checks passed")
