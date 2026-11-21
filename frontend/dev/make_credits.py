"""Write CREDITS.md at the root of the repository: every photo the page can show, with its author, date,
licence and source link, read from the page's own data: for every area in frontend/data/areas.json its picture on the
first screen, its saved run and its places (for Shibuya frontend/data/run.json and frontend/data/candidates.json).

Free: no network, no key, no model. Run from the repo folder after the data changed: python3 frontend/dev/make_credits.py

Nothing is filled in: a photo without an author, a date or a licence in the data is listed as unknown.
The page shows no credit lines, so this file is where the photos' authors are named.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.dirname(HERE)
ROOT = os.path.dirname(FRONTEND)


def load(name):
    path = os.path.join(FRONTEND, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def row(photo):
    cell = lambda value, missing: str(value).replace("|", "/").replace("\n", " ") if value else missing
    link = photo.get("source_url")
    return "| %s | %s | %s | %s |" % (cell(photo.get("credit"), "author unknown"), cell(str(photo.get("taken_at") or "")[:10], "date unknown"),
                                      cell(photo.get("licence"), "licence unknown"), f"<{link}>" if link else "source unknown")


def main():
    seen, sections = set(), []

    def section(title, photos):
        fresh = []
        for photo in photos:
            key = photo.get("source_url") or photo.get("url") or photo.get("id")
            if key and key not in seen:
                seen.add(key)
                fresh.append(photo)
        if fresh:
            sections.append((title, fresh))

    # Without the list of areas the page knows one: Shibuya, in the two files it always read.
    areas = load("data/areas.json").get("areas") or [{"name": "Shibuya, Tokyo", "run": "data/run.json", "candidates": "data/candidates.json"}]
    files = []
    for entry in areas:
        name = str(entry.get("name") or "An area").split(",")[0].strip()
        if entry.get("photo"):
            section(f"{name}, on the first screen", [entry["photo"]])
        files += [(name, path) for path in (entry.get("run"), entry.get("candidates")) if path]
    first = files[0][0] if files else None
    for name, path in files:
        data = load(path)
        where = "" if name == first else f" in {name}"
        area = data.get("area") or {}
        if area.get("photo"):
            section(f"{name}, on the first screen", [area["photo"]])
        for place in data.get("candidates") or []:
            section(place.get("name") or "A place", place.get("photos") or [])
        model = data.get("spatial_model") or {}
        near = [photo for kind in ("stops", "legs", "benches") for item in model.get(kind) or [] for photo in item.get("photos") or []]
        section(f"Photos taken near the stops, walks and benches of the saved route{where}", near)
        section(f"Photos taken near the benches on the map{where}", [photo for spot in data.get("rest_spots") or [] for photo in spot.get("photos") or []])
        section(f"Photos taken on the streets{where} (the grey dots on the map)", data.get("street_photos") or [])

    total = sum(len(photos) for _, photos in sections)
    lines = ["# Credits", "",
             "Written by `frontend/dev/make_credits.py` from %s. Do not edit by hand." % ", ".join(f"`frontend/{path}`" for _, path in files),
             "",
             f"The page shows {total} photos from these files. Each is listed here with its author, date, licence and source, as the data states them.",
             "Street-level photos are by Mapillary contributors, CC BY-SA 4.0 (mapillary.com). The other photos are from Wikimedia Commons under the licence named in each row.",
             "Map data is © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright). The font is Aspekta, SIL Open Font Licence.", ""]
    for title, photos in sections:
        lines += [f"## {title} ({len(photos)})", "", "| Author | Date | Licence | Source |", "|---|---|---|---|"] + [row(photo) for photo in photos] + [""]
    with open(os.path.join(ROOT, "CREDITS.md"), "w", encoding="utf-8") as out:
        out.write("\n".join(lines))
    print(f"CREDITS.md: {total} photos in {len(sections)} sections")


if __name__ == "__main__":
    main()
