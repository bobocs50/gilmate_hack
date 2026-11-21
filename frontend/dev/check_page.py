"""Open the page in a real browser, walk the map-first flow once, check it and take screenshots.

Free: nothing leaves this machine, no key, no model, no search. Run from the repo folder:

    python frontend/dev/check_page.py [folder for the screenshots]

It needs Playwright, which is not a requirement of the project. Install it outside the repo, for example:

    uv venv /tmp/gilmate-pw && uv pip install --python /tmp/gilmate-pw/bin/python playwright
    /tmp/gilmate-pw/bin/python -m playwright install chromium
    /tmp/gilmate-pw/bin/python frontend/dev/check_page.py /tmp/gilmate-shots

What it walks (CONTRACT.md section 7), with ?pace= so a saved run's steps are told faster than they really
took (the page's own pace is the run's: at least three seconds a step, about a minute in all):
  1. Desktop, development sample 4 (nothing remembered): the text field, a place that has no map, the map being
     made told in one line, Yes and No per place, a place pressed again on the map, the one open question, the
     route note in both languages, the final map with "Start the route" opening the phone handoff, the page in Korean, the Knowledge graph tab (that it opens
     the graph; the graph itself is checked by frontend/dev/know-check.py), the wordmark starting over.
     The guide types its sentence and the answers come when it is whole.
     On every screen: what can be pressed is counted, a card is a narrow column at the left edge and never
     over the map's middle or the guide, the bubble is one sentence, every button is at least 44 px high.
  2. Desktop, development sample 2 (answers kept from an earlier visit): a new visit starts with nothing
     remembered, so "Still true?" is not asked.
  3. Phone, development sample 4: the same line; a card is a sheet of at most half the screen.
  4. The saved real run (frontend/data/run.json), when there is one.
  4b. The weather of the day (CONTRACT.md section 9) with a made-up forecast put into sample 2: a danger, no
     warning found, and no answer from any source. The top bar shows a small mark (icon, average temperature,
     one word) from the backend's verdict or from the forecast read in the browser, and nothing when neither
     answers; the narration tells the forecast as one step. And a place's rating as one short line.
     Every request to the forecast is answered inside this script with a made-up one.
  5. The live path, against a STAND-IN and not against the agent. The browser's requests to http://stand-in.test
     are answered inside this script from sample 4: "start", "context" (two things left open) and "route".
     The stand-in has no model in it: it does not show that the agents call the right tools.
     Only a paid end-to-end run shows that. And an address where no server answers: the saved run is shown.

The script fails (exit 1) on a failed check or on an error in the browser console.
"""
import datetime
import functools
import http.server
import json
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.dirname(HERE)

from playwright.sync_api import sync_playwright  # noqa: E402

SIZES = {"phone": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "has_touch": True, "is_mobile": True},
         "desktop": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1}}
STAND_IN = "http://stand-in.test"
failures = []


