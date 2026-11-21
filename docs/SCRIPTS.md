# Scripts and checks

Every script in `scripts/` and every check in `tests/` and `frontend/dev/`: what it is about, when you would run it, the exact command, what it costs and what it writes. Run every command from the repository folder.

"Free" means no key, no model call and no web search. "Paid" means it calls the model or the search, which costs money: start one only when a human said go.

Each free command below was run once for this file on 2026-11-21, on main as it was at 13:25. The paid ones were not started; their costs are the counts the earlier runs of today logged.

## Set up once

```bash
uv venv --python 3.13 && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env          # only for paid runs: put your keys in .env
```

Run the install line again after pulling: the `mcp` package was added on 2026-11-21 for Google Places.

`scripts/demo.sh --saved`, `scripts/drills.sh`, `scripts/demo_check.py`, `scripts/fetch_osm.py` and `scripts/make_map.py` also run on a bare `python3` without the virtualenv. Everything that imports the agents needs it.

## Start the demo

| Command | What it is about | Cost | Writes |
|---|---|---|---|
| `scripts/demo.sh --saved` | Serves the page on the saved run in `frontend/data/run.json`. Picks a free port, prints the address to open, stops on Ctrl-C. | Free. Needs only `python3`. | Logs in a temporary folder it names. |
| `scripts/demo.sh` | Starts the agent server (`adk api_server`) and the page, and prints one address that connects them. Stops before starting anything when `ANTHROPIC_API_KEY`, `TAVILY_API_KEY` or the virtualenv is missing, names what is missing and never prints the value of a key. | Starting is free. Using the page is paid: one visit (start, your free text, a route, one tap, one forget) was 37 or 38 model calls in today's runs, and no search while the searches are saved. With `GOOGLE_API_KEY` set, the scout's Places calls (at most 15 searches and 5 details per start turn, each saved after the first time) are billed by Google. | Logs in a temporary folder; sessions and memory in `gilmate/.adk/` and the audit log `audit.jsonl`, both git-ignored. |
| `scripts/demo.sh --saved --phone` | As above, and the page folder is served to this computer's network, so a phone on the same Wi-Fi can open the route from the QR code on the final map. Static files only. | Free. | Logs. |
| `scripts/demo.sh --phone-live` | As `--phone` on the live agents, and the agent server listens on the network too, so the phone's "Fine" / "Too far" reach the agents. Anyone on that network can then send turns to your agents. Not for a Wi-Fi you do not trust. | Paid on use. | As the live demo. |
| `scripts/demo.sh --help` | The options. `--frontend <folder>` serves another copy of the page. | Free. | Nothing. |
| `python3 scripts/demo_check.py` | Checks `demo.sh` itself under bash and zsh: `--saved` serves the page and Ctrl-C closes the port; the live mode with keys missing stops, names them, offers `--saved` and prints no value of a key. It does not start the agent server. | Free. | Nothing. |

Without the script, by hand: `python3 -m http.server 8765 -d frontend` serves the saved run at `http://localhost:8765/`. For the live agents also run `adk api_server --allow_origins http://localhost:8765 .` and open `http://localhost:8765/?api=http://localhost:8000&root=coordinator` (paid on use).

## Free checks

| Command | What it is about | Needs | Writes |
|---|---|---|---|
| `scripts/drills.sh` | Runs every `tests/drill_*.py` and fails when one fails. Run it before every commit. | `python3`; the parts that need the ADK say so and are skipped without the virtualenv. | Nothing. |
| `python3 tests/drill_<name>.py` | One drill. The eighteen are listed below. | As above. | Nothing (temporary files only). |
| `python3 tests/e2e/check.py --map-first` | Sends every map-first turn to the real agent server as the page sends them: a request for another city, the start turn, two typed answers, a route for four places, "Too far", forget. The model is the scripted stand-in `tests/e2e/stand_in_model.py` and the search results are fixtures. No browser. | The virtualenv. | A temporary folder with the server logs and the final state (`--out <folder>` names it). |
| `python3 tests/e2e/check.py --map-first --context` | The same, with the answers told in one free text (the context turn). `--no-wish` leaves the wish out. | The virtualenv. | As above. |
| `python tests/e2e/check.py` | The older questions-first page in a real browser against the real server and the stand-in. It fails on the page as it is on main, which is map first; kept until that flow is removed. `--attack` plants a search result that gives orders and uses a stand-in that breaks the rules. | The virtualenv and Playwright, see `tests/e2e/README.md`. | Screenshots and logs in a temporary folder. |

The stand-in answers the Anthropic Messages API on this machine; the two free runs for this file made 49 and 51 calls to it and none to the real model.

