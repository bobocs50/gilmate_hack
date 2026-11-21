"""Open the handoff card on the laptop page and walk the phone page once, in a real browser, with screenshots.

Free: no key, no model, no search. The only network asked is what the phone page itself asks for: the street
photos at their source. Run from the repo folder:

    python frontend/dev/walk-check.py [folder for the screenshots]

It needs Playwright, which is not a requirement of the project. Install it outside the repo, for example:

    uv venv /tmp/gilmate-pw && uv pip install --python /tmp/gilmate-pw/bin/python playwright
    /tmp/gilmate-pw/bin/python -m playwright install chromium
    /tmp/gilmate-pw/bin/python frontend/dev/walk-check.py /tmp/gilmate-shots

What it does, with the saved run (frontend/data/run.json):
  1. Desktop, 1440x900: opens the page, calls openHandoff with the saved run as a live page would hold it,
     looks at the card (QR code, link, "Copy link", close cross and nothing else to press), reads the QR code
     back with the browser's own detector when it has one, otherwise compares the link text, and closes the card.
  2. Phone, 390x844 with touch: opens the link the card made and goes through the walk: every stop with its
     photo, name, three facts and map strip (with the network cut after the first stop has loaded), "Next",
     the two answers after a walk (kept on the phone, not sent,
     because the link names no live agent), "Done", the route note in English and Korean, and Copy.
     Every name, distance and bench count on the screen is compared with the saved run.
  3. Phone, a link that names a live agent, against a STAND-IN and not against the agent: the browser's
     requests to http://stand-in.test are answered inside this script. "Too far" must be sent as the
     "feedback" turn of CONTRACT.md section 6.2 and said as saved; with the stand-in gone, "Fine" must be
     said as not sent. It does not show that the real agent saves the answer: only a paid run shows that.

The script fails (exit 1) on a failed check or on an error in the browser console.
"""
import functools
import http.server
import json
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.dirname(HERE)

failures = []


def check(what, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + what + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(what)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=FRONTEND))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def watch(page, errors):
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "Failed to load resource" not in message.text else None)


# Reads the card's QR code with the browser's own detector. Returns the text, or None when there is no detector.
READ_QR = """async () => {
  if (!("BarcodeDetector" in window)) return null;
  const drawn = document.querySelector(".handoff-code svg");
  const image = new Image();
  image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(drawn));
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1160;
  canvas.getContext("2d").drawImage(image, 0, 0, 1160, 1160);
  try {
    const found = await new BarcodeDetector({ formats: ["qr_code"] }).detect(canvas);
    return found.length ? found[0].rawValue : "";
  } catch { return null; }
}"""


