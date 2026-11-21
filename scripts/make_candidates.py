"""Builds the places on the map without the model and saves them for the page. FREE: no model, no search.

It asks Wikimedia Commons, Wikidata and Wikipedia (no key) for what is not yet saved in data/cache/photos and
data/cache/wiki; with everything saved it needs no network. Writes frontend/data/candidates.json
({area, candidates, street_photos, rest_spots, counts}, CONTRACT.md 7.2) and frontend/data/photos/CREDITS.md.
For another area the same files are in its own folders: data/cache/hongdae/photos, frontend/data/hongdae/.
Usage: python3 scripts/make_candidates.py [--area hongdae]
"""
import argparse, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:                                    # MAPILLARY_TOKEN, when there is one, lives in .env; it is optional
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass
from gilmate import areas, candidates, photos

parser = argparse.ArgumentParser()
parser.add_argument("--area", default=areas.DEFAULT, choices=sorted(areas.AREAS))
AREA = areas.use(parser.parse_args().area)
built = candidates.build()
seen = dict(candidates.saved_results(), **built.pop("sources"))
built.pop("own")
for c in built["candidates"]:
    problems = candidates.check(c, seen)
    if problems:
        sys.exit("not saved, %s fails its own checks: %s" % (c["name"], problems))
out = os.path.join(ROOT, "frontend", *areas.page_file(AREA, "candidates.json").split("/"))
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as handle:
    json.dump(built, handle, ensure_ascii=False, indent=1)

lines = ["# Photo credits", "",
         "Small copies of photos from Wikimedia Commons, shown on the place cards. Each keeps its author and licence;",
         "the full picture and its page are at the source. Written by `scripts/make_candidates.py`.", "",
         "| File | Place | Author | Licence | Source |", "|---|---|---|---|---|"]
for path in sorted(glob.glob(os.path.join(photos.PHOTO_CACHE, "*.json"))):
    saved = json.load(open(path, encoding="utf-8"))
    for p in saved.get("photos", []):
        if "name" in saved and str(p.get("thumb_url", "")).startswith(photos.THUMBS_URL):
            lines.append("| %s | %s | %s | %s | %s |" % (os.path.basename(p["thumb_url"]), saved["name"],
                                                       p["credit"].replace("|", "/"), p["licence"], p["source_url"]))
if os.path.isdir(photos.THUMBS):
    with open(os.path.join(photos.THUMBS, "CREDITS.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

for c in built["candidates"]:
    print("%-4s %-5s %-34s %-26s photos %d  %s" % (c["id"], c["category"], c["name"][:34], c["kind"]["en"],
          len(c["photos"]), (c["description"] or {}).get("en", "no description")[:60]))
print(built["counts"], "->", out)
