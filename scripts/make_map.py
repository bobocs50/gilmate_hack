"""Write the map drawing data of one area: building outlines and streets from its saved extract, in metres.
Shibuya: frontend/data/map.json. Hongdae: frontend/data/hongdae/map.json (the table is gilmate/areas.py).
Run from the repo folder: python3 scripts/make_map.py [--area hongdae]"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gilmate import areas, osm

parser = argparse.ArgumentParser()
parser.add_argument("--area", default=areas.DEFAULT, choices=sorted(areas.AREAS))
AREA = areas.use(parser.parse_args().area)
LANDMARK = re.compile(AREA["landmarks"], re.I)
WIDTH = {"primary": 15, "trunk": 15, "secondary": 12, "tertiary": 10, "unclassified": 9, "residential": 9,
         "pedestrian": 8, "living_street": 8, "service": 5, "trunk_link": 9}
CAP_M = 34.0

def height(t):
    try:
        return float(str(t.get("height", "")).replace("m", "").strip())
    except ValueError:
        lv = t.get("building:levels", "")
        return float(lv) * 3.2 if lv.replace(".", "", 1).isdigit() else 10.0

buildings, ways = [], []
for e in json.load(open(osm.EXTRACT, encoding="utf-8"))["elements"]:
    t = e.get("tags", {})
    if "building" in t:
        rings = [e["geometry"]] if e["type"] == "way" else [m["geometry"] for m in e.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        name = t.get("name", "") + " " + t.get("name:en", "")
        lm = bool(LANDMARK.search(name)) or "tourism" in t or t.get("shop") in ("mall", "department_store")
        for r in rings:
            if len(r) >= 4:
                buildings.append({"pts": [[round(v, 1) for v in osm._metres(p["lat"], p["lon"])] for p in r[:-1]],
                                  "h_m": min(max(height(t), 6.0), CAP_M), "landmark": lm})
    elif e["type"] == "way" and "highway" in t and osm._on_the_surface(t):
        k = t["highway"]
        kind = "steps" if k == "steps" else "street" if k in WIDTH else "path"
        ways.append({"kind": kind, "width": WIDTH.get(k, 3),
                     "pts": [[round(v, 1) for v in osm._metres(p["lat"], p["lon"])] for p in e["geometry"]]})
out = {"origin": {"lat": osm.LAT0, "lon": osm.LON0, "m_per_deg_lat": osm.M_LAT, "m_per_deg_lon": osm.M_LON},
       "bearing_deg": AREA["bearing_deg"], "source": "OpenStreetMap contributors, ODbL", "buildings": buildings, "ways": ways}
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend",
                    *areas.page_file(AREA, "map.json").split("/"))
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(out, open(path, "w"), separators=(",", ":"))
print(len(buildings), "buildings,", len(ways), "ways ->", path, os.path.getsize(path) // 1024, "KB")
