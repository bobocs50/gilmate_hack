"""Write frontend/data/areas.json: the areas with map data and where the page finds each one's files. FREE.

{ default: "shibuya",
  areas: [ { key, name, bbox: [south, west, north, east], words: [...], example: "I want to visit ...",
             map, candidates, run, photos, photo } ] }

`map`, `candidates` and `run` are paths below the page folder, or null when that file is not saved; `photos` is
the folder of the small place photos; `photo` is the saved front page photo of the area (a place_photo with
credit and licence, CONTRACT.md 7.2) or null. `words` are the lower-case words by which a typed request names the area
(gilmate/areas.py decides with the same list), so the page can open the right saved run without a backend.
Run from the repo folder: python3 scripts/make_areas.py
"""
import json, os, sys

os.environ["GILMATE_OFFLINE"] = "1"          # only what is saved: this script never asks a source
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gilmate import areas, photos

EXAMPLE = {"shibuya": "I want to visit Shibuya in Tokyo", "hongdae": "I want to visit Hongdae in Seoul"}


def saved(area, name):
    path = areas.page_file(area, name)
    return path if os.path.exists(os.path.join(ROOT, "frontend", *path.split("/"))) else None


def front_photo(area):
    areas.use(area["key"])
    return photos.for_area()


out = {"default": areas.DEFAULT,
       "areas": [{"key": a["key"], "name": a["name"], "bbox": a["bbox"], "words": list(a["words"]),
                  "example": EXAMPLE[a["key"]], "map": saved(a, "map.json"), "candidates": saved(a, "candidates.json"),
                  "run": saved(a, "run.json"), "photos": areas.page_file(a, "photos"), "photo": front_photo(a)}
                 for a in areas.AREAS.values()]}
path = os.path.join(ROOT, "frontend", "data", "areas.json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(out, handle, ensure_ascii=False, indent=1)
for a in out["areas"]:
    print("%-8s map %s, candidates %s, run %s" % (a["key"], a["map"], a["candidates"], a["run"]))
print("->", path)
