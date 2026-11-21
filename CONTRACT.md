# Gilmate: contract between the three workers

Started 2026-11-21 09:30, on the day of the hackathon. Three workers, each owning its own files. This file is the only thing they share. If something here is wrong or missing, say so in your report; do not silently diverge.

| Worker | Owns | Never touches |
|---|---|---|
| A, backend | `gilmate/` except `guards.py`; `data/`; `scripts/`; `frontend/data/` | `frontend/` other than `frontend/data/` |
| B, page | `frontend/` except `frontend/data/` | everything else |
| C, guards | `gilmate/guards.py`, `tests/drill_*.py`, `tests/fixtures/` | everything else |

Rules for all: plain, readable code; no placeholder data shown as real; missing data is "unknown", never safe; nothing books, pays or sends.

## 1. Session state (written by backend tools, read by the page)

```
# Since section 7 (map first) the state also holds area, candidates, street_photos, rest_spots, counts, said,
# progress and route_note; picks are two to five candidate ids; the profile has no food. Shapes: section 7.2.
# Since section 9 (dangers of the day) also weather and dangers, and spatial_model.weather. Shapes: section 9.1.
profile:   { walk: "short"|"medium"|"long", stairs: "avoid"|"few"|"ok",
             rest: "often"|"sometimes"|"rarely", wish: string|null, language: "ko"|"en" }
             # the older questions-first page also sends food: "sushi"|"ramen"|"surprise"; only its searches read it
options:   [ { id, category: "see"|"shop"|"eat", name, summary: {en, ko},
               facts: [ {label, value, source_url, quote} ],
               place: {lat, lon, osm_id, access: "yes"|"limited"|"no"|"unknown"} } ]     # two per category
picks:     [ option id ]                                                                   # one per category
spatial_model: {
  area:    { name, bbox: [south, west, north, east] },
  stops:   [ { id, option_id, order, category, name, lat, lon, access, background: {en, ko}, sources: [url] } ],
  legs:    [ { id, from, to, distance_m, line: [[lon, lat]], kind: "routed"|"straight_line",
               stairs: "none_mapped"|"some"|"unknown", fits_profile: bool, note: {en, ko} } ],
  hazards: [ { id, leg_id|null, stop_id|null, kind: "steps"|"long_walk"|"unknown_access", lat, lon, detail: {en, ko}, source } ],
  benches: [ { id, leg_id, lat, lon, off_route_m, source } ],
  review:  { status: "verified"|"partly_unverified", rounds, removed: [ {what, why} ] },
  generated_at }
audit:     [ { t: "HH:MM:SS", agent, tool, decision: "allowed"|"blocked"|"withheld", rule, detail } ]
```

