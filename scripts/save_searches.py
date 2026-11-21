"""Run the start turn's web searches of one area and save them, without the model.

PAID: one Tavily search for every query that is not saved yet in data/cache/tavily (eight per area; none when all
are saved). A saved search is never asked again. Needs TAVILY_API_KEY in .env.
Usage: python scripts/save_searches.py --area hongdae [--dry]      (--dry only lists what would be asked)
"""
import argparse, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from gilmate import areas, tools

parser = argparse.ArgumentParser()
parser.add_argument("--area", required=True, choices=sorted(areas.AREAS))
parser.add_argument("--dry", action="store_true")
args = parser.parse_args()
areas.use(args.area)
fresh = 0
for category in ("see", "shop", "eat"):
    for query in tools.start_queries(category):
        path = os.path.join(tools.CACHE, tools.cache_name(query))
        if os.path.exists(path) or args.dry:
            print("%-5s %-9s %s" % (category, "saved" if os.path.exists(path) else "to ask", query))
            continue
        saved, _ = tools._tavily(query)
        fresh += 1
        print("%-5s %-9s %d results  %s" % (category, "asked", len(saved["results"]), query))
print("fresh searches: %d" % fresh)