def main():
    from playwright.sync_api import sync_playwright

    shots = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "walk-shots")
    os.makedirs(shots, exist_ok=True)
    with open(os.path.join(FRONTEND, "data", "run.json"), encoding="utf-8") as handle:
        run = json.load(handle)
    model = run["spatial_model"]
    stops = sorted(model["stops"], key=lambda stop: stop["order"])
    legs = {leg["from"]: leg for leg in model["legs"]}

    server = serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        # ---- 1. The card on the laptop page ----
        print("Desktop, 1440x900: the handoff card")
        desk = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        desk.grant_permissions(["clipboard-read", "clipboard-write"])
        page = desk.new_page()
        desk_errors = []
        watch(page, desk_errors)
        page.goto(base + "/index.html")
        page.wait_for_timeout(1500)
        made = page.evaluate("""async () => {
          const { openHandoff } = await import("./js/handoff.js");
          const run = await (await fetch("data/run.json")).json();
          const made = await openHandoff({ ...run, source: { kind: "recorded" }, lang: "en" });
          return { kind: made.kind, link: made.link };
        }""")
        link = made["link"]
        check("the card says the route is in the link", made["kind"] == "in_link", made["kind"])
        check("the link opens walk.html with the route after the #", bool(link) and "/walk.html#R1" in link, str(link)[:80])
        print(f"        the link is {len(link)} characters long")
        card = page.locator(".handoff")
        check("the card is on the page", card.is_visible())
        check("the card has a QR code", card.locator(".handoff-code svg").is_visible())
        check("the link is written out on the card", card.locator(".handoff-link").inner_text().strip() == link)
        check("the card has two things to press: Copy link and the close cross", card.locator("button").count() == 2)
        check("the card shows no credit line", "CC BY" not in card.inner_text() and "Mapillary" not in card.inner_text())
        box = card.bounding_box()
        check("the card is small (at most 320 px wide)", box["width"] <= 320, str(box))
        read = page.evaluate(READ_QR)
        if read is None:
            print("  note  this browser has no QR detector, so the QR code was not read back; the link text was compared instead")
        else:
            check("the QR code, read back by the browser's detector, is the link", read == link, f"{len(read)} characters read")
        card.locator(".handoff-copy").click()
        page.wait_for_timeout(200)
        check("Copy link says Copied", "Copied" in card.locator(".handoff-copy").inner_text())
        check("the clipboard holds the link", page.evaluate("navigator.clipboard.readText()") == link)
        page.screenshot(path=os.path.join(shots, "handoff-desktop.png"))
        card.screenshot(path=os.path.join(shots, "handoff-card.png"))
        card.locator(".handoff-close").click()
        check("the close cross takes the card away", page.locator(".handoff").count() == 0)
        desk.close()

        # ---- 2. The phone page, from that link ----
        print("Phone, 390x844: the walk from the link")
        phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, has_touch=True, is_mobile=True)
        page = phone.new_page()
        watch(page, errors)
        page.goto(link.replace(link.split("/walk.html")[0], base))
        page.wait_for_selector(".walk-name")
        check("the page says the route came from the link", "Route from the link" in page.locator(".walk-where").inner_text())
        # Once the page and its photos are loaded the network is cut: the rest of the walk must go on without it.
        page.wait_for_selector(".walk-photo[data-state='ok'] img", timeout=15000)
        page.wait_for_load_state("networkidle")
        phone.set_offline(True)
        print("        the network is cut from here to the end of the walk")

        for index, stop in enumerate(stops):
            last = index == len(stops) - 1
            page.wait_for_function("name => document.querySelector('.walk-name')?.textContent === name", arg=stop["name"])
            body = page.locator(".walk-screen").inner_text()
            check(f"stop {index + 1}: the name {stop['name']}", stop["name"] in body)
            check(f"stop {index + 1}: says stop {index + 1} of {len(stops)}", f"Stop {index + 1} of {len(stops)}" in body)
            try:
                page.wait_for_selector(".walk-photo[data-state='ok'] img", timeout=15000)
                shown = page.evaluate("document.querySelector('.walk-photo img').naturalWidth")
                check(f"stop {index + 1}: a photo is shown", shown > 0)
            except Exception:
                check(f"stop {index + 1}: a photo is shown", False, page.locator(".walk-photo").get_attribute("data-state") or "")
            check(f"stop {index + 1}: no credit line on the photo", page.locator(".walk-photo figcaption").count() == 0 and "CC BY" not in body)

            if index > 0:
                before = stops[index - 1]
                check(f"stop {index + 1}: asks how the walk from {before['name']} was", f"How was the walk here from {before['name']}?" in body)
                check(f"stop {index + 1}: the only things to press are Fine and Too far",
                      [button.inner_text() for button in page.locator(".walk button").all()] == ["Fine", "Too far"])
                if index == 1:
                    page.screenshot(path=os.path.join(shots, f"phone-stop-{index + 1}-asked.png"))
                page.locator("#walk-too-far" if index == 1 else "#walk-fine").tap()
                page.wait_for_selector("#walk-next")
                said = page.locator(".walk-ask").inner_text()
                check(f"stop {index + 1}: the answer is shown as kept on the phone, not sent",
                      ("too far" if index == 1 else "fine") in said and "Kept on this phone, not sent." in said, said)

            leg = legs.get(stop["id"])
            if leg:
                nxt = stops[index + 1]
                facts = [item.inner_text() for item in page.locator(".walk-facts li").all()]
                benches = sum(1 for bench in model["benches"] if bench["leg_id"] == leg["id"])
                bench_words = "No bench mapped" if benches == 0 else "1 bench mapped" if benches == 1 else f"{benches} benches mapped"
                check(f"stop {index + 1}: three facts about the walk", len(facts) == 3, str(facts))
                check(f"stop {index + 1}: {leg['distance_m']} m to {nxt['name']}", facts[:1] == [f"{round(leg['distance_m'])} m to {nxt['name']}"], str(facts))
                check(f"stop {index + 1}: the stairs as the map has them", facts[1:2] == ["No stairs mapped" if leg["stairs"] == "none_mapped" else "Stairs on the way" if leg["stairs"] == "some" else "Stairs unknown"], str(facts))
                check(f"stop {index + 1}: {bench_words}", facts[2:3] == [bench_words], str(facts))
                warned = [hazard["detail"]["en"] for hazard in model["hazards"] if hazard.get("leg_id") == leg["id"]]
                shown_warnings = [line.inner_text() for line in page.locator(".walk-leg .walk-warn").all()]
                check(f"stop {index + 1}: the walk's warning and no other", shown_warnings == list(dict.fromkeys(warned)), str(shown_warnings))
                check(f"stop {index + 1}: a map strip of the walk with the OpenStreetMap mark",
                      page.locator(".walk-strip .walk-strip-line").count() == 1 and "© OpenStreetMap" in (page.locator(".walk-strip").text_content() or ""))
            else:
                check("the last stop says so", "This is the last stop." in body)

            buttons = [button.inner_text() for button in page.locator(".walk button").all()]
            check(f"stop {index + 1}: one thing to press, {'Done' if last else 'Next'}", buttons == ["Done" if last else "Next"], str(buttons))
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(f"stop {index + 1}: nothing wider than the screen", overflow <= 0, str(overflow))
            page.wait_for_timeout(400)
            page.screenshot(path=os.path.join(shots, f"phone-stop-{index + 1}.png"))
            page.locator("#walk-next").tap()

        # ---- The route note ----
        page.wait_for_selector(".walk-note")
        note = page.locator(".walk-note-text").inner_text()
        english = [line for line in run["route_note"]["en"].split("\n") if line.strip()]
        check("the route note is the saved one, in English", [line for line in note.split("\n") if line.strip()] == english)
        check("the note screen has EN, KO and Copy to press and nothing else",
              [button.inner_text() for button in page.locator(".walk button").all()] == ["EN", "KO", "Copy"])
        check("it says how many answers were not sent", f"{len(stops) - 1} answers about the walks are kept on this phone and were not sent." in page.locator(".walk-screen").inner_text())
        page.screenshot(path=os.path.join(shots, "phone-note-en.png"), full_page=True)
        page.locator(".walk-lang[data-lang='ko']").tap()
        page.wait_for_function("document.documentElement.lang === 'ko'")
        korean = [line for line in run["route_note"]["ko"].split("\n") if line.strip()]
        check("KO shows the saved Korean note", [line for line in page.locator(".walk-note-text").inner_text().split("\n") if line.strip()] == korean)
        check("the page's own words are Korean too", "경로 메모" in page.locator(".walk-name").inner_text())
        page.locator("#walk-copy").tap()
        page.wait_for_timeout(300)
        copied = page.locator("#walk-copy").inner_text()
        check("Copy answers (copied, or says to select the text)", copied in ("복사됨", "복사하지 못했습니다. 글을 직접 선택해 주세요"), copied)
        page.screenshot(path=os.path.join(shots, "phone-note-ko.png"), full_page=True)

        # ---- The phone remembers where it was ----
        phone.set_offline(False)
        page.reload()
        page.wait_for_selector(".walk-note")
        check("after a reload the page is still at the route note", page.locator(".walk-note").is_visible())
        phone.close()

        # ---- 3. A link that names a live agent: the answers are sent (to a stand-in) ----
        print("Phone, 390x844: answers sent to a stand-in for the live agent")
        desk = browser.new_context(viewport={"width": 1440, "height": 900})
        page = desk.new_page()
        page.goto(base + "/index.html")
        live_link = page.evaluate("""async () => {
          const { openHandoff } = await import("./js/handoff.js");
          const run = await (await fetch("data/run.json")).json();
          const made = await openHandoff({ ...run, source: { kind: "live", api: "http://stand-in.test", root: "coordinator" }, sessionId: "s-check" });
          return made.link;
        }""")
        desk.close()
        check("a live page's link is made too", bool(live_link) and "/walk.html#R1" in live_link)
        phone = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page = phone.new_page()
        watch(page, errors)
        sent = []
        stand_in = {"up": True}
        cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"}

        def answer(route):
            request = route.request
            if not stand_in["up"]:
                route.abort()
            elif request.method == "OPTIONS":
                route.fulfill(status=204, headers=cors)
            elif request.url.endswith("/run_sse"):
                body = json.loads(request.post_data)
                sent.append((body["sessionId"], body["userId"], json.loads(body["newMessage"]["parts"][0]["text"])))
                event = {"author": "coordinator", "content": {"parts": [{"functionResponse": {"name": "record_feedback", "response": {"status": "recorded", "fact": None}}}]}}
                route.fulfill(status=200, headers={**cors, "Content-Type": "text/event-stream"}, body="data: " + json.dumps(event) + "\n\n")
            else:
                route.fulfill(status=200, headers={**cors, "Content-Type": "application/json"}, body=json.dumps({"state": run}))

        page.route("http://stand-in.test/**", answer)
        page.goto(live_link)
        page.wait_for_selector("#walk-next")
        page.locator("#walk-next").tap()
        page.locator("#walk-too-far").tap()
        page.wait_for_selector("#walk-next")
        first_leg = legs[stops[0]["id"]]["id"]
        check("Too far is sent as the feedback turn of that walk, in the link's session",
              sent == [("s-check", "traveller", {"step": "feedback", "leg_id": first_leg, "verdict": "too_far"})], str(sent))
        said = page.locator(".walk-ask").inner_text()
        check("and is said as saved by the guide", "You said: too far." in said and "Saved by your guide." in said, said)
        page.screenshot(path=os.path.join(shots, "phone-answer-sent.png"))
        stand_in["up"] = False
        page.locator("#walk-next").tap()
        page.locator("#walk-fine").tap()
        page.wait_for_selector("#walk-next")
        said = page.locator(".walk-ask").inner_text()
        check("with the agent out of reach the answer is said as kept on the phone, not sent",
              "The guide could not be reached. Kept on this phone, not sent." in said, said)
        phone.close()
        browser.close()

    server.shutdown()
    for error in errors:
        print("  FAIL  error in the phone page's console: " + error)
    if desk_errors:
        print(f"  note  the laptop page itself logged {len(desk_errors)} console error(s); they are the page's own, not the card's:")
        for error in desk_errors[:3]:
            print("        " + error[:200])
    print(f"Screenshots: {shots}")
    if failures or errors:
        print(f"{len(failures) + len(errors)} problem(s).")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