Notes on what the backend really writes:
- An option's and a stop's `name` is the map's name for the place (for example "Ten" for the restaurant the web calls "Sushi Tokyo Ten"), never the model's.
- `review.rounds` is the number of reviews by the critic, not the number of drafts. `review.removed` is not a list of things taken out: when a route is published as `partly_unverified` it lists the points the checker did not confirm (failed rule checks and the critic's open problems, `why: "not confirmed within two rounds"`). Nothing is removed from the route. A route is published after an approval, or after the second review at the latest.
- A leg's `note` is the router's advice when it passes the rule checks, otherwise a sentence written by Python. A note that promises "no stairs" or "step-free" is refused; "no stairs mapped" and "the map shows no stairs" are accepted.
- `hazards[].kind: "unknown_access"` has two meanings: with a `stop_id` the entrance has no accessibility tag; with a `leg_id` there is no mapped path (the leg is a `straight_line`), placed at the leg's first stop.
- `benches[].off_route_m` is measured to the points of the leg's line. On a `straight_line` leg that is the distance to the nearer stop, and one bench can be listed under two legs.
- `audit`: `t` is a bare clock time. Every step of every agent is in the list, the specialists' too. Her own decisions are rows with `agent: "traveller"` (tools `record_picks`, `record_feedback`, `forget_fact`) and `rule: "human_decision"`. An allowed row otherwise has `rule: ""`, except the publishing review (`published:verified` or `published:partly_unverified`). A blocked row names the rule (`search_options.max_calls:3`, `quote_not_found`, `sent_back_to_router`, ...). The same rows go into the hash-chained file `audit.jsonl` (path from `AUDIT_LOG`).
- The session state also holds keys the page does not read: `seen`, `draft`, `rule_failures`, `review_problems`, `rounds`, `search_fetched_at`, `attack`, and `user:memory` (section 6).

`stairs: "none_mapped"` means the map data shows no stairs on that path. It is not a promise that there are none; the page says "no stairs mapped".

## 2. What the page loads

- Live: `GET {api}/apps/gilmate/users/{u}/sessions/{s}` after each agent turn; the state is in the response's `state` key.
- Without a backend: `frontend/data/run.json`, one saved real run of the map-first flow (section 7): `{ recorded_at, area, candidates, street_photos, rest_spots, counts, said, profile, picks, spatial_model, route_note, audit, progress, "user:memory" }`, exactly these keys, and `profile_missing` (section 7.2) since the run of 12:21, which told the answers in a context turn (`recorded_at` is `YYYY-MM-DDTHH:MM:SS`). It holds what one real start turn returned (the scout's real searches, the 12 candidates with their photos, descriptions and facts), her typed answer, the route for four Yes places with the photos taken near every stop, walk and bench, the route note, every audit row with its progress step, and her memory as it was after one "too far" tap and before the forget turn (section 6.1). It has no `options`: the run of the older questions-first flow is no longer saved. The page was to say "Recorded run, HH:MM" as one quiet line inside its menu (the three-line button); the page on main has no menu any more and does not show that line (checked 2026-11-21, 13:00: the words are still in `frontend/js/words.js`, no code draws them). It is written by `tests/e2e/check.py --real --map-first --context --save-run <file>`. The run saved at 12:21 offers the Shibuya Scramble Crossing (`c2`) and has it as a stop; its `review.status` is `partly_unverified` with two open points in `review.removed`.
- For building and testing the page without a backend and without a model: `frontend/data/candidates.json` (section 7.2), written by `python3 scripts/make_candidates.py`, and the small photo copies in `frontend/data/photos/`.
- Map drawing data: `frontend/data/map.json`, written by worker A from OpenStreetMap:
  `{ origin: {lat, lon, m_per_deg_lat, m_per_deg_lon}, bearing_deg, source, buildings: [ {pts: [[east_m, north_m]], h_m, landmark: bool} ], ways: [ {kind: "street"|"path"|"steps", width, pts: [[east_m, north_m]]} ] }`
  A point `[lon, lat]` from the spatial model becomes metres with `east = (lon - origin.lon) * m_per_deg_lon`, `north = (lat - origin.lat) * m_per_deg_lat`.
- A second area (section 8): Shibuya's files stay where they are, `frontend/data/{map,candidates,run}.json` and `frontend/data/photos/`. Hongdae's are the same four in its own folder, `frontend/data/hongdae/{map,candidates,run}.json` and `frontend/data/hongdae/photos/`, in the same shapes; each area's `map.json` has its own `origin`. `frontend/data/areas.json` lists both: `{ default: "shibuya", areas: [ {key, name, bbox, words, example, map, candidates, run, photos, photo} ] }`, the file paths below the page folder, `null` for a file that is not saved; `photo` is the area's front page photo (a `place_photo`, section 7.2) and `words` the lower-case words by which a typed request names the area. Live, `state.area.map` names the map drawing file of the session's area.

## 3. Agent turns the page sends (message text is JSON)

- `{"step": "start", "text": "..."}`, `{"step": "candidates"}`, `{"step": "say", ...}` and `{"step": "context", "text": "..."}`: section 7.3.
- `{"step": "route", "picks": ["c5", "c1", "c9"], "profile": {...}}`: section 7.3; state then has `spatial_model` and `route_note`.
- The older page: `{"step": "options"}` after the questions (state then has `options`) and `{"step": "route", "picks": ["o1", "o3", "o5"]}` with one option per category and the profile in the session's initial state. Both still work; they go when that page is gone.
- `{"step": "ask", "stop_id": "s1", "question": "..."}`; the answer is the final text of the turn, in the language of her question: Korean for a question written in Korean, English otherwise.
- `{"step": "feedback", ...}` and `{"step": "forget", ...}`: section 6.2. Any other message: the coordinator says it can only do these things.
- The agents: `coordinator` (root), `scout` (the start turn), `router`, `critic`, `companion`, and `option_scout` for the older page's options.
- The root agent is named `coordinator` (`?root=coordinator` on the page). The server must allow the page's origin: `adk api_server --allow_origins http://localhost:8765 .`
- With the real model a start turn ran about 60 seconds and a route turn for four places about 40; a typed answer, a tap or a forget takes a few seconds.

## 4. `gilmate/guards.py` (worker C; pure Python, no ADK import, no network)

```
INJECTION: compiled regex
screen_results(results: list[dict]) -> dict
    # each result: {title, url, content}. Returns {"passed": [...], "withheld": [ {url, rule, sample} ]}
    # passed results keep their keys; the text is data, never instructions
POLICY: dict            # tool name -> {"max_calls": int, "args": {...}} ; a tool not listed is denied
check_policy(tool: str, args: dict, calls_so_far: int, state: dict) -> str | None
    # returns the violated rule name or None. Tools: search_options, find_place, save_options, walking_route,
    # rest_spots, propose_route, read_draft, submit_review, route_facts, record_feedback, forget_fact,
    # scout, option_scout, router, critic, companion, and for the map-first turns read_request, search_places,
    # find_candidates, describe_candidates, record_said, record_context. gilmate/security.py adds record_picks and
    # raises two limits (save_options 4, find_place 20).
    # read_request, find_candidates, record_said, record_context: 1 call. search_places: category see|shop|eat, 3 calls.
    # walking_route and rest_spots: 12 calls (five picks have ten pairs).
    # search_options: category must be see|shop|eat, max 3 calls. propose_route: every stop must be in state["picks"].
    # record_feedback: verdict must be fine|too_far, max 1 call.
    # weather_today (section 9): no arguments, 1 call; added by gilmate/security.py like record_picks.
ground_option(option: dict, seen: dict[str, str]) -> list[str]
    # seen maps each passed result url to its text. Problems: source url not seen; quote not found in that text
    # (case and whitespace folded); digits of a fact value not in its quote.
ground_description(candidate: dict, seen) -> list[str]         # source read, quote in it, every number in the quote
unsupported_sentences(text: str, source: str) -> list[str]      # the sentences a source page does not support
ground_written_description(description, source_text) -> ({en, ko}|None, dropped)   # a model's text, cut to what is supported
ground_rating(candidate: dict, seen, names) -> list[str]        # a rating needs a read page that names the place and states it
access_label(tags: dict) -> "yes"|"limited"|"no"|"unknown"      # missing wheelchair tag -> "unknown"
audit(event: dict, path: str) -> dict                           # appends one JSON line with "prev" = sha256 of the line before
verify_chain(path: str) -> bool
screen_fields(value) -> (clean, withheld)                       # every string inside a tool answer screened on its own;
    # a string that reads like an instruction becomes WITHHELD_TEXT, a key-shaped part KEY_REMOVED.
    # withheld: [ {field: "candidates[2].name", rule, sample} ]. Numbers and the shape stay.
find_keys(text) -> [(position, kind)]; redact(text) -> str      # the shapes of the four keys; audit() redacts every row
safe_file_name(name: str) -> bool                               # one plain file name: no folder, no "..", no odd character
```

What the plugin does with them (`gilmate/security.py`, added 12:50; SECURITY.md has the inventory): after every tool call except the specialists and the two Places tools (which their own hook screens record by record), the answer goes through `screen_fields` before the model reads it. Each replaced string is a `withheld` audit row whose `detail` is `<field> | <sample>`, agent and tool as in the call. A call with a key-shaped argument is refused with the rule `secret:key_shape`. A page message whose `text` or `question` reads like an instruction is a row in the chained file only (agent `traveller`, tool `typed_text`, decision `flagged`, `detail` `step=...; field=...`); the message itself is passed on unchanged. Free check: `tests/drill_security_today.py`.

How the limits are counted (`gilmate/security.py`): the calls to the four specialists and her three decisions count per turn. The calls of a specialist's own tools count per call to that specialist, because it starts each call with nothing in mind: a scout asked a second time may read the saved searches again. A refused call returns `{status: "denied", rule, message}` to the agent and is a `blocked` row in the audit.

Rule checks on a drafted route (`osm.check_model`, no sentence can talk its way past them): the stops are the picks, coordinates and access unchanged and inside the area, every leg reproducible from the map, no note or background that promises "no stairs" or full access, and the meal is not the first stop when the same stops in reverse order are as short.

### 4.1 Google Places over MCP (optional; added 2026-11-21, 12:45; `gilmate/places.py`, `gilmate/places_server.py`)

A second source for the scout: rating with its number of ratings, opening hours and the entrance flag from Google Maps, as facts with their source. The map stays the truth for name, coordinates, access and routing; a place from Places is never offered by itself.

- **The MCP server is our own**, standard MCP over stdio: `python3 -m gilmate.places_server` (package `mcp`, pinned in `requirements.txt`). It wraps the Places API (New) Text Search and Place Details over HTTPS with the key from `GOOGLE_API_KEY`. It only reads. Google's own MCP server (`mapstools.googleapis.com/mcp`) was not used: its `search_places` returns a text summary without rating, hours or entrance flag as fields, has no bounding box, and its terms forbid keeping the content.
- **The scout gets it through ADK's `McpToolset`** (`StdioConnectionParams`), attached by `places.wire(scout)` in `gilmate/agent.py` only when `GOOGLE_API_KEY` is set at start. Without the key (or with a key that cannot be one, without the `mcp` package, or with a server that does not start) the scout's tools and instruction are exactly as before.
- **Tools** (both in `guards.POLICY`; any other MCP tool is denied by default):
  ```
  places_search(category: "see"|"shop"|"eat", area: str, name: str = "")     # 15 calls: three kinds, then one per place
      # Text Search inside the area's bounding box. The query is built by Python: the kind of place, or one place by its name.
  place_details(place_id: str)                                                 # 5 calls; only an id a search returned
  -> {status: "ok", source: "saved"|"fresh", fetched_at, places: [record], withheld: [ {url, rule, sample} ]}
   | {status: "unavailable", reason: "no_key"|"offline"|"timeout"|"network"|"http_403:PERMISSION_DENIED"|...}
   | {status: "refused", reason}
  record: { place_id, name, type, rating|null, ratings|null, address, lat, lon, hours: [str], wheelchair_entrance: "yes"|"no"|"unknown", source_url }
  ```
  `source_url` is the place's Google Maps link. A rating without its number of ratings is dropped; a missing entrance flag is "unknown"; a place that has closed is no record.
- **Results are data, never instructions.** Every record is screened like a web result (`guards.screen_text`) in the server and again in the agent's process (`places.after_tool`, the scout's after-tool hook), where a record outside the area's bounding box or without a Google Maps link is withheld too. The model is given names and numbers only.
- **State it adds** (written by Python, never by the model): `places_results: {source_url: record}`, `places_matched: {candidate id: source_url}`, `places_unavailable: [turn, reason]`. A record is about a candidate only when the names agree and its point is at most 80 m from the map's. Then `candidates[].facts` gains up to three facts with `source_url` = the Google Maps link and a `quote` from the text Python wrote out of the record (kept in `seen` under that link): `Google Maps rating` ("4.6 out of 5 (28,255 ratings on Google Maps)"), `Opening hours (Google Maps)` (the week as Google gives it, or "Every day: ..." when the seven days are the same), `Entrance for wheelchairs (Google Maps)` ("listed as accessible" / "listed as not accessible"). `candidates[].rating` is set (same value, link, quote) when it was null and Google's name contains the map's. `place` is never changed.
- **Order**: when Places gave ratings, the candidates are reordered inside each kind (ids do not change, so the list is then no longer in id order): `q = (n*r + 200*C) / (n + 200)` with `C` the mean rating of everything fetched; a place without a rating counts `C - 0.3`; an accessible entrance (Google yes, or map access yes/limited; a "no" from either wins) adds 0.10. The terms for web mentions and for rain are not built.
- **Audit rows** (agent `scout`): the policy plugin's `allowed` or `blocked` row per call; `places_search` rule `screened`, detail `category=see; passed=12; withheld=0; source=google_places_fresh` (or `_saved`, and `; name=...` for a lookup by name); a `withheld` row per record screened out; `places_facts`, detail `source=google_places; places=5; reordered=yes`; and when Places cannot be used one row per turn, `places_search`, `blocked`, rule `source_not_available`, detail `source=google_places; reason=no_key` (or the server's reason). After a call that answered "unavailable" the tools are taken away until the server process restarts.
- **Cache**: one file per query in `data/cache/places`, not committed (Google's terms allow keeping only the place id), so a query costs a call only the first time on a machine. `GILMATE_PLACES_CACHE` points at another folder; with `GILMATE_OFFLINE` nothing is fetched. The drill's responses are hand-written fixtures in `tests/fixtures/places`, labelled as fixtures.
- **Free check**: `python3 tests/drill_places.py`.
- **In the Google Cloud console**: enable "Places API (New)" (`places.googleapis.com`) for the key's project, and the project needs a billing account. The fields asked for are billed as Text Search Enterprise.

## 5. Run

- Python env: see README. Keys come from `.env` in the repo folder (git-ignored); never print, read or commit them.
- Free checks: `python3 tests/drill_<name>.py` exit non-zero on failure, no network, no key, no model. Sixteen drills: `injection`, `policy`, `grounding`, `memory`, `audit`, `search`, `route`, `candidates`, `note`, `say`, `progress`, `areas`, `context`, `weather`, `places`, `security_today`. They set or respect `GILMATE_OFFLINE=1`: photos, Wikipedia texts and searches come only from the committed caches, and what is not saved is "not found". Parts that need the ADK say so and are skipped when it is not installed.
- All drills with one command: `scripts/drills.sh` (exits non-zero when one fails).
- Free end-to-end check: `tests/e2e/check.py` (see `tests/e2e/README.md`). The real server and the page in a real browser, with a scripted stand-in for the model and fixture search results. It needs Playwright, installed outside the repository, so it is not a drill. `tests/e2e/check.py --map-first` sends the map-first turns of section 7 to the real server as the page sends them (start, two typed answers, a route for four places, "too far", forget) and needs no browser and no Playwright.
- Paid model runs only when the user says go: `tests/e2e/check.py --real --map-first` (26 and 27 model calls in the first two runs of 2026-11-21; 37 and 38 with `--context`, for Shibuya and with `--area hongdae`; no search once the start turn's searches are saved); for the older page `python scripts/run_once.py` (27 to 36) or `tests/e2e/check.py --real` (32 or 33).
- Web search: each category is searched with one or two fixed queries built by Python (`tools.queries`); the second names places that are on the map (`osm.SEARCH_HINTS`), because only those can be offered. Results are saved per query in `data/cache/tavily`, which is committed and never cleared, so a query costs a search only the first time. The start turn asks eight queries (`candidates.start_queries`: the usual ones without a food answer, and one per category that asks for ratings; the exact words per area are in `gilmate/areas.py`); all eight are saved for Shibuya and for Hongdae, so a start turn costs no search. Also saved: the queries of the older page for the food answer "sushi" (18 files in all). `python scripts/save_searches.py --area <key>` asks the ones of an area that are not saved, without the model. Its answers "ramen" and "surprise" cost up to two searches each the first time. `GILMATE_SEARCH_CACHE` points the tool at another folder (used by the end-to-end check for its fixtures).
- Photos and cited texts (`gilmate/photos.py`, no model): Wikimedia Commons, Wikidata and Wikipedia need no key; Mapillary needs `MAPILLARY_TOKEN` in `.env` and is asked only when its saved file is missing. Everything is saved in `data/cache/photos` and `data/cache/wiki` (committed) and the small copies of the place photos in `frontend/data/photos`. `python3 scripts/make_candidates.py` fills what is missing and rewrites `frontend/data/candidates.json`; with everything saved it needs no network. KartaView's public API was asked too and gave no usable photo for this area today.

## 6. Memory: one person's guide (added 2026-11-21, 10:30)

Gilmate asks her once, remembers, and learns from how the day went. She can see and delete everything it holds.

### 6.1 State (backend writes, page reads)
Kept per traveller across sessions, in ADK per-user state (keys prefixed `user:`). Written only by Python from her own answers and taps; never from web text or model text.

```
user:memory: {
  facts: [ { id, key: "walk"|"stairs"|"rest"|"wish"|"walk_limit_m"|"see"|"shop"|"eat"|"see2"|..., value,
             group: "answers"|"day"|"picks",
             source: "answer"|"feedback"|"pick",
             evidence: {en, ko},     # e.g. "You said: too far, after the 554 m walk from Loft."
             at: "HH:MM",
             effect: {en, ko},       # e.g. "Walks longer than 544 m are flagged for the rest of that day. ..."
             status: "candidate"|"kept",
             changed_legs: [leg id] } ],                                  # walks this fact changed, for the blue lines
  feedback: [ { leg_id, distance_m, verdict: "fine"|"too_far", at: "YYYY-MM-DDTHH:MM:SS" } ] }
```

Rules:
- Her four answers (`walk`, `stairs`, `rest`, `wish`) become facts with `source: "answer"`, `status: "kept"`, ids `f1` to `f4`; a `food` answer is no longer kept (a `food` fact stored earlier stays until she forgets it, and is not read). Her picks, two to five, become facts in group `picks` with the map's name of the place as `value`: the first pick of a category has the category as `key` (`see`, `shop`, `eat`), a further one of the same category `see2`, `see3` and so on. One fact per key: a changed answer or pick keeps its id, and a pick she no longer has is dropped at the next route turn.
- `evidence` and `effect` are `{en, ko}` like every other text in the state, built by Python from fixed sentences. Facts stored by a version before 2026-11-21 midday may still hold single English strings.
- One "too_far" on a walk adds a `walk_limit_m` fact 10 m below that walk's distance with `status: "candidate"`. A candidate counts for routes only on the day of the newest "too_far" tap (the dates are in `feedback[].at`; a fact's own `at` has no date). After that day it stays in memory as `candidate`, is not applied, and becomes `kept` on the next "too_far". A second "too_far" makes it `kept` and keeps the lower of the old and the new value. "fine" is stored in `feedback` and changes nothing.
- When a learned limit and the limit from her `walk` answer both exist, the lower one applies when a route is built, so a learned limit never lifts her answer. A learned limit alone, or her answer alone, applies as it is. The long-walk warning names the learned limit only when that is the one that applies.
- `changed_legs` is filled only for `walk_limit_m`, when a route is published: the walks of that route judged differently than her answer alone would judge them. A tap does not rewrite the published route.
- Forgetting `walk_limit_m` also deletes the "too_far" taps it came from. "fine" taps stay; no tool deletes them. Forgetting an answer also removes it from this session's `profile` (routes then use the code's default for it: stairs not avoided, 600 m), so the page should ask that question again. Forgetting a pick removes the fact, not the session's `picks`.
- Memory is kept per user id (the page uses `traveller`), by the server's session storage. A new session of that user has `user:memory` in its state from the start.