def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        failures.append(what)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=FRONTEND))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def made_up_forecast(route):
    """Open-Meteo's answer, made up: 18 degrees and a clear sky all day, at a place where it is noon now."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    offset = (12 - now.hour) * 3600
    day = (now + datetime.timedelta(seconds=offset)).strftime("%Y-%m-%d")
    hours = list(range(24))
    route.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps({
        "utc_offset_seconds": offset, "hourly": {"time": [f"{day}T{h:02d}:00" for h in hours], "temperature_2m": [18.2 for _ in hours],
            "apparent_temperature": [18.0 for _ in hours], "precipitation_probability": [5 for _ in hours], "precipitation": [0.0 for _ in hours], "weather_code": [1 for _ in hours]}}))


def offline_context(browser, **options):
    """A browser context whose forecast requests are answered here: the check sends nothing to the network."""
    context = browser.new_context(**options)
    context.route("**/api.open-meteo.com/**", made_up_forecast)
    return context


def weather_mark(page):
    """What the weather mark in the top bar says, or None when it is hidden."""
    return page.evaluate("() => { const m = document.getElementById('weather'); return m && !m.hidden && m.offsetParent ? m.lastElementChild.textContent : null; }")


DEMO = ("My mom wants to visit Shibuya in Tokyo. She loves sushi. Stairs and steep hills are hard for her, and she can walk about 1 km "
        "before she needs to sit down. Show us the sights and the best-rated sushi places.")


class Shots:
    def __init__(self, page, folder, size):
        self.page, self.folder, self.size, self.n = page, folder, size, 0

    def take(self, name):
        self.n += 1
        try:                                     # the guide types its sentence; her choices come when it is whole
            self.page.wait_for_selector(".dock[data-ready]", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(700)          # panels rise in 220 ms, the map moves in 650 ms
        self.page.screenshot(path=os.path.join(self.folder, f"{self.size}-{self.n:02d}-{name}.png"))


def text(page, selector="#content"):
    return page.inner_text(selector)


def layout_checks(page, label):
    """Every pressable thing is at least 44 px high, nothing leaves the screen, the bubble is in sight."""
    small = page.evaluate("""() => [...document.querySelectorAll('#content button, .bar button, .map-controls button, .map-place')]
        .filter((b) => b.offsetParent && getComputedStyle(b).visibility !== 'hidden')
        .map((b) => { const r = b.getBoundingClientRect(); const a = getComputedStyle(b, '::after');
            const extra = a.content !== 'none' && a.position === 'absolute' ? 10 : 0;
            return [b.id || b.className.toString().slice(0, 24), Math.round(r.width), Math.round(r.height + extra)]; })
        .filter(([, w, h]) => h < 44 || w < 36)""")
    check(not small, f"{label}: every button is at least 44 px high ({small})")
    wide = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1")
    check(not wide, f"{label}: the page does not scroll sideways")
    line = page.evaluate("""() => { const r = document.querySelector('.dialogue .guide-line')?.getBoundingClientRect();
        return r ? r.top >= 0 && r.bottom <= window.innerHeight + 1 : false; }""")
    check(line, f"{label}: the guide's bubble is on the screen")


def nothing_over_the_map(page, label):
    """A card or list is a narrow column at the left edge (wide screens), under the top bar, and never under the guide."""
    box = page.evaluate("""() => { const c = document.querySelector('.work-content'); if (!c) return null;
        const r = c.getBoundingClientRect(); const bar = document.querySelector('.bar').getBoundingClientRect();
        const d = document.querySelector('.dialogue').getBoundingClientRect();
        return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, bar: bar.bottom, w: innerWidth, h: innerHeight,
                 over: !(r.right <= d.left || r.left >= d.right || r.bottom <= d.top) }; }""")
    if not box:
        return
    if box["w"] >= 700:
        check(box["right"] <= 380 and box["top"] >= box["bar"] - 12 and box["bottom"] <= box["h"] - 8 and not box["over"],
              f"{label}: the card is a narrow column at the left edge, clear of the top bar and the guide ({box})")
    else:
        check(box["bottom"] - box["top"] <= box["h"] / 2 + 1 and not box["over"], f"{label}: the card is a sheet of at most half the screen ({box})")


def one_sentence(page, label):
    """The bubble is one short line of words: no second paragraph, no small print."""
    parts = page.evaluate("() => [document.querySelectorAll('.guide-line .line-words').length, document.querySelectorAll('.guide-line small').length]")
    check(parts == [1, 0], f"{label}: the bubble is one sentence ({parts})")


def pressable(page):
    """What can be pressed on the screen, apart from the top bar and the places on the map."""
    return page.evaluate("""() => [...document.querySelectorAll('#content button:not(:disabled), #content input:not(:disabled)')]
        .filter((e) => e.offsetParent && !e.closest('.photo-frame')).map((e) => e.id || e.className.toString().split(' ')[0]).sort()""")


def walk(page, shots, dev, full=True):
    """The whole line once, in one development sample: landing, the map being made, Yes / No, what the guide should know, the note, the final map."""
    run = json.load(open(os.path.join(HERE, {2: "shape-sample-2.json", 4: "shape-sample-4.json"}[dev]), encoding="utf-8"))
    places = run["candidates"]
    label = f"dev{dev} {shots.size}"

    bar = page.evaluate("() => [...document.querySelector('.bar').children].map((c) => c.id || c.className)")
    check(bar == ["start-over", "view-tabs", "bar-tools"] and not page.query_selector("#menu-open"), f"{label}: the top bar is the wordmark, Map / Knowledge graph and the language ({bar})")
    check(page.get_attribute("#search textarea", "placeholder") == "I want to visit Shibuya, Tokyo", f"{label}: the empty text field would show the example sentence")
    field = page.evaluate("() => { const a = document.querySelector('#search textarea'); return [a.value, a.scrollHeight <= a.clientHeight + 1]; }")
    check(field == [DEMO, True], f"{label}: the text field comes filled in with the demo's sentence and shows all of it ({field})")
    landing = text(page)
    check("A tour guide that plans around you," in landing and "not the city" in landing and "Last runs" in landing, f"{label}: the headline and Last runs are the given words")
    check(page.inner_text(".guide-line").strip() == "Type where you want to go, or open the last runs below.", f"{label}: the landing bubble is the one given sentence")
    check("Credits" not in page.inner_text("body") and not page.query_selector(".photo-credit, .ready-credit"), f"{label}: no credit line and no Credits link on the page")
    check(pressable(page) == ["composer-send", "start-button"], f"{label}: landing: only the filled-in field's button and the card can be pressed ({pressable(page)})")
    layout_checks(page, f"{label} landing")
    one_sentence(page, f"{label} landing")
    shots.take("landing")
    if full:
        page.fill("#search textarea", "I want to visit Paris")
        page.keyboard.press("Enter")
        check("only Shibuya in Tokyo has one today" in text(page) and page.query_selector("#search"), f"{label}: another place gets a plain sentence and no map")
        shots.take("landing-other-place")

    page.fill("#search textarea", "I want to visit Shibuya, Tokyo")
    page.keyboard.press("Enter")
    page.wait_for_selector(".making-head")
    first_line = page.inner_text(".guide-line")
    check(not page.query_selector(".work-content") and not page.query_selector(".run"), f"{label}: while the map is made there is no panel and no list")
    check("Replay" not in text(page) and not any(word in first_line for word in ("scout", "search_options", "save_options", "coordinator")), f"{label}: no replay wording and no tool or agent name ({first_line!r})")
    check(pressable(page) == ["making-skip"], f"{label}: making the map: only Skip can be pressed ({pressable(page)})")
    lines = page.evaluate("() => { const p = document.querySelector('.line-words'); return Math.round(p.getBoundingClientRect().height / parseFloat(getComputedStyle(p).lineHeight)); }")
    check(lines == 1 and page.get_attribute(".line-words", "data-working") is not None, f"{label}: the working sentence is one line and is marked as working ({lines})")
    one_sentence(page, f"{label} making")
    shots.take("making-step")
    seen = {first_line}
    for _ in range(40):
        if page.query_selector("#place-yes"):
            break
        page.wait_for_timeout(150)
        seen.add(page.inner_text(".guide-line"))
    page.wait_for_selector("#place-yes", timeout=15000)
    check(1 <= len(seen) <= 8, f"{label}: the bubble tells the sample's steps one at a time, a handful at most ({sorted(seen)})")

    first = places[0]
    check(first["name"] in text(page) and "Place 1 of" in page.inner_text(".spot"), f"{label}: the first place comes by itself")
    check(page.locator(".photo img").count() == len(first["photos"]), f"{label}: its pictures are shown, {len(first['photos'])} of them")
    check(pressable(page) == ["place-no", "place-yes"], f"{label}: a place: exactly Yes and No ({pressable(page)})")
    check(page.locator(".spot-rating").count() == 0, f"{label}: a place without a rating in its facts has no rating line")
    check(page.locator(".map-place").count() == len(places), f"{label}: every place is a button on the map")
    layout_checks(page, f"{label} place")
    nothing_over_the_map(page, f"{label} place")
    one_sentence(page, f"{label} place")
    shots.take("place-with-pictures")
    if full:
        page.click(".photo-nav[data-side=next]")
        page.wait_for_timeout(500)
        check(page.inner_text(".photo-count").startswith("2 /"), f"{label}: Next shows the second picture")
    said = page.evaluate("() => [document.querySelector('.dock').hasAttribute('data-ready'), document.querySelector('.untyped')?.textContent ?? '']")
    check(said == [True, ""], f"{label}: when the answers can be pressed the guide's sentence is whole ({said})")
    page.click("#place-yes")
    check(places[1]["name"] in text(page), f"{label}: after Yes the next place comes by itself")
    waiting = page.evaluate("""() => { const d = document.querySelector('.dock');
        return !d.hasAttribute('data-ready') && getComputedStyle(d.querySelector('.work-actions')).visibility === 'hidden'; }""")
    check(waiting, f"{label}: the answers wait while the guide says its sentence")
    check(page.locator('.map-place[data-state="yes"]').count() == 1, f"{label}: the Yes place is marked on the map")
    page.click("#place-no")
    third = places[2]
    check(third["name"] in text(page) and "No photo found" in text(page), f"{label}: a place without a picture says No photo found")
    shots.take("place-without-picture")
    if full:
        # A changed mind: the place answered No is pressed on the map and answered again.
        page.evaluate("() => document.querySelector('.map-place[data-state=\"no\"]').click()")
        check(places[1]["name"] in text(page) and page.get_attribute("#place-no", "aria-pressed") == "true", f"{label}: a place pressed on the map opens with the earlier answer")
        page.click("#place-no")
    while page.query_selector("#place-yes"):
        page.click("#place-yes")

    if dev == 2:
        # A visit starts with nothing remembered (the knowledge graph fills as she decides), so the answers kept
        # from an earlier visit are not asked about: the guide asks its one open question, as in sample 4.
        page.wait_for_selector(".dialogue .composer")
        check("Still true?" not in text(page) and not page.query_selector("#still-yes"), f"{label}: a new visit starts with nothing remembered, so Still true? is not asked")
        shots.take("what-i-should-know")
    else:
        page.wait_for_selector(".dialogue .composer")
        check(page.get_attribute(".dialogue .composer input", "placeholder") == "I have a bad knee and need to sit every ten minutes" and not page.query_selector(".choice"),
              f"{label}: one open question with a text field and no answer buttons")
        shots.take("what-i-should-know")
    page.wait_for_selector("#route-map", timeout=20000)
    model = run["spatial_model"]
    note = page.inner_text(".note-text")
    check(model["stops"][0]["name"] in note and "on foot" in note, f"{label}: the route note comes first, in sentences")
    check(pressable(page) == ["note-copy", "note-lang", "note-lang", "route-map"], f"{label}: the note: Show my route, and EN / KO and Copy inside the note ({pressable(page)})")
    nothing_over_the_map(page, f"{label} route note")
    one_sentence(page, f"{label} route note")
    shots.take("route-note")
    if full:
        page.click('[data-note-lang="ko"]')
        check("걸어서" in page.inner_text(".note-text"), f"{label}: the note has a Korean tab")
        shots.take("route-note-korean")
    page.click("#route-map")
    check(page.locator(".map-stop").count() == len(model["stops"]) and page.locator('.map-pill[data-kind="leg"]').count() >= 1, f"{label}: the route's stops are numbered and a walk carries its distance")
    page.wait_for_selector("#start-walk", timeout=5000)
    check(pressable(page) == ["start-walk"] and not page.query_selector(".work-content"), f"{label}: the final map: one thing to press, Start the route ({pressable(page)})")
    check("Your route is" in text(page) and "saved run" not in text(page), f"{label}: the bubble says the route's length and nothing about a saved run")
    layout_checks(page, f"{label} final map")
    one_sentence(page, f"{label} final map")
    shots.take("final-map")
    if full:
        # "Start the route" hands the route to the phone: the card with the QR code and the link to walk.html.
        page.click("#start-walk")
        page.wait_for_selector(".handoff .handoff-link:not(:empty)", timeout=8000)
        check("walk.html" in page.inner_text(".handoff-link") and page.query_selector(".handoff-code svg, .handoff-code canvas, .handoff-code img") is not None,
              f"{label}: Start the route opens the phone handoff with a QR code and the link")
        shots.take("phone-handoff")
        page.click(".handoff-close")
        page.click('#lang [data-lang="ko"]')
        check("경로는 걸어서" in text(page) and "지식 그래프" in page.inner_text(".bar"), f"{label}: the page is Korean after the switch")
        shots.take("final-map-korean")
        page.click('#lang [data-lang="en"]')
        page.click("#know-open")
        page.wait_for_selector("#know[open]")
        check(page.get_attribute("#know-open", "aria-pressed") == "true", f"{label}: the Knowledge graph tab opens the graph")
        shots.take("knowledge-graph")
        page.click("#know-close")
        page.click("#start-over")
        check(page.query_selector("#search") is not None, f"{label}: the wordmark starts over")


def korean_typing(page, shots):
    """Writing Korean into the text field turns the page Korean."""
    page.fill("#search textarea", "시부야에 가고 싶어요")
    page.keyboard.press("Enter")
    page.wait_for_selector("#place-yes", timeout=15000)
    check(page.evaluate("() => document.documentElement.lang") == "ko" and "가 보시겠어요" in text(page), "Korean: writing Korean turns the page Korean")
    shots.take("place-korean")


def stand_in(page, sample):
    """Answers the page's requests to the agent from one sample. No model, no search."""
    state = {"audit": []}
    turns = []

    def events(message):
        step = message["step"]
        turns.append(message)
        rows = []

        def tool(agent, name, response):
            rows.append({"author": agent, "content": {"parts": [{"functionCall": {"name": name, "args": {}}}]}})
            rows.append({"author": agent, "content": {"parts": [{"functionResponse": {"name": name, "response": response}}]}})
            state["audit"].append({"t": "12:00:00", "agent": agent, "tool": name, "decision": "blocked" if response.get("status") == "denied" else "allowed", "rule": response.get("rule", ""), "detail": ""})

        if step == "start":
            supported = "shibuya" in message["text"].lower()
            state["area"] = {**sample["area"], "supported": supported}
            if supported:
                tool("coordinator", "scout", {"status": "ok"})
                tool("scout", "search_options", {"status": "ok"})
                tool("scout", "search_options", {"status": "denied", "rule": "search_options.max_calls:3"})
                tool("scout", "find_place", {"status": "ok"})
                tool("scout", "save_options", {"status": "ok"})
                state.update(candidates=sample["candidates"], street_photos=sample["street_photos"], counts=sample["counts"])
        elif step == "context":
            # Nothing but walking could be told from the words: stairs and sitting down are left open.
            state.update(profile={"walk": "short", "stairs": None, "rest": None, "wish": message["text"]}, missing=["stairs", "rest"])
        elif step == "route":
            tool("coordinator", "router", {"status": "ok"})
            tool("router", "walking_route", {"status": "ok"})
            tool("critic", "submit_review", {"status": "ok"})
            state.update(picks=message["picks"], profile=message["profile"], spatial_model=sample["spatial_model"])
        elif step == "feedback":
            fact = {"id": "f1", "key": "walk_limit_m", "value": 300, "group": "day", "source": "feedback", "status": "candidate", "at": "12:00", "changed_legs": [],
                    "evidence": {"en": "Stand-in: you said too far.", "ko": "대역: 너무 멀다고 하셨습니다."}, "effect": {"en": "Stand-in: walks longer than 300 m are flagged today.", "ko": "대역: 오늘은 300 m보다 긴 구간을 표시합니다."}}
            tool("coordinator", "record_feedback", {"status": "recorded", "fact": fact if message["verdict"] == "too_far" else None})
            if message["verdict"] == "too_far":
                state["user:memory"] = {"facts": [fact], "feedback": [{"leg_id": message["leg_id"], "distance_m": 300, "verdict": "too_far", "at": "2026-11-21T12:00:00"}]}
        elif step == "ask":
            rows.append({"author": "coordinator", "content": {"parts": [{"text": "Stand-in answer: nothing was looked up."}]}})
        return "".join(f"data: {json.dumps(row)}\n\n" for row in rows)

    def handle(route, request):
        if request.url.endswith("/run_sse"):
            body = json.loads(request.post_data)
            message = json.loads(body["newMessage"]["parts"][0]["text"])
            route.fulfill(status=200, content_type="text/event-stream", body=events(message))
        elif request.method == "POST":
            route.fulfill(status=200, content_type="application/json", body="{}")
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"state": state}))

    page.route(f"{STAND_IN}/**", handle)
    return turns