### The eighteen drills

| Drill | What it proves |
|---|---|
| `drill_injection.py` | Planted instructions in search results are withheld; the audit chain notices an edit. |
| `drill_policy.py` | The tool policy denies by default and enforces argument and call limits. |
| `drill_grounding.py` | Every fact needs a quote from a result that was seen. |
| `drill_audit.py` | The audit list keeps the rows a specialist wrote while the coordinator's call to it was open. |
| `drill_search.py` | The place lookup on the map, and which places the web searches name. |
| `drill_route.py` | The route draft keeps the router's advice, counts reviews, and tells a promise ("no stairs") from what the map shows. |
| `drill_candidates.py` | 8 to 10 real places from the map, every name, coordinate and access the map's, no photo without author and licence, unsupported descriptions and ratings dropped. |
| `drill_note.py` | The route note says every fact of the route once, in both languages, and nothing else. |
| `drill_say.py` | What you type reaches the session only as one of the fixed choices. |
| `drill_context.py` | Your free text reaches the session only as the fixed answers, a wish quoted word for word, and the list of what is missing. |
| `drill_progress.py` | The progress steps are the audit rows, one step per row, nothing invented. |
| `drill_memory.py` | One "Too far" gives a candidate limit, two keep it, the next route changes, forgetting restores the old result. |
| `drill_areas.py` | The typed words decide the area; every tool works on the area of its session. |
| `drill_places.py` | Google Places on hand-written fixtures: screened, sourced facts; no rating without its number of ratings and its link; the map keeps name, coordinates and access; without a key the scout's tools are as before. |
| `drill_security_today.py` | Planted instructions in a Places field, a warning text, a typed sentence and a map name are withheld, each with an audit row; a tool not in the policy table is refused; no file holds anything shaped like a key. |
| `drill_request.py` | The typed request shapes the visit: the demo's sentence becomes stairs avoided, a walking limit of 1000 m, sitting often and sushi places first among the places to eat, and nothing else of the words is kept. |
| `drill_page_areas.py` | The page reads its areas from `frontend/data/areas.json` and knows none by fixed path. It reads the data and the page's source as text, no browser. |
| `drill_weather.py` | Made-up forecasts (dry, rain likely, very hot and variants) become the fixed verdict and dangers and change a route only by rule; with the source not answering the route is the one built without weather. |

### The page in a real browser

These need Playwright, which is not a project requirement. Install it outside the repository:

```bash
uv venv /tmp/gilmate-pw && uv pip install -p /tmp/gilmate-pw playwright && /tmp/gilmate-pw/bin/playwright install chromium
```

| Command | What it is about | Writes |
|---|---|---|
| `/tmp/gilmate-pw/bin/python frontend/dev/check_page.py /tmp/gilmate-shots` | Walks the map-first page once at phone (390x844) and desktop (1440x900) size and four more sizes, on the development samples, the saved run and a stand-in for the agents. | Screenshots in the folder given. |
| `/tmp/gilmate-pw/bin/python frontend/dev/know-check.py /tmp/gilmate-shots` | The knowledge graph alone (`frontend/dev/know-lab.html`): drag, pan, zoom, the card, forgetting, an empty memory, Korean. Forgetting is simulated by that lab page. | Screenshots. |
| `/tmp/gilmate-pw/bin/python frontend/dev/walk-check.py /tmp/gilmate-shots` | Opens the QR handoff card on the laptop page and walks the phone page once. The phone page asks the street photos at their source, the only network used. | Screenshots. |

All three are free.

## Build the data (free)

| Command | What it is about | When | Writes |
|---|---|---|---|
| `python3 scripts/fetch_osm.py --area hongdae` | Fetches the OpenStreetMap extract of one area: one request to the Overpass API, no key. A saved extract is kept (it then says "kept" and exits 1); `--again` fetches anew. `--area shibuya --junctions` adds only the named crossings with a Wikidata entry, which is how the Scramble Crossing came in. | A new area, or a fresher map. | `data/<area>_osm.json` |
| `python3 scripts/make_map.py [--area hongdae]` | Turns the extract into the page's map drawing data: building outlines and streets in metres. | After the extract changed. | `frontend/data/map.json`, or `frontend/data/hongdae/map.json` |
| `python3 scripts/make_candidates.py [--area hongdae]` | Chooses the places and fetches their photos and cited texts without the model. Asks Wikimedia Commons, Wikidata and Wikipedia (no key) and Mapillary (with `MAPILLARY_TOKEN`) only for what is not saved; with everything saved it needs no network. | To build or test the page without a model, or to renew Mapillary's photo links. | `frontend/data/candidates.json` and `frontend/data/photos/CREDITS.md` (or the same below `frontend/data/hongdae/`), and what it fetched in `data/cache/` |
| `python3 scripts/make_areas.py` | Lists the areas and where the page finds each one's files. Never asks a source. | After an area or one of its files was added. | `frontend/data/areas.json` |
| `python3 frontend/dev/make_credits.py` | Lists every photo the page can show with author, date, licence and source, from the saved run and places of every area in `frontend/data/areas.json`. | After the page's data changed. | `CREDITS.md`, whole: the last two parts of that file (four photos taken near places, and the other sources) are not written by it and have to be added again. |
| `python3 frontend/dev/make_samples.py` | Writes the four development samples the page loads with `?dev=1` to `?dev=4`. Names and texts are invented and say so; the geometry comes from the map. | Layout work. | `frontend/dev/shape-sample*.json`, `frontend/dev/photos/` |
| `python tests/e2e/seed_search.py <folder>` | Writes the fixture search results under the names the search tool looks for. The end-to-end check calls it; you rarely do. | Rarely. | The folder given. |