### 6.2 Tools (worker A; both are in the policy table in `gilmate/guards.py`)
```
record_feedback(leg_id: str, verdict: "fine"|"too_far") -> {status: "recorded"|"rejected", fact|null, reason?}
forget_fact(fact_id: str) -> {status: "forgotten"|"not_found"}
```
`leg_id` must be a walk of the published route; the distance is read from that route, never from the message. Each is allowed once per turn; a call refused by the policy table returns `{status: "denied", rule, message}`.
Page turns: `{"step": "feedback", "leg_id": "s1>s2", "verdict": "too_far"}` and `{"step": "forget", "fact_id": "f7"}`.
Free check: `tests/drill_memory.py`: one tap gives a candidate, two give kept, the next route's `fits_profile` flags change, forgetting the fact restores the old result.

### 6.3 Page: the knowledge graph, "What Gilmate knows about you" (the graph: `fm/gilmate-knowledge-graph`; the rest: worker B)
A knowledge graph of her memory, very little drawn: a pale ground with faint grey dots, small node dots, hairlines and quiet names. It starts as a tidy ring and can be moved. It is one function, `createKnow(host, panelHost, act)` in `frontend/js/know.js`, returning `{ render(view) }` as before: `host` is any element with a height (a tab or a dialog; the graph fills it and asks for at least 420 px), `panelHost` is the element the card is put into, or `null`, and then the card lives inside the graph. `view` and `act` are unchanged.
- The Gilmate guide in the middle. Three source nodes: "Your answers", "Your day", "Your picks". Every fact in `user:memory` is a node behind its source with its name under it (for example "Avoids stairs", "Walks up to 500 m"), in the order `walk`, `stairs`, `rest`, `food`, `wish`; `walk_limit_m`; `see`, `shop`, `eat`, and after those in the order saved. Several facts may share a key (two places to eat); each is its own node. A fact whose source is none of the three stands behind a fourth source, "Other", drawn only then: nothing kept is hidden. The ring is an ellipse cut to the ground, tall on a phone held upright; it grows when there are more facts than fit.
- Lines: a quiet line from the guide to each source; a hairline from a source to each of its facts. A `kept` learned fact has a solid blue line (the route colour), a blue dot and the words "learned, kept"; a `candidate` has a dashed blue line, a dashed ring and the words "still learning" under its name. State is said in words, never by colour alone.
- A `candidate` limit counts only on the day of its newest `too_far` row in `feedback`. On another day the page says "still learning, not in use today" and names that day; the fact stays in memory. A fact's `at` has no date, so the panel says "the day is not saved with it".
- Movable: every node can be dragged with mouse or finger (pointer capture, one finger at a time) and stays where it was put, its line ends following; the arrow keys move the node that has the focus. A released node settles with a light spring. Names do not lie on each other: after a drop the other nodes give way, the dropped one does not. The ground pans (drag the empty ground) and zooms between 0.4 and 2.5 (wheel, two fingers, and the small + / - buttons); a third button puts every node back in the tidy ring. Places are kept while the page is open and are not saved. Only transform and opacity move; with "reduce motion" everything is placed at once.
- Pressing a node opens a small card beside it (at the bottom on a ground narrower than 600 px, where the graph shifts so the node stays in view): what it knows, where it came from and when (`evidence`, `at`, and for the limit the `too_far` rows with their dates), what it changes (`effect`, and for the limit the walks in `changed_legs`), and "Forget this", which asks once ("Keep it" / "Yes, forget"). A source node lists its facts. A press on the empty ground, the card's x or Escape closes it. No hover cards. Controls are small pills (28 to 30 px) with a press area of 44 px on touch.
- Nothing is drawn that is not in `user:memory`: an empty memory shows the guide and three empty sources ("nothing yet"); when no memory could be read at all, only the guide and the reason.
- `evidence` and `effect` are drawn as given: a plain string as it is, an `{en, ko}` pair in the page's language. The page translates neither.
- In the Go view, at every stop after the first: "How was the walk here from ...?" with "Fine" and "Too far", for the walk that led there. One saved answer per walk and session; after it the buttons are gone, the `effect` of the returned fact is shown, and a button opens the map on that fact. A walk the learned limit judged differently (`changed_legs`) carries the chip "Judged by the limit learned from your taps" in Route and Go.
- When memory already holds her answers, the guide does not ask the five questions again. It says what it remembers (and the learned limit, if any) and asks "Still true?" with Yes / Change. Yes sends the remembered answers as `profile`; a question whose answer she made it forget is asked again, alone. Change asks all five with her old answers marked.