def live_walk(page, shots, sample):
    turns = stand_in(page, sample)
    page.fill("#search textarea", "I want to visit Shibuya, Tokyo")
    page.keyboard.press("Enter")
    page.wait_for_selector("#place-yes", timeout=8000)
    check(turns[0] == {"step": "start", "text": "I want to visit Shibuya, Tokyo"}, f"live: the sentence is sent as the start turn ({turns[0]})")
    for _ in range(2):
        page.click("#place-yes")
    while page.query_selector("#place-no"):
        page.click("#place-no")
    page.wait_for_selector(".dialogue .composer input:not(:disabled)")
    shots.take("live-what-i-should-know")
    page.fill(".dialogue .composer input", "I have a bad knee")
    page.keyboard.press("Enter")
    page.wait_for_selector(".choice", timeout=8000)
    check(turns[-1] == {"step": "context", "text": "I have a bad knee"}, f"live: the words are sent as the context turn ({turns[-1]})")
    check("Are stairs a problem for you?" in text(page) and page.locator(".choice").count() == 3, "live: only what the words left open is asked, with its answers")
    shots.take("live-open-question")
    page.click(".choice")
    check("Do you need to sit down along the way?" in text(page), "live: the second open thing is asked next")
    page.click(".choice")
    page.wait_for_selector("#route-map", timeout=8000)
    route = turns[-1]
    check(route["step"] == "route" and len(route["picks"]) == 2 and route["profile"] == {"language": "en", "wish": "I have a bad knee", "walk": "short", "stairs": "avoid", "rest": "often"},
          f"live: the route turn carries the two places and the profile, without food ({route})")
    page.click("#route-map")
    shots.take("live-final-map")


