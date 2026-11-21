# Security

Gilmate is a tour guide made of five agents. It reads the web, a map, photo sites, a weather service and what you type, and it turns that into a route. This page says what is defended, how it was checked, and what is not defended. It was written on 2026-11-21 between 12:45 and 13:25, at the hackathon, from the code as it stood then.

## 1. What is defended, and how

**The model writes sentences. Python owns the facts.** Every coordinate, distance, stair, bench, warning and source is computed or copied by plain Python (`gilmate/osm.py`, `gilmate/candidates.py`, `gilmate/note.py`, `gilmate/weather.py`). A model can propose an order of stops and write a line of advice. It cannot change a number, a name or a place, and the route note is assembled by Python, not written by a model.

**A tool that is not listed is refused.** `gilmate/guards.py` holds one table, `POLICY`: tool name, how often it may be called in a turn, and which values an argument may have. `gilmate/security.py` is a plugin that every agent runs behind; it checks each call against the table before the tool runs. A name that is not in the table is refused with `deny_by_default:tool_not_in_policy`, and that holds for tools that arrive over MCP too, because they are checked by name like any other. A call with something shaped like a key in its arguments is refused, whatever the tool.

**Text from outside is data, never an instruction.** There are three layers:

1. Web search results are screened before a model sees them (`guards.screen_results`). A result that addresses an AI, asks to ignore instructions, or orders a payment or a passport number is withheld whole, in English, Korean or Japanese. Google Places records get the same screen, record by record (`places.screen`).
2. New today: every string in every tool answer is screened once more, on its own, just before the model reads it (`guards.screen_fields`, called by the plugin). This is the layer that catches what the first one never looked at: a place name from the map, a field of a record, a warning text. A string that reads like an instruction is replaced by `[withheld: this text read like an instruction]`. Numbers and the rest of the answer stay.
3. What you type is read by Python, not retold by a model. A typed answer becomes one of a few fixed choices or `not_understood`. A sentence about yourself becomes fixed values for walking, stairs and resting; a wish is kept only when it stands word for word in your text, is at most 200 characters and does not read like an instruction. Nothing else you type is written into the session.

**A source and a quote for every fact.** A description, a rating or a fact about a place is kept only when its source was really read in this session, the quote stands in that source, and every number is in the quote (`guards.ground_option`, `ground_description`, `ground_rating`). A description a model wrote is cut sentence by sentence to what its page supports. What cannot be tied to a source is dropped, and the card says "No description found". Missing data is "unknown", never "safe".

**A chained log.** Every tool call, every refusal and every withheld text is one row in `audit.jsonl`. Each row holds the hash of the row before, and the hash of the last row is kept beside the log, so an edited, removed or inserted row is found by `guards.verify_chain`. Keys are cut out of a row before it is written.

**Nothing books, pays or sends.** No tool writes outside the session and the cache folders. The agents can read; they cannot buy a ticket, send a message or call anyone. The companion is told to say so when asked.

**Keys only in a git-ignored file.** The four keys (Anthropic, Tavily, Mapillary, Google) are read from `.env`, which is git-ignored, as is the audit log. The Google key is passed only to the small MCP server of our own and sent only to `places.googleapis.com` in a header. A drill reads every file of the repository except `.env` and fails when anything shaped like one of the four keys appears.

## 2. Inventory

Read from `origin/main` at 12:55, which holds the weather work and Google Places. "Field screen" means layer 2 above. Every tool call is one `allowed` or `blocked` row in the chained log, written by the plugin; tools add their own rows where the table says so.

### 2.1 Tools