How the page talks to the agent (live, `?api=`):
- Every session uses the same user id, `traveller`. On load the page creates one session with an empty state and reads `user:memory` from it; "forget" turns go to that session until the planning session exists. The planning session is created with `profile` as its initial state, as before.
- Taps and "Forget this" are the turns of 6.2. The page reads the tool's own answer from the turn's events (`functionResponse` of `record_feedback` / `forget_fact`), then reads the session state again and redraws from it. `recorded` and `forgotten` are said as done. A turn may hold several answers of one tool (the model sometimes calls it a second time and is refused then): one `recorded` or `forgotten` among them counts as done, and only when none says so is the last answer the reason given. `rejected` (with its `reason`), `not_found` and the policy plugin's `denied` (with its `rule`) are said as "Not saved" / "Not forgotten" with that reason, and nothing on the page changes. A turn without a tool answer is said as not saved; for "forget" the fact being gone from the state counts as done.
- Without a live agent (a saved run, a development sample) the two buttons and "Forget this" are switched off and the page says why. Nothing is simulated.
- A saved run may carry `user:memory` next to its other keys; then the map and "Still true?" show it. Without it the map says that the saved run holds no memory.

Language: English by default. When she writes to the guide in Korean (an own-words answer, the wish, a question to the companion), the page turns Korean: its own words in every view, the map's names, labels and panel texts included. The EN / 한국어 switch turns it either way; once she has used the switch, her writing no longer changes the language. Names, quotes and any text saved in English only are shown as given. The Korean words are in `frontend/js/words.js`; those of the knowledge graph and of `memory.js` are also in `frontend/js/know/words.js`, which is asked first there; a sentence without a Korean line there is shown in English.