def with_weather(sample, mode):
    """Sample 2 with a made-up forecast, as Python writes one (CONTRACT.md section 9): a danger, none, or no answer.
    And a rating from Google Maps among the first place's facts, as the Places section writes it."""
    run = json.loads(json.dumps(sample))
    at = next(index for index, row in enumerate(run["audit"]) if row.get("tool") == "record_picks")
    row = {**run["audit"][at], "tool": "weather_today", "rule": "weather_not_available" if mode == "missing" else "weather", "detail": "made up for the page check"}
    run["audit"].insert(at + 1, row)
    run["candidates"][0]["facts"] = (run["candidates"][0].get("facts") or []) + [
        {"label": "Google Maps rating", "value": "4.9 out of 5 (17,274 ratings on Google Maps)", "source_url": "https://example.org/made-up-for-the-check", "quote": "made up for the page check"}]
    if mode == "danger":
        dangers = [{"kind": "rain", "level": "watch", "text": WEATHER["text"], "effect": {"en": "shorter walks", "ko": "걷는 거리 줄임"}, "shortens": True},
                   {"kind": "darkness", "level": "watch", "text": {"en": "Dark after 16:30", "ko": "16:30 이후 어두움"}, "effect": {"en": "shown on the route", "ko": "경로에 표시"}, "shortens": False}]
        run["spatial_model"]["weather"] = {"summary": WEATHER["summary"], "dangers": dangers}
        run["weather"] = {"summary": WEATHER["summary"], "verdict": "rain", "rain": "likely", "heat": "ok", "cold": False, "dangers": dangers,
                          "hours": [{"time": f"2026-11-21T{hour:02d}:00", "temperature_c": temperature, "feels_like_c": temperature - 1, "rain_chance_pct": 70, "rain_mm": 1.2, "weather_code": 61}
                                    for hour, temperature in ((13, 15.0), (14, 14.6), (15, 14.0), (16, 13.4), (23, 2.0))]}
    elif mode == "none":
        run["spatial_model"]["weather"] = {"summary": WEATHER["none"], "dangers": []}
    return run