| Agent | Tool | In the policy table | Argument rule | Text in its answer screened before a model sees it | Writes to state, and through which check |
|---|---|---|---|---|---|
| coordinator | `scout`, `option_scout` | yes, 2 calls each | none | no: a specialist's report is a model's text | nothing itself |
| coordinator | `router`, `critic` | yes, 3 each | none | no, as above | nothing itself |
| coordinator | `companion` | yes, 20 | none | no, as above | nothing |
| coordinator | `record_picks` | yes, 1 (added in `security.py`) | picks and profile are read by Python from the page's own message | field screen | `picks` (2 to 5 ids that are on the map), `profile` (each answer one of the fixed values; wish screened, 200 characters), `user:memory` |
| coordinator | `record_said` | yes, 1 | the choice must be one of the fixed values for that question (`say.said`) | field screen | `said`: one fixed choice, none of your words |
| coordinator | `record_context` | yes, 1 | values kept only when fixed values (`say.accept`); a text that reads like an instruction gets no say through the model | field screen | `profile`, `profile_missing`; the audit row holds values, not words |
| coordinator | `record_feedback` | yes, 1 | `verdict` must be `fine` or `too_far`; the walk must be one of the published route | field screen | `user:memory`; the distance is read from the route |
| coordinator | `forget_fact` | yes, 1 | the id must be a fact in memory | field screen | removes one fact from `user:memory` |
| scout | `read_request` | yes, 1 | Python decides which area the words mean (`areas.which`) | field screen | `area`: one of two fixed rows, or "not supported" |
| scout | `search_places` | yes, 3 | `category` must be `see`, `shop` or `eat`; the queries are built by Python | result screen, then field screen | `seen`, `searched`: only results that passed |
| scout | `find_candidates` | yes, 1 | none taken | field screen (place names and descriptions) | `candidates`, photos, benches, counts: each place through `candidates.check` (source, quote, name and coordinates are the map's) |
| scout | `describe_candidates` | yes, 3 | every addition checked against a page that was read | field screen | additions that passed the grounding checks, nothing else |
| scout | `places_search` (MCP) | yes, 15, by name | `category` must be `see`, `shop` or `eat`; the server refuses an area without map data and a name that reads like an instruction | record screen in the server and again in the scout's hook (`places.screen`) | `places_results`, and rating, hours and entrance flag on a candidate: only a valid record inside the area's box, within 80 m of the map's place |
| scout | `place_details` (MCP) | yes, 5, by name | the id must be one a search of this server returned, letters and digits only | as above | as above |
| scout | any other MCP tool | no: refused by name | | | |
| option scout (older page) | `search_options` | yes, 3 | `category` as above | result screen, then field screen | `seen` |
| option scout | `find_place` | yes, 20 | none; the name is only compared with the map | field screen | nothing |
| option scout | `save_options` | yes, 4 | each option: on the map, a source that was read, a quote in it | field screen | `options` that passed |
| router | `walking_route`, `rest_spots` | yes, 12 each | ids are looked up in the session; an unknown id finds no place | field screen | nothing |
| router | `propose_route` | yes, 3 | every stop must be one of your picks | field screen | `draft`, `rule_failures`: built by Python, checked by `osm.check_model` |
| router | `weather_today` | yes, 1 (added in `security.py`) | none taken | field screen; its sentences are fixed ones written by Python from Open-Meteo's numbers | `weather`, `dangers`: verdicts from fixed thresholds, each with its source |
| critic | `read_draft` | yes, 6 | none taken | field screen (stop names, advice) | nothing |
| critic | `submit_review` | yes, 3 | approval counts only when no rule check failed | field screen | `spatial_model`, `route_note`: the draft, published after at most two rounds |
| companion | `route_facts` | yes, 6 | an unknown stop id falls back to the first stop | field screen | nothing |

### 2.2 Turns the page can send

| Turn | What you can put in it | What happens to those words |
|---|---|---|
| `start` | free text: where you want to go | The coordinator's model sees it. Python screens it and decides the area; only the area is written to state. |
| `candidates` | nothing | Shibuya. |
| `say` | free text, and which card or question it is about | The model picks one fixed choice; Python checks it. Nothing typed is stored. A text that reads like an instruction is noted in the log. |
| `context` | free text about yourself | See layer 3 above. Hostile text: a `blocked` row, only Python's own reading counts, no wish. |
| `route` | pick ids and a profile with a wish | Ids must be on the map; each answer must be a fixed value or the turn is refused; a wish that reads like an instruction is dropped. |
| `ask` | free text: a question | The companion's model sees it and answers from `route_facts` only. Nothing is stored. Noted in the log when it reads like an instruction. |
| `feedback`, `forget` | a walk id and `fine` or `too_far`; a fact id | Checked against the published route and against memory. |
| `options` (older page) | nothing | The older six options. |
| anything else | | The coordinator says it can only do these things; it has no tool that would do more. |

### 2.3 Outside sources of text

| Source | Where its text goes | Screened as data before a model sees it | Written to state through |
|---|---|---|---|
| Tavily search results (title, text, address) | scout, option scout | yes: result screen on every read, also from the saved files; then field screen | `seen`, only passed results; facts need a quote from them |
| Google Places (name, type, address, hours) | scout, as a short list; facts to the cards | yes: record screen twice | `places.attach`: valid record, inside the box, matched to a map place |
| Open-Meteo forecast, air quality, ground heights | router, as fixed verdicts | numbers only are read; no text of the service is passed on; field screen behind it | fixed thresholds in `weather.judge` |
| OpenStreetMap names | scout, critic, companion; the page | new today: field screen | names are copied as the map has them; a candidate's name must equal the map's |
| OpenStreetMap tags | nobody directly | not needed: kind through a fixed table, access through `access_label` (anything odd is "unknown") | fixed tables |
| Wikipedia and Wikidata texts | scout (as a description), the page | yes: `ground_description` drops a candidate whose description reads like an instruction; field screen behind it | copied by Python with its source and quote |
| Wikimedia Commons and Mapillary metadata (author, licence, links) | the page only; no tool hands it to a model | not screened, because no model reads it | `photos.has_credit`; shown as text |
| What you type (start, say, context, wish, question) | the coordinator; the question also the companion | cannot be withheld from the model it is addressed to; screened by Python before anything is stored, and noted in the log | fixed choices only; the wish word for word, screened |

Addresses and file names: every outside call goes to a fixed host with its parameters encoded. A search is saved under a hash of its words, a photo list under the map's own id, a Wikipedia text under an id that must be `Q` and digits, a Places answer under a fixed alphabet and a hash. No file name is taken from outside text as it is.

## 3. What was tested, and how

All of these are free: no network, no key, no model. `scripts/drills.sh` runs them all.

- `tests/drill_security_today.py`, new: planted instructions in a Places field, in a warning text, in a typed context sentence and in a map name are withheld or dropped, and each leaves a row in the log; an unlisted tool is refused by the table and by the plugin; every tool named in `gilmate/agent.py` has a row in the table; a key is cut out of a log row, refused as an argument, cut out of a tool answer; no file in the repository, the saved runs or the caches holds anything shaped like a key; cache file names stay plain for hostile words; nothing in the two saved real runs trips the new screen.
- `tests/drill_injection.py`: planted instructions in search results in three languages are withheld, ordinary travel text is not; an edited log is noticed.
- `tests/drill_policy.py`: the table, call limits and argument rules.
- `tests/drill_grounding.py`, `tests/drill_candidates.py`: a fact without a read source, a quote that is not in it, a number that is not in the quote.
- `tests/drill_audit.py`: the chain; edits, cuts and inserted rows.
- `tests/drill_context.py`, `tests/drill_say.py`: typed text reaches the session only as fixed choices.
- `tests/e2e/check.py --map-first`, run with this change at 12:53 and again at 12:56 on top of the weather and Places work: the map-first turns sent to the real ADK server as the page sends them, with a stand-in for the model and saved search results. All 19 checks passed, so the plugin's new steps do not disturb a normal start, typed answers, a route, a "too far" tap or a forget.
- The attack run: `python scripts/run_once.py --attack` plants `tests/fixtures/planted_result.json` (a fake ticket notice that orders a bank transfer and a passport number) into a real run with the real model. `tests/e2e/check.py --attack` does the same against a stand-in model that breaks the rules on purpose. Neither was run again for this change: the first costs money, the second needs a browser.

## 4. What is not defended, and what was not tested

Said plainly, because a judge should not have to find these.

- **No login.** Anyone who can reach the server can use it, and each use of the live agents costs money. There is no limit per person, only per turn.
- **One memory for everyone.** The page uses one fixed user id, and the id is part of the server's address. Whoever can reach the server can read that memory and delete it.
- **Whoever creates a session can fill its state.** The ADK server lets the caller set the first state of a session. A profile given there is not checked before it becomes part of the router's instructions, and keys such as `seen` or `candidates` could be set by hand, which would get past the source checks. The fix is a check of the first state on the server side; it is not built.
- **The phone link carries the route in its address.** Anyone who sees the QR code or the link sees the route. The walk page draws what the address holds.
- **A demo server on the hall's Wi-Fi.** No encryption; in phone mode it listens on every interface of the laptop. The list of allowed origins is not a lock.
- **The screen is a list of known phrasings.** It knows English, Korean and Japanese orders to an assistant. A cleverly reworded instruction, or one in another language, passes it. Behind it stand the things a sentence cannot talk its way past: the table, the source checks and the route's rule checks.
- **What you type reaches the model it is written to.** A typed instruction cannot be kept from the coordinator, or a question from the companion. What limits the harm is that these agents have few tools, each with fixed arguments, and none that acts in the world.
- **A hostile place name is hidden from the models but still in the session and on the page**, drawn as text. Dropping such a place belongs in `candidates.check`.
- **The log shows tampering; it does not prevent it.** It is not signed. Someone who can write both the log and the small file beside it can write a new chain.
- **The caches are trusted files.** Whoever can write `data/cache` decides what the agents "found". Saved search results are screened on every read; saved photo credits are not.
- **When the new screen changes an answer of `find_candidates` or `describe_candidates`, the Places hook does not run for that call**, so Google's facts are not attached then. The two Places tools are left to their own screen.
- **Korean is not proofread**, in the page's words or in the screen's patterns.
- **Not tested:** the new screen inside a paid run with the real model; Google Places with a real key together with the new screen (the drills check its record screen and its two rows in the table, without a key and without the network); the page of the two look branches for text drawn as HTML; two sessions of different areas at the very same moment.