Run for this file, `make_map.py`, `make_candidates.py` and `make_areas.py` wrote exactly the files that are committed. `make_samples.py` did not: it changed all four sample files, and the changes were discarded.

## Paid: only when a human says go

| Command | What it is about | Cost | Writes |
|---|---|---|---|
| `python scripts/save_searches.py --area hongdae` | Asks the start turn's web searches of one area and saves them, without the model. | One Tavily search per query that is not saved, eight per area. Today: none, all sixteen are saved. `--dry` only lists them and is free. | `data/cache/tavily/` |
| `python3 tests/e2e/check.py --real --map-first --context --save-run frontend/data/run.json` | The map-first turns against the real model, without a browser. This is how the saved run is recorded. `--area hongdae` asks for Hongdae (save to `frontend/data/hongdae/run.json`). | 37 or 38 model calls with `--context`, 26 or 27 without, in today's runs. No search while the start turn's searches are saved. | The file given to `--save-run`; logs. |
| `python tests/e2e/check.py --real` | The older questions-first page against the real model. | 32 or 33 model calls in today's runs. | Screenshots and logs. |
| `python scripts/run_once.py --out <file>` | One run of the older questions-first flow in the terminal, with a trace of every tool call. `--attack` plants a search result. It has no `--help`: every call starts the run. | 27 to 36 model calls in today's runs, up to 3 searches when the saved ones are missing. | Without `--out` it overwrites `frontend/data/run.json` with a run of the older shape, which the page no longer reads. Always give `--out`. |

## A second area from nothing

How Hongdae was made. Only the search and the run are paid.

```bash
python3 scripts/fetch_osm.py --area hongdae            # the map extract, one request to Overpass
python3 scripts/make_map.py --area hongdae             # the map drawing file for the page
python3 scripts/save_searches.py --area hongdae --dry  # lists the eight searches; without --dry it asks the ones not saved (paid)
python3 scripts/make_candidates.py --area hongdae      # places and photos
python3 tests/e2e/check.py --real --map-first --area hongdae --context --save-run frontend/data/hongdae/run.json   # paid
python3 scripts/make_areas.py                          # the list of areas for the page
```

The area itself is one row in `gilmate/areas.py`.

## Switches

Environment variables the scripts and checks read. None of them is a key.

| Name | What it does |
|---|---|
| `GILMATE_OFFLINE=1` | Nothing is fetched: photos, texts and searches come only from the committed caches, and what is not saved is "not found". The drills set it. |
| `GILMATE_SEARCH_CACHE`, `GILMATE_PHOTO_CACHE`, `GILMATE_WIKI_CACHE` | Another folder for the saved searches, photo answers or Wikipedia texts. The end-to-end check points the first at its fixtures. |
| `GILMATE_PLACES_CACHE` | Another folder for what Google Places answered. Default `data/cache/places/`, git-ignored. |
| `GILMATE_WEATHER=off` | The weather and air quality of the day are not read; routes are built as without them. |
| `GILMATE_CLIMB=on` | Adds the metres up and down of each walk from Open-Meteo's heights. Off by default: the heights include buildings. |
| `GILMATE_WEATHER_CACHE`, `GILMATE_ELEVATION_CACHE` | Another folder (for the heights: another file) for what Open-Meteo answered. Defaults are below `data/cache/`, git-ignored. |
| `AUDIT_LOG` | Where the chained audit file is written. Default `audit.jsonl` in the repository folder, git-ignored. |
| `GILMATE_PYTHON` | The Python that `tests/e2e/check.py` starts the server with. Default `.venv/bin/python`; `--python` does the same. |