WEATHER = {"summary": {"en": "Rain likely this afternoon: shorter walks", "ko": "오후에 비 올 가능성 높음: 걷는 거리 줄임"},
           "text": {"en": "Rain likely this afternoon", "ko": "오후에 비 올 가능성 높음"},
           "none": {"en": "No warning found in today's forecast", "ko": "오늘 예보에서 경고를 찾지 못함"}}


def answer_with(body, route):
    route.fulfill(status=200, content_type="application/json", body=body)


def weather_walk(browser, base, folder, errors):
    """The weather of the day: the mark in the top bar and one step of the narration. And the rating line of a place."""
    sample = json.load(open(os.path.join(HERE, "shape-sample-2.json"), encoding="utf-8"))
    told = {"danger": "Checking today's weather: Rain likely this afternoon", "none": "Checking today's weather: No warning found in today's forecast",
            "missing": "Today's weather could not be read"}
    # danger: the backend's verdict is in the data (four hours until the evening at 14.25 degrees, rain likely).
    # none: no verdict in the data, so the forecast is read in the browser (made up here: 18 degrees, clear).
    # missing: no verdict and no answer from the forecast: nothing is shown.
    marks = {"danger": "14° · Rain likely", "none": "18° · Sunny", "missing": None}
    for mode in ("danger", "none", "missing"):
        page = offline_context(browser, **SIZES["desktop"]).new_page()
        page.on("pageerror", lambda e: errors.append(f"weather {mode}: {e}"))
        page.route("**/dev/shape-sample-2.json", functools.partial(answer_with, json.dumps(with_weather(sample, mode))))
        if mode == "missing":
            page.route("**/api.open-meteo.com/**", lambda route: route.abort())
        page.goto(base + "?dev=2&pace=5")
        page.wait_for_selector(".dock")
        page.wait_for_timeout(500)
        check(weather_mark(page) == marks[mode], f"weather {mode}: the landing's top bar says {marks[mode]!r} ({weather_mark(page)!r})")
        page.fill("#search textarea", "I want to visit Shibuya, Tokyo")
        page.keyboard.press("Enter")
        page.wait_for_selector(".making-head")
        check(weather_mark(page) == marks[mode], f"weather {mode}: the mark stays while the map is made ({weather_mark(page)!r})")
        page.wait_for_selector("#place-yes", timeout=15000)
        if mode == "danger":
            check(page.locator(".spot-rating").count() == 1 and page.inner_text(".spot-rating").strip() == "4.9 · 17,274 ratings on Google",
                  f"rating: the place panel shows the rating from its facts as one short line ({page.locator('.spot-rating').all_inner_texts()})")
            Shots(page, folder, "desktop-weather").take("place-with-rating")
        while page.query_selector("#place-yes"):
            page.click("#place-yes")
        seen = set()
        for _ in range(400):
            if page.query_selector("#route-map"):
                break
            seen.add(page.inner_text(".guide-line").strip())
            page.wait_for_timeout(80)
        page.wait_for_selector("#route-map", timeout=20000)
        check(told[mode] in seen, f"weather {mode}: the guide tells the forecast as one step of its own ({sorted(seen)})")
        page.click("#route-map")
        page.wait_for_selector("#start-walk", timeout=5000)
        check(weather_mark(page) == marks[mode] and pressable(page) == ["start-walk"], f"weather {mode}: on the final map the mark says {marks[mode]!r} and nothing new can be pressed ({weather_mark(page)!r}, {pressable(page)})")
        if mode == "danger":
            Shots(page, folder, "desktop-weather").take("final-map")
            page.click('#lang [data-lang="ko"]')
            check(weather_mark(page) == "14° · 비 올 가능성 높음", f"weather: the mark is Korean after the switch ({weather_mark(page)!r})")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="gilmate-shots-")
    os.makedirs(folder, exist_ok=True)
    server = serve()
    base = f"http://127.0.0.1:{server.server_address[1]}/index.html"
    sample = json.load(open(os.path.join(HERE, "shape-sample-4.json"), encoding="utf-8"))
    has_run = os.path.exists(os.path.join(FRONTEND, "data", "run.json"))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors = []

        def new_page(size, query):
            context = offline_context(browser, **SIZES[size])
            context.grant_permissions(["clipboard-read", "clipboard-write"])
            page = context.new_page()
            # A file the backend has not written yet is asked for and not found: that is said on the page, it is no error here.
            page.on("console", lambda m: errors.append(f"{size} {query}: {m.text}") if m.type == "error" and "404" not in m.text and "handoff" not in m.text else None)
            page.on("pageerror", lambda e: errors.append(f"{size} {query}: {e}"))
            page.goto(base + query)
            page.wait_for_selector(".dock")
            page.wait_for_timeout(400)
            return page

        print("1. desktop, sample 4")
        page = new_page("desktop", "?dev=4&pace=5")
        walk(page, Shots(page, folder, "desktop"), 4)
        print("2. desktop, sample 2: answers remembered")
        page = new_page("desktop", "?dev=2&pace=5")
        shots = Shots(page, folder, "desktop-remembered")
        check(page.query_selector("#start-button img") is not None and "Last runs" in text(page), "dev2: the landing card under Last runs shows the area's picture")
        walk(page, shots, 2, full=False)
        page = new_page("desktop", "?dev=4&pace=5")
        korean_typing(page, Shots(page, folder, "desktop-korean"))
        print("3. phone, sample 4")
        page = new_page("phone", "?dev=4&pace=5")
        walk(page, Shots(page, folder, "phone"), 4, full=False)
        if has_run:
            print("4. the saved real run")
            real = json.load(open(os.path.join(FRONTEND, "data", "run.json"), encoding="utf-8"))
            page = new_page("desktop", "?pace=30")
            shots = Shots(page, folder, "desktop-saved-run")
            check(page.inner_text(".bar").split("\n")[0].strip() == "gilmate" and "Recorded run" not in page.inner_text("body"), "saved run: nothing sits under the wordmark and no recorded-run line is shown")
            check(page.locator(".map-stop").count() == len(real["spatial_model"]["stops"]) and page.locator(".map-pill:visible").count() == 0 and page.locator(".map-place").count() == 0,
                  "saved run: the landing backdrop is the saved route, its stops as dots and no words")
            page.wait_for_function("() => !document.getElementById('weather').hidden", timeout=5000)
            mark = page.evaluate("() => { const m = document.getElementById('weather'); const r = m.getBoundingClientRect(); const l = document.getElementById('lang').getBoundingClientRect(); return [m.tagName, Boolean(m.closest('button') || m.querySelector('button')), r.right <= l.left, Boolean(m.querySelector('svg'))]; }")
            check(weather_mark(page) == "18° · Sunny" and mark == ["P", False, True, True], f"saved run: the top bar shows today's weather left of the language, with an icon, and it is not a button ({weather_mark(page)!r}, {mark})")
            cards = page.evaluate("() => [...document.querySelectorAll('.ready-row .ready-card')].map((card) => card.id)")
            check(cards == ["start-button", "start-hongdae"], f"saved run: two cards stand under Last runs ({cards})")
            shots.take("landing")
            page.click("#start-button")
            page.wait_for_selector(".making-head")
            shots.take("making-step")
            page.wait_for_selector("#place-yes", timeout=20000)
            shots.take("place")
            for place in real.get("candidates", []):
                if not page.query_selector("#place-yes"):
                    break
                page.click("#place-yes" if place["id"] in real["picks"] else "#place-no")
            if page.query_selector("#still-yes"):
                shots.take("still-true")
                page.click("#still-yes")
            page.wait_for_selector("#route-map", timeout=30000)
            nothing_over_the_map(page, "saved run route note")
            shots.take("route-note")
            page.click("#route-map")
            check(page.locator(".map-stop").count() == len(real["spatial_model"]["stops"]), "saved run: the final map shows the saved route's stops")
            drawn = int(page.get_attribute(".stage-map", "data-blocks") or 0)
            in_data = page.locator(".map-block-roof, .map-landmark-roof").count()
            check(0 < drawn < in_data / 2, f"saved run: only the buildings near the route are drawn ({drawn} of {in_data})")
            check(page.locator(".map-haze").count() == 1 and page.locator(".map-haze").is_visible(), "saved run: the far part of the final map fades into the ground")
            shots.take("final-map")
        print("4b. the dangers of the day, made up in sample 2")
        weather_walk(browser, base, folder, errors)
        print("5. the live path against a stand-in")
        page = offline_context(browser, **SIZES["desktop"]).new_page()
        page.on("pageerror", lambda e: errors.append(f"live: {e}"))
        stand_in(page, sample)          # the session is opened on load
        page.goto(f"{base}?api={STAND_IN}")
        page.wait_for_selector(".dock")
        page.wait_for_timeout(400)
        page.unroute(f"{STAND_IN}/**")
        live_walk(page, Shots(page, folder, "desktop-live"), sample)
        # No server answers at the address: the page shows the saved run instead of an error.
        page = offline_context(browser, **SIZES["desktop"]).new_page()
        page.route("http://no-agent.test/**", lambda route: route.abort())
        page.goto(f"{base}?api=http://no-agent.test&pace=30")
        page.wait_for_selector(".dock")
        page.wait_for_timeout(600)
        check(page.query_selector("#start-button:not(:disabled)") is not None if has_run else True, "no agent answers: the saved run is offered instead")
        browser.close()

    check(not errors, f"no error in the browser console ({errors[:5]})")
    print(f"\nScreenshots: {folder}")
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for what in failures:
            print("  - " + what)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