Development samples and the free page check (all under `frontend/dev/`):
- `?dev=1` to `?dev=4`, written by `python3 frontend/dev/make_samples.py`, which lets `gilmate/memory.py` write each memory: 1 a kept limit that changed two walks, 2 a limit learned today (and `evidence` / `effect` as `{en, ko}`, the Korean being the sample's own), 3 a limit from an earlier day (not in use today), 4 an empty memory. `_today` in a sample is the day it pretends to be.
- `frontend/dev/know-lab.html?dev=1` to `?dev=4` (`&lang=ko` for Korean) shows the knowledge graph alone on the same samples. There, and only there, "Forget this" is simulated: the fact is taken out of the sample in the tab and the page says so. `frontend/dev/know-check.py` opens it with Playwright at 1440x900 and at 390x844 with touch: it drags a node 120 px and checks that it stays and that its line end follows, drops a node on another, pans, zooms (wheel, buttons, two fingers), opens the card, forgets, and looks at the candidate, the empty memory and Korean. Free: no network, no key, no model. `check_page.py` below walks the map-first page and only opens the graph; the graph itself is checked by `know-check.py`.
- `frontend/dev/check_page.py` opens the page with Playwright at phone (390x844) and desktop (1440x900) size and at four more sizes, checks it and saves screenshots. Free: no network, no key, no model. Playwright is not a project requirement; the file's first lines say how to install it outside the repo and how to run the check.
- That check walks the live path against a stand-in inside the script, which answers the "feedback" and "forget" turns by calling `gilmate/memory.py` directly. It does not show that the coordinator calls the right tool, and it knows only the string shape of `evidence` / `effect` from the backend as it is on main. The page has not been run against the real agent by this check.

## 7. Map first (added 2026-11-21, 11:00; made more exact until 11:30; replaces the questions-first order)

She types where she wants to go, the scout searches and makes the map with the places found and the photos people took there, she chooses on the map, the guide asks about her body, and the route is built for the places she said Yes to. This section is the truth for all workers. Where sections 1 to 6 still describe the old order (five questions, two options per category, one pick per category, a `food` answer), this section wins.

### 7.1 The flow
1. A text field first. She types where she wants to go ("I want to visit Shibuya in Tokyo"). Python decides which area the text asks for: Shibuya or, since section 8, Hongdae, the two areas with map data.
2. The map is made, and the page shows the work step by step. The scout really searches the web (sights, well-rated places to eat, souvenir shops), Python chooses 8 to 10 places that are on the map, mixed, fetches photos of them and the photos taken in the area, lists the places to sit, and checks every fact. The page shows the real counts: places found, photos found.
3. She chooses on the map. Pressing a place opens its card: real photos of the place, what it is (a sight, a shop, somewhere to eat) with a short description, its facts with sources, access. Two answers, Yes and No. Yes puts it on her list; No dims it. She can change her mind. She may also type in her own words instead of pressing.
4. When she has said Yes to at least two places (at most five), the guide asks about her body, one question at a time with numbered choices: how far she walks comfortably (`walk`), stairs (`stairs`), how often she needs to sit (`rest`), and an optional free wish. No food question: `food` leaves the profile. Since the context turn (7.3) the page first asks for one free text and then asks with choices only what `profile_missing` lists.
5. The route is built for her Yes places with distances, stairs, benches and warnings, checked by the critic, and shown on the same map with real photos taken near every stop, walk and bench, and with the route note written out in sentences; then feedback (Fine / Too far) and memory as before. The walk itself (the Go view of section 6.3) is no longer on this page: the final map hands the route to the phone page `frontend/walk.html` by QR code, and "Fine" / "Too far" are pressed there.

### 7.2 State
```
area:       { name: "Shibuya, Tokyo"|"Hongdae, Seoul"|null, bbox: [south, west, north, east]|null, supported: bool,
              photo: place_photo|null,                                               # one real photo of the area for the front page
              key: "shibuya"|"hongdae", map: "data/map.json"|"data/hongdae/map.json" }   # only when supported: section 8
candidates: [ { id, category: "see"|"shop"|"eat", name, kind: {en, ko},            # "Statue", "Shopping centre", "Sushi restaurant"
                description: {en, ko}|null, description_source: {url, quote, ko?: {url, quote}}|null,
                rating: {value, source_url, quote}|null,                             # only a rating a source states
                facts: [ {label, value, source_url, quote} ],
                place: {lat, lon, osm_id, access},
                photos: [ place_photo ],                                             # photos of the place itself; may be []
                near_photos: [ near_photo ] } ]                                      # taken within 60 m of it; 8 to 10 places
place_photo:  { url, thumb_url, width, height, credit, licence, source_url, taken_at|null }
street_photos: [ taken_photo ]                                                       # the photo dots on the map
taken_photo:  { id, lat, lon, thumb_url, url, credit, licence, source_url, taken_at|null,
                source: "mapillary"|"kartaview"|"commons" }                          # only mapillary and kartaview are street-level
near_photo:   taken_photo + { distance_m }                                           # distance from the point it is shown for, at most 60
rest_spots: [ { id, lat, lon, kind: "bench", source: "osm:node/...", photos: [ near_photo ] } ]   # every bench the map has in the area
counts:     { places_on_map, places_shown, photos_found, street_photos, photo_sources: {source: n}, rest_spots }
said:       { about: candidate id|question key|null, choice, at: "HH:MM:SS" }       # the result of the last "say" turn
progress:   [ step ]                                                                # 7.4: the audit rows as steps, for the page
profile:    { walk: "short"|"medium"|"long", stairs: "avoid"|"few"|"ok", rest: "often"|"sometimes"|"rarely", wish: string|null, language: "ko"|"en" }
              # after a "context" turn: walk, stairs and rest only as far as the text told them (a key not told is absent)
profile_missing: [ "walk"|"stairs"|"rest" ]                                          # after a "context" turn: what the text did not tell; [] when it told all three
picks:      [ candidate id ]                                                        # 2 to 5, any category
route_note: { en, ko }                                                              # the route written out, one sentence per line
spatial_model: as in section 1, and also
  stops[].photos, legs[].photos, benches[].photos: [ near_photo ]                    # legs: up to 6 along the walk, in walking order
  photo_counts: { stops: {with, without}, walks: {with, without}, benches: {with, without} }
```
- A candidate id is `c1`, `c2`, ... in the order Python chose them. A stop's `option_id` is the candidate id.
- `description.ko` may be `""` when no Korean source text exists and the scout's Korean did not pass; the page then shows the English. `description: null` means "No description found".
- `frontend/data/candidates.json` holds `{area, candidates, street_photos, rest_spots, counts}` exactly as Python builds them from the committed caches without the model (`python3 scripts/make_candidates.py`). It is for building and testing the page; the demo and the saved run show what a real start turn returned. With the same saved searches the places and ids are the same; the turn adds descriptions, ratings and facts.
- `thumb_url` of a `place_photo` is a path below the page folder (`data/photos/...jpg`, 500 px wide, committed, credits in `data/photos/CREDITS.md`), so the place cards show their photos without network; `url` is the full picture at the source. `thumb_url` of a `taken_photo` is at the source and needs network; Mapillary's links expire after some days (delete `data/cache/photos/street_mapillary.json` and run the script again to renew them).
- `street_photos` holds at most 400 dots (street-level ones first); `counts.street_photos` is how many were found.

### 7.3 Turns
- `{"step": "start", "text": "I want to visit Shibuya in Tokyo"}` after session creation; state then has `area`. When `area.supported` is true the state also has `candidates`, `street_photos`, `rest_spots` and `counts`; when false they are null and the page says that only Shibuya has map data. About 40 to 70 seconds with the real model.
- `{"step": "candidates"}` is the same thing without text (the area is Shibuya). The old `{"step": "options"}` and `options` stay working until the new page has landed, then may be removed.
- `{"step": "say", "text": "...", "about": candidate id | question key | null}`: she typed instead of pressing. State then has `said` with one of the fixed choices of that step: for a candidate id `"yes" | "no" | "more"`; for `walk`, `stairs`, `rest` one of that question's values; for `null` (no card and no question open) `"yes" | "no"`; or `"not_understood"` for all of them. The model chooses, Python checks the choice against the allowed values (`gilmate/say.py`); nothing she typed is written into state. The page then acts as if she had pressed that choice, and must number its choices in the order of `say.allowed`: a place 1 yes, 2 no, 3 more; walk 1 short, 2 medium, 3 long; stairs 1 avoid, 2 few, 3 ok; rest 1 often, 2 sometimes, 3 rarely. The wish is not a `say` turn: it travels in the profile.
- `{"step": "context", "text": "..."}`: you tell the guide about yourself in one free text instead of pressing the answer buttons ("I can walk about 300 m, I can't climb stairs and I need to sit down often. I would love to see some street art."). State then has `profile` and `profile_missing`. The coordinator calls the tool `record_context(walk, stairs, rest, wish)` once. What the text says in an obvious way, in English or Korean, is decided by Python alone (`say.from_text`: a distance, "no stairs please", "자주 쉬어야 해요"; two parts that contradict each other decide nothing), and the model cannot change it. For the rest the model proposes a value and Python keeps it only when it is one of the question's fixed values (`say.accept`). `wish` is kept only when it stands word for word in the text (at most 200 characters) and does not read like an instruction. `language` is `"ko"` when the text holds Korean, else `"en"`. A text that reads like an instruction (the screen of section 4) gets a `blocked` audit row, and then only Python's own reading counts: the model's proposals and the wish are dropped. Nothing else of the text is written to state; the audit row holds the values, not the words (`walk=short; stairs=avoid; rest=; wish=no; missing=rest`, agent `traveller`, rule `human_decision`, or blocked `not_understood` when the text told nothing). A second context turn keeps what an earlier one told and fills in the rest, so the page can ask only for what is in `profile_missing`. With the real model the turn takes a few seconds.
- `{"step": "route", "picks": [candidate ids, 2 to 5], "profile": {walk, stairs, rest, wish, language}}`; state then has `spatial_model` and `route_note`. The profile arrives with this turn, not at session creation; Python reads it from the message itself and checks every value (an unknown value refuses the turn; a wish that reads like an instruction is dropped). Stop order is the router's, not her tap order. When the message carries no `profile`, the one already in the session counts (the one a context turn wrote); an answer still missing then falls back to the code's default for it (walks up to 600 m, stairs not avoided, one bench shown per walk), so the page should ask for what is in `profile_missing` first.
- `ask`, `feedback` and `forget` are unchanged (sections 3 and 6.2).
- What the page on main sends (checked 2026-11-21, 13:00): `start`, `context`, `route` and `forget` from `frontend/js/main.js`, and `feedback` from the phone page (`frontend/js/walk/main.js`, only when the agent server can be reached from the phone). It sends no `say`, no `ask` and no `candidates` turn: those three work on the server and are exercised by `tests/e2e/check.py` only.

### 7.4 Progress: what the agents do, step by step
`state.progress` is the audit list as steps the page can show while and after a turn: one step per audit row, in the same order, made by `gilmate/progress.py` each time a row is written.
```
progress: [ { id: "p1", label: {en, ko}, agent, tool, status: "done"|"blocked"|"withheld", detail: {en, ko}, t: "HH:MM:SS" } ]
```
The audit rows themselves stay as in section 1: `{t, agent, tool, decision, rule, detail}` with `detail` a plain string. The rows that carry numbers write them as `key=value; key=value`, which the steps read. A saved run keeps `audit` and `progress`. The rows of a start turn, in order:

| # | tool (agent `scout`) | rule | detail | the step says |
|---|---|---|---|---|
| 1 | `read_request` | `area_supported`, or blocked `area_not_supported` | `area=Shibuya, Tokyo` | Request read |
| 2 | `search_places`, once per category | `screened` | `category=see; passed=9; withheld=0; source=saved` (or `fresh`) | Search results screened: sights; 9 passed, 0 withheld |
| 3 | `find_place`, once per candidate | | `name=Shibuya Sky; access=yes` | Looked up on the map: Shibuya Sky |
| 4 | `find_candidates` | `candidates` | `places_on_map=785; places_shown=12` | Places chosen from the map |
| 5 | `place_photos` | `photos` | `places=12; photos=22; street_photos=1381; without=5; commons=963; mapillary=418` | Photos fetched |
| 6 | `rest_spots` | | `benches=11; with_photo=11` | Benches looked up on the map |
| 7 | `ground_candidates` | blocked with the failed rule per place dropped, then `grounding` | the place's name; `kept=12; dropped=0` | Refused by the grounding check; Grounding check |
| 8 | `map_ready` | `done` | `places=12; photos=1403` | Done |
| 9 | `describe_candidates`, once per place changed or refused | none, or blocked with the failed rule | `name=Loft; added=description,description_source`; the place's name | Added, with its source: Loft; Refused by the grounding check |
| 10 | `descriptions_checked` | | `added=5; dropped=1` | Descriptions checked against their sources |

Between them stand the policy plugin's own rows, one `allowed` row per tool call (`detail` is the call's category or name, for example `category=see`) or a `blocked` row with the rule, and a `withheld` row for every search result that was screened out. Her typed answer is a row of agent `traveller`, tool `record_said`, rule `human_decision` (or blocked, `not_understood`).

