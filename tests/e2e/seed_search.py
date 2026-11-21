"""Write the fixture search results into a folder, in the saved-search format and under the names the search tool
looks for, so the free end-to-end check never needs the search key. Run with the project's Python (it imports the
tools to use their exact queries): python tests/e2e/seed_search.py <folder>"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from gilmate import memory, tools  # noqa: E402

folder = sys.argv[1]
os.makedirs(folder, exist_ok=True)
world = json.load(open(os.path.join(HERE, "fixtures", "world.json"), encoding="utf-8"))
for category in tools.QUERIES:
    asked = {q for food in list(memory.FOOD_SEARCH) + ["surprise", None] for q in tools.queries(category, food)}
    for query in sorted(asked | set(tools.start_queries(category))):      # the old page's searches and the start turn's
        if True:
            name = hashlib.sha256(query.encode()).hexdigest()[:16] + ".json"
            json.dump({"query": query, "fetched_at": "2026-01-01T00:00:00", "results": world["search"][category]},
                      open(os.path.join(folder, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("seeded", len(os.listdir(folder)), "fixture searches in", folder)
