# End-to-end check

The real backend the way the page uses it (`adk api_server`, coordinator, tools, guards, policy plugin, per-user
storage in a temporary folder) and the page in a real browser. Free by default: the model is the scripted
`stand_in_model.py` and the search results are the fixtures in `fixtures/world.json`, so there is no key, no network
and no search. It is not a drill, because it needs Playwright, which is installed outside the repository:

```bash
uv venv /tmp/gilmate-pw && uv pip install -p /tmp/gilmate-pw playwright && /tmp/gilmate-pw/bin/playwright install chromium
/tmp/gilmate-pw/bin/python tests/e2e/check.py        # needs the project's .venv from the main README
```

- `--attack`: a planted search result, and a stand-in model that breaks the rules; the guards must hold.
- `--real`: PAID. The real model and the saved search results in `data/cache/tavily`. 32 or 33 model calls in the runs of 2026-11-21, no search for the food answer "sushi".
- `--out <folder>`: where the screenshots (390x844 and 1440x900), the server logs and the final state go.
- `--save-run <file>`: write the run as `frontend/data/run.json` expects it (only sensible with `--real`).
- `--map-first`: only the map-first turns of CONTRACT.md 7, sent to the server as the page sends them: a request for
  another city, the start turn, two typed answers, a route for four places, "too far", forget. No browser and no
  Playwright. The stand-in scout quotes its descriptions from the fixture results and invents one rating, which the
  grounding check must drop. With `--real --save-run` this is how `frontend/data/run.json` is recorded.
- `--context` (with `--map-first`): the answers are told in one free text, the context turn of CONTRACT.md 7.3, and
  the route turn then carries no profile. Free with the stand-in, which proposes nothing, so only what Python reads
  in the text counts. `--no-wish` leaves the wish out of that text.
- `--area hongdae` (with `--real --map-first`): the start turn asks for Hongdae in Seoul. The free run has fixtures
  for Shibuya only.
- `--food ramen|surprise`, `--walk short|medium|long`: her answers. `--frontend <folder>`: another copy of the page.

What it does: the five questions (or "Still true?" when the page knows her answers), six options, the Korean
switch, three picks, the route with map, Go, one question to the companion in Korean and one in English, the agent
panel, one "too far" and one "forget". The tap and the forget go through the page's own buttons and its knowledge
map when the page has them, otherwise straight to the API. In the free run the same traveller then comes a second
time, to see the learned limit change the route. When `frontend/data/run.json` exists, the free check also walks
through the page without a backend.

The stand-in answers the Anthropic Messages API on localhost; the real model adapter is pointed at it with
`ANTHROPIC_BASE_URL`, and `.env` is not loaded in that mode.