### 7.5 Rules
- Photos are real photos from a source that states author and licence; each is shown with its credit. No photo is shown that a tool did not return; a place without photos says "No photo found".
- A photo of a place (`candidates[].photos`) comes from Wikimedia Commons: the picture Wikidata names for the place, files in the place's own Commons category, or a file that names the place. It counts only when it was taken within 300 m of the place (150 m when found by name), or, without coordinates, when it is from the place's own entry and says Shibuya. A restaurant of a chain usually has none.
- A photo of where to go (`street_photos`, `rest_spots[].photos`, and the `photos` of stops, walks and benches) carries its own coordinates. Street-level photos are Mapillary's when `MAPILLARY_TOKEN` is set when the program runs (credit "Mapillary contributors", CC BY-SA 4.0); without the token KartaView's public API is asked. Wikimedia Commons photos with coordinates are added with `source: "commons"` and are never called street view. Nothing farther than 60 m is attached to a stop, a walk or a bench.
- Descriptions and kinds come from sources, never from the model's memory. `kind` is the map tag through a fixed table. A description is copied by Python from Wikipedia, Wikidata or the map's note, or written by the scout from a search result; a written one is checked sentence by sentence against its page (every number and name, and two thirds of the other content words, must stand there), unsupported sentences are cut, and a description with nothing left is dropped (`description: null`). The scout's Korean is kept only when nothing was cut and its numbers and Latin-letter names stand in the page; it is a translation and is not proofread.
- "Top rated" is only ever said with a rating a source states: `rating` holds the value, the page it is from and the quote, and the page must name the place. Without one the place is listed with no rating claim (`rating: null`).
- Every candidate's name, coordinates and access are the map's (section 1's rule for options).
- Which places are offered (`candidates.choose`, fixed rules, no place is written into the output by hand): a place is a sight when the map tags it as attraction, viewpoint, artwork, museum or gallery, or as a named crossing with its own Wikidata entry (the Shibuya Scramble Crossing is a junction on the map, named "渋谷駅前"; its kind is "Crossing"). A search result names a place when it holds any name the map has for it, written as the map writes it: `name:en`, `name`, `name:ja`, `name:ko`, `alt_name`, `official_name`, `short_name` ("Shibuya Scramble Crossing", "Shibuya Crossing", "渋谷スクランブル交差点"); a longer name of another place does not count ("Watch Shibuya Crossing"). `find_place` matches the same names. Among the sights, the ones most screened search results name come first and are looked up for photos first; after that the score decides (Wikidata entry, named by a result, access known, opening hours, a real photo). At most four per category, at most two of one kind among sights and shops, one of a kind among places to eat.
- `route_note` is assembled by Python from the spatial model (`gilmate/note.py`: stops, distances, stairs, benches, warnings); the model does not write it.
- Every text written for the page (advice, warnings, memory evidence and effect, the route note, progress steps, descriptions) speaks to the person using it as "you". The fixed sentences never say her, she, mom, older or elderly; the agents are told the same, and a walk's advice that does is replaced by Python's sentence (rule failure `note.not_addressed_to_you`).
- Memory (section 6): her answers are `walk`, `stairs`, `rest`, `wish` (ids `f1` to `f4`); `food` is no longer kept. Each pick is a fact in group `picks`: the first pick of a category has the key `see`, `shop` or `eat`, a further one of the same category `see2`, `see3`, and so on. A pick she no longer has is dropped from memory at the next route turn.

## 8. Areas (added 2026-11-21, 12:00)

The area is a parameter. `gilmate/areas.py` holds one row per area: name, bounding box, map extract, the page's folder, the web searches and the cache folders. Two areas have map data: `shibuya` (Shibuya, Tokyo; the default) and `hongdae` (Hongdae, Seoul).

- `read_request` decides from the typed text which area is meant (`areas.which`): Shibuya, 渋谷, 시부야; Hongdae, Hong-dae, Hongik, 홍대, 홍익대, 弘大, ホンデ. When the text names two, the first one counts. Any other text is not supported, and the scout is told to say that only these two have map data.
- `state.area` of a supported area also holds `key` (`"shibuya"` or `"hongdae"`) and `map`, the path of the area's map drawing file below the page folder. An unsupported area keeps exactly `{name: null, bbox: null, supported: false, photo: null}`. A state without `area.key` (a run saved before this section, the older page) is Shibuya.
- Every tool works on the area of its own session (`state.area.key`), so one server can hold a Shibuya session and a Hongdae session one after the other. Two sessions of different areas whose tool calls run at the very same moment are not protected from each other: the area in use is one value per server process.
- `{"step": "candidates"}` (no text) stays Shibuya.

Files per area (the row in `gilmate/areas.py` names them):

| | Shibuya (`shibuya`) | Hongdae (`hongdae`) |
|---|---|---|
| box (south, west, north, east) | 35.6570, 139.6975, 35.6632, 139.7050 | 37.5506, 126.9196, 37.5576, 126.9274 (about 780 m by 690 m, around Hongik University station) |
| map extract | `data/shibuya_osm.json` | `data/hongdae_osm.json` (`python3 scripts/fetch_osm.py --area hongdae`, one free request) |
| map drawing file | `frontend/data/map.json` | `frontend/data/hongdae/map.json` (`python3 scripts/make_map.py --area hongdae`) |
| places without the model | `frontend/data/candidates.json` | `frontend/data/hongdae/candidates.json` (`python3 scripts/make_candidates.py --area hongdae`) |
| saved real run | `frontend/data/run.json` | `frontend/data/hongdae/run.json` |
| small place photos, `thumb_url` | `frontend/data/photos/`, `data/photos/...jpg` | `frontend/data/hongdae/photos/`, `data/hongdae/photos/...jpg` |
| photo cache | `data/cache/photos/` | `data/cache/hongdae/photos/` |
| saved searches, Wikipedia texts | `data/cache/tavily/`, `data/cache/wiki/` | the same two folders (a search is saved under its exact words, a text under its Wikidata id) |

What Hongdae's map holds (OpenStreetMap, fetched 2026-11-21): 290 streets and paths, 13 of them steps, 1126 buildings, 19 benches, 962 named places inside the box (14 sights, 419 shops, 529 places to eat). 1037 of 1075 path points are one connected network, so walks are routed along streets. It is thinner than Shibuya's in two ways that show on the page: only 20 places carry a wheelchair tag, so nearly every entrance is "access unknown", and no sight has a Wikidata entry, so no description is copied from Wikipedia and the scout writes them from the search results under the usual checks.

### 8.1 How the page shows more than one area

The page does the following since 2026-11-21, 13:00 (before, it read Shibuya's three files by fixed path and knew one area by name). The first area of `areas` (the `default`) is the one drawn on the landing screen; a development sample (`?dev=`) knows only Shibuya. The phone link carries `?area=<key>` for every area but the first, and the phone page also finds the area by the name the route carries. While a live start turn runs, the page draws the map of the area the typed words seem to name; the answer of the turn decides.

1. Read `data/areas.json` once at load. Draw one "Last runs" card per entry of `areas` whose `run` is not `null`: the name is `name` cut at the comma ("Hongdae" over "Seoul"), the picture is `photo.thumb_url` (Hongdae: `data/hongdae/photos/area_hongdae.jpg`, Striker9498, CC0; its `credit` and `licence` stand in CREDITS.md, not on the card), no picture when `photo` is `null`.
2. `frontend/js/api.js`: `loadRun`, `loadEarly` and `loadMap` take the area's entry and fetch its `run`, `candidates` and `map` instead of `data/run.json`, `data/candidates.json` and `data/map.json`. Shibuya's entry holds exactly those three paths, so it behaves as today. The walk page (`frontend/js/walk/main.js`) reads the same three paths and needs the area too (for example `?area=hongdae` in the handoff link).
3. Pressing a card opens that area. Without a backend: replay that area's saved run. Live: send `{"step": "start", "text": <the entry's example>}` ("I want to visit Hongdae in Seoul"); `{"step": "candidates"}` is Shibuya only.
4. Typed text without a backend: `asksForShibuya` in `frontend/js/main.js` becomes "which entry's `words` does the lower-cased text hold" (the one named first wins); no match is the not-supported note. Live, nothing is matched on the page: after the start turn `state.area.supported` and `state.area.key` say it.
5. The map drawing: live, load `state.area.map` once the start turn has answered (it is `data/hongdae/map.json` for Hongdae) and set the map up again from it. Each `map.json` has its own `origin` and `bearing_deg` (Hongdae: 0; Shibuya: 24), and a `[lon, lat]` becomes metres with the `origin` of the same file, so Shibuya's file must not stay loaded for a Hongdae session.
6. Words that say Shibuya: the title of the choosing view, "Gilmate · Shibuya", "Photo of Shibuya" and the not-supported sentences ("only Shibuya in Tokyo has one today") take the area's `name`; the not-supported note names every entry of `areas`.
7. Nothing else changes: the session state, the turns and the shapes of `run.json` and `candidates.json` are the same for both areas. `thumb_url` of a place photo is already a full path below the page folder.

What Hongdae's data holds, so the page says it as it is (run of 12:35): 10 places (3 sights, 4 shops, 3 places to eat); `photos` is `[]` for every place, so each card says "No photo found", and 8 of the 10 carry `near_photos`; 139 photos taken in the area, 23 of them street-level (Mapillary, all from 2019) and 116 from Wikimedia Commons; 19 benches; every picked stop has `access: "unknown"`; 5 of 10 places have no description (`description: null`); no rating. The route for Olive Young, Trick Eye Museum, Hongdae Dakgalbi and Hongdae Mural Street was published as verified after two reviews; two of its three walks are longer than the 300 m asked for and say so.

## 9. Dangers of the day: weather, darkness, air (added 2026-11-21, 12:40; `gilmate/weather.py`, `fm/gilmate-weather`)

Conditions today that could be dangerous on a walk, for the place being visited (the middle of `area.bbox`). Each is a fixed verdict Python decides from a free source without a key, shown with its source, and able to shorten or flag walks by rule. No model judges the weather or writes a sentence about it. Nothing is called dangerous that a source did not report, and nothing found is said as "No warning found", never as safe.

Optional at run time: with no network, a timeout (4 s), an unusable answer, `GILMATE_OFFLINE=1` with nothing saved, or `GILMATE_WEATHER=off`, the route is exactly the one built without this section, `weather` and `dangers` are `null`, and one audit row says the source was not available. A session without `area` (the older questions-first page) is never read for.

Sources: Open-Meteo's forecast (`api.open-meteo.com/v1/forecast`: hourly temperature, apparent temperature, precipitation probability, precipitation, weather code, wind, gusts, UV index, snowfall; daily sunrise and sunset) and its air-quality forecast (`air-quality-api.open-meteo.com/v1/air-quality`: US AQI). Each answer is saved for the hour in `data/cache/weather` (git-ignored: a forecast must not be replayed on another day; `GILMATE_WEATHER_CACHE` names another folder). Only the hours of today still to come at the place count.

### 9.1 State
```
weather: null | { summary: {en, ko},                       # the line for the page: "Rain likely this afternoon: shorter walks"
                  verdict: "dry"|"rain"|"heat",            # one word for ordering places (weather.order_hint; null = "unknown")
                  rain: "none"|"possible"|"likely", heat: "ok"|"hot"|"very_hot", cold: bool, shorter_walks: bool,
                  dangers: [danger], local_time, sunrise, sunset, rain_chance_pct, feels_like_c: {min, max},
                  source_url, fetched_at, sources: [url],
                  hours: [ {time, temperature_c, feels_like_c, rain_chance_pct, rain_mm, weather_code, wind_kmh,
                            gust_kmh, uv_index, snow_cm, us_aqi} ] }
dangers: null | [ { kind: "thunderstorm"|"ice"|"snow"|"rain"|"heat"|"wind"|"cold"|"air_quality"|"uv"|"darkness",
                    level: "watch"|"warning", text: {en, ko}, effect: {en, ko}, source_url,
                    valid_from, valid_to,                   # the first and the last forecast hour it is true for, local time
                    shortens: bool } ]                      # worst first; the same list as weather.dangers
spatial_model.weather: { summary, rain, heat, cold, shorter_walks, dangers, usual_walk_limit_m, walk_limit_m,
                         flagged_legs: [leg id], dark_legs: [leg id], covered_benches: int, note: {en, ko},
                         source_url, fetched_at }           # only when a verdict was read
spatial_model.hazards[]: also kind "darkness"; a hazard written here has cause: "weather" and the forecast URL as source
spatial_model.benches[]: covered: true on a bench the map marks indoor=yes or covered=yes
```
- `dangers: null` means no source answered (unknown). `[]` means the sources answered and no warning was found.
- State also holds `weather_checked_at` (when the sources were last asked; they are asked again after five minutes), which the page does not read.

### 9.2 Rules (product choices, constants at the top of `gilmate/weather.py`)
| kind | watch | warning | shortens walks |
|---|---|---|---|
| rain | chance 60 % or 1 mm in an hour ("likely") | 10 mm in an hour | both |
| thunderstorm | | weather code 95, 96, 99 | yes |
| heat | feels like 30 °C | feels like 35 °C | warning only |
| uv | UV index 6 | UV index 8 | no |
| wind | gusts 50 km/h | gusts 75 km/h | warning only |
| cold | feels like 5 °C or less | feels like -5 °C or less | warning only |
| snow | snowfall or weather code 71 to 77, 85, 86 | | yes |
| ice | | freezing rain or drizzle, code 56, 57, 66, 67 | yes |
| darkness | after sunset, before sunrise, or sunset within 120 minutes | | no |
| air_quality | US AQI 101 | US AQI 151 | warning only |

- When a danger shortens walks, the walking limit that applies (her answer, or the learned limit, section 6) is lowered by a quarter for this route. A walk longer than the lowered limit and not longer than the usual one gets `fits_profile: false` and a `long_walk` hazard with `cause: "weather"`, both limits in its sentence and the forecast as `source`. Walks over the usual limit keep their own warning. With no limit (`walk: "long"`, nothing learned) nothing is flagged and the note says so.
- Then, too, benches the map marks as indoors or under cover are listed first on the walks that have one near (`covered: true`); other walks keep their benches. Stops are her picks and are never changed.
- Darkness: a walk that would end after sunset when setting out at the time of the reading, at 50 m a minute and with no time at the stops, gets a hazard of kind `darkness`. `fits_profile` is not changed by it.
- With no danger the stops, walks, warnings and benches are untouched; only `spatial_model.weather` is added.
- `route_note` gets one line after the order line, `spatial_model.weather.note`: the worst danger (or "No warning found in today's forecast"), what it changes, how many more there are, and "Source: Open-Meteo, read at HH:MM".
- The router and the critic see the verdict in the facts they are given: `walking_route` and `read_draft` return `weather` (rain, heat, cold, dangers, what it changes) and `her_limit_m` already lowered.

### 9.3 Tool and audit rows
```
weather_today() -> {status: "ok", rain, heat, cold, shorter_walks, sunset, local_time, summary, dangers, source, what_it_changes}
                 | {status: "unavailable", message}
```
The router may call it once per turn (`gilmate/weather_tool.py`; in the policy table through `gilmate/security.py`). The sources are read by Python at the router's first `walking_route` at the latest, so the route does not depend on the model calling it. Audit rows, all `tool: "weather_today"`, `decision: "allowed"`:

| rule | detail | the step says |
|---|---|---|
| `weather` | `rain=likely; heat=ok; cold=no; dangers=rain:watch; shorter_walks=yes; source=open-meteo.com; from=fresh` (or `saved`) | Today's weather read from Open-Meteo |
| `weather_not_available` | `source=open-meteo.com; reason=offline; the route is built without it` (or `switched_off`, `TimeoutError`, `URLError`, `no_usable_hours`, ...) | Weather not available: the route is built without it |
| `air_quality` | `air_quality=no_warning_found; source=air-quality-api.open-meteo.com; from=fresh` | Today's air quality read from Open-Meteo |
| `air_quality_not_available` | `source=air-quality-api.open-meteo.com; reason=...` | Air quality not available: left out |

### 9.4 The climb on each walk (`gilmate/climb.py`): built, switched off
**Off by default; `GILMATE_CLIMB=on` switches it on.** Measured on 2026-11-21, the heights are a surface model that includes buildings and raised tracks: along the flat walk from Shibuya Hikarie to the Scramble Crossing the samples read 34, 34, 32, 43, 35, 41, 41 m, which would be shown as "climbs about 17 m". In Hongdae the samples looked like ground. A climb shown as a fact would be wrong in the centre of Shibuya, so no route carries it until the numbers are checked against a ground model. No heights are committed for the saved routes for the same reason. What follows describes it when switched on.

The map has stairs but no hills. Ground heights along each walk's line (one about every 90 m, at most 12) come from Open-Meteo's elevation endpoint (`api.open-meteo.com/v1/elevation`, free, no key, a 90 m grid, so every number is "about") and are saved in `data/cache/elevation/heights.json` (git-ignored while the feature is off; `GILMATE_ELEVATION_CACHE` names another file).
```
spatial_model.legs[]: climb_m, descent_m, climb_source      # metres up and down along the walk; absent when a height is unknown
spatial_model.hazards[]: also kind "climb", cause: "elevation", source: the endpoint
```
- A walk is steep from 8 m up for `stairs: "avoid"`, 12 m for `"few"`, 20 m otherwise (product choices, `climb.STEEP_M`). A steep walk gets a `climb` hazard ("This walk climbs about 9 m ..."); for `"avoid"` it also gets `fits_profile: false`, like stairs. Its sentence is in the route note with the other warnings.
- A height that is neither saved nor answered (offline, timeout, `GILMATE_WEATHER=off`) is unknown: the walk keeps no `climb_m` and nothing is flagged. Only sessions with `area` are read for.
- One audit row per draft, `tool: "climb"`, `decision: "allowed"`: rule `elevation` with `walks=3; known=3; steep=1; source=open-meteo.com; from=saved` (or `fresh`), or `elevation_not_available` with `reason=...`.
- The router does not see the climb when it compares orders (`walking_route` does not return it), and `osm.check_model` does not recheck it.

Free check: `python3 tests/drill_weather.py`, on the made-up forecasts in `tests/fixtures/weather_*.json` (dry, rain likely, very hot) and variants of them: every row of the table above, the route flags, and that with the source not answering the route equals the one built without it; the climb on real saved heights (`tests/fixtures/elevation_heights.json`).

Not built: official severe-weather warnings (typhoon, heavy rain) from the Japan Meteorological Agency; the weather at the start turn (it is read when the route is built, so `weather` is not in state while she chooses places; whoever orders places by it calls `weather.ensure(state, agent, tools.log)` first). The Korean sentences were not proofread. The page does not show `weather`, `dangers` or the `darkness` hazards' own word yet (an unknown hazard kind is drawn as "Check here" with its sentence).
