"""Fetch the OpenStreetMap extract of one area and save it under data/. FREE: one request to the Overpass API,
no key, no model, no search.

The extract holds what gilmate/osm.py and scripts/make_map.py read: streets, paths and steps with their geometry,
building outlines, and every node or way tagged amenity (places to eat, benches), shop or tourism, with the
wheelchair tags they carry. Map data (c) OpenStreetMap contributors, ODbL.

A named crossing that has its own Wikidata entry is a sight too (the Shibuya Scramble Crossing is mapped as a
junction, not as an attraction). `--junctions` fetches only those and adds the ones a saved extract does not have
yet, leaving every other byte of the file as it was.

Usage: python3 scripts/fetch_osm.py --area hongdae        (a saved extract is kept; --again fetches it anew)
       python3 scripts/fetch_osm.py --area shibuya --junctions
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gilmate import areas  # noqa: E402

OVERPASS = "https://overpass-api.de/api/interpreter"
AGENT = "gilmate-hackathon/0.1 (map extract; python-urllib)"       # a generic client name, no personal details
QUERY = """[out:json][timeout:90][bbox:{south},{west},{north},{east}];
(
  way[highway];
  way[building];
  node[amenity]; way[amenity];
  node[shop]; way[shop];
  node[tourism]; way[tourism];
  node[railway~"^(station|subway_entrance)$"];
  node[junction][name][wikidata];
);
out tags geom;
relation[building];
out tags bb;
"""
JUNCTIONS = """[out:json][timeout:60][bbox:{south},{west},{north},{east}];
node[junction][name][wikidata];
out tags geom;
"""


def ask(query):
    request = urllib.request.Request(OVERPASS, urllib.parse.urlencode({"data": query}).encode(), {"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=120) as answer:
        return json.loads(answer.read())


parser = argparse.ArgumentParser()
parser.add_argument("--area", required=True, choices=sorted(areas.AREAS))
parser.add_argument("--again", action="store_true", help="fetch even when the extract is already saved")
parser.add_argument("--junctions", action="store_true",
                    help="add the named crossings with a Wikidata entry to the saved extract; nothing else changes")
args = parser.parse_args()
area = areas.AREAS[args.area]
path = os.path.normpath(area["extract"])
south, west, north, east = area["bbox"]
if args.junctions:
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    before = json.loads(raw)["elements"]
    have = {(e["type"], e["id"]) for e in before}
    new = [e for e in ask(JUNCTIONS.format(south=south, west=west, north=north, east=east)).get("elements", [])
           if (e["type"], e["id"]) not in have]
    if not new:
        sys.exit("nothing to add: %s holds every named crossing with a Wikidata entry in the area" % path)
    body = raw.rstrip()
    inner = body[:-1].rstrip()                    # the file ends with the elements list: ... ] }
    if not body.endswith("}") or not inner.endswith("]"):
        sys.exit("not changed: %s does not end with its elements list" % path)
    text = inner[:-1].rstrip() + ",\n" + ",\n".join(json.dumps(e, ensure_ascii=False, indent=2) for e in new) + "\n]}\n"
    if json.loads(text)["elements"] != before + new:
        sys.exit("not changed: the file would not read back as before plus the new elements")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    for e in new:
        print("added %s/%s %s" % (e["type"], e["id"], e["tags"].get("name:en") or e["tags"].get("name")))
    sys.exit(0)
if os.path.exists(path) and not args.again:
    sys.exit("kept: %s is already saved (use --again to fetch it anew)" % path)

data = ask(QUERY.format(south=south, west=west, north=north, east=east))
if not data.get("elements"):
    sys.exit("not saved: the answer holds no elements (%s)" % str(data.get("remark", ""))[:200])
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))

tags = [e.get("tags", {}) for e in data["elements"]]
print("%d elements -> %s, %d KB" % (len(tags), path, os.path.getsize(path) // 1024))
print("ways with highway %d (steps %d), buildings %d, benches %d, amenity %d, shop %d, tourism %d, wheelchair tags %d" % (
    sum(1 for t in tags if "highway" in t), sum(1 for t in tags if t.get("highway") == "steps"),
    sum(1 for t in tags if "building" in t), sum(1 for t in tags if t.get("amenity") == "bench"),
    sum(1 for t in tags if "amenity" in t), sum(1 for t in tags if "shop" in t),
    sum(1 for t in tags if "tourism" in t), sum(1 for t in tags if "wheelchair" in t)))
