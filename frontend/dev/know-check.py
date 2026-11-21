"""The knowledge graph in a real browser: drag, pan, zoom, the card, forgetting, an empty memory, Korean.

Free: nothing leaves this machine, no key, no model, no search. It opens frontend/dev/know-lab.html, which shows
the graph alone on the development samples (?dev=1 to ?dev=4). "Forget this" is simulated by that page: the fact
is taken out of the sample in the tab. Whether the agent forgets is shown only by a run against the agent.

    python frontend/dev/know-check.py [folder for the screenshots]

It needs Playwright, which is not a requirement of the project. Install it outside the repo, for example:

    uv venv /tmp/gilmate-pw && uv pip install -p /tmp/gilmate-pw playwright && /tmp/gilmate-pw/bin/playwright install chromium

The script fails (exit 1) on a failed check or on any error in the browser console.
"""
import functools
import http.server
import os
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED = []
SETTLED = ".know-graph[data-settled]:not([data-arrive]) .know-node"      # at rest, and the first fade is over


def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        FAILED.append(what)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def node(page, selector):
    """Where a dot is: on the screen (the middle of its dot) and in the graph's own measure, with its line's end."""
    return page.evaluate("""(selector) => {
        const button = document.querySelector(selector);
        const dot = button.querySelector('.know-dot').getBoundingClientRect();
        const index = [...button.parentNode.querySelectorAll('.know-node')].indexOf(button);
        const line = document.querySelectorAll('.know-line')[index - 1];        // the guide, first, has no line
        return { id: button.dataset.node, sx: dot.left + dot.width / 2, sy: dot.top + dot.height / 2,
                 x: +button.dataset.x, y: +button.dataset.y, lx: +line.getAttribute('x2'), ly: +line.getAttribute('y2') };
    }""", selector)


def fact(page, n):
    """A selector for the n-th fact dot that plain document.querySelector understands."""
    return f'.know-node[data-node="{page.locator('.know-node[data-kind="fact"]').nth(n).get_attribute("data-node")}"]'


def settle(page):
    page.wait_for_selector(SETTLED)
    page.wait_for_timeout(120)
    page.wait_for_selector(SETTLED)


def labels_apart(page):
    return page.evaluate("""() => {
        const boxes = [...document.querySelectorAll('.know-node')].flatMap((b) => [b.querySelector('.know-dot'), b.querySelector('.know-label')]
            .map((part) => ({ id: b.dataset.node, r: part.getBoundingClientRect() })));
        const hits = [];
        for (let i = 0; i < boxes.length; i += 1) for (let j = i + 1; j < boxes.length; j += 1) {
            const a = boxes[i], b = boxes[j];
            if (a.id === b.id) continue;
            if (Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left) > 1 && Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top) > 1) hits.push(a.id + '/' + b.id);
        }
        return hits;
    }""")


def view(page):
    return page.evaluate("() => { const g = document.querySelector('.know-graph'); return { k: +g.dataset.zoom, shift: g.dataset.shift.split(',').map(Number) }; }")


def desktop(browser, base, folder, watch):
    print("desktop 1440x900")
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    watch(page)
    page.goto(f"{base}/dev/know-lab.html?dev=1")
    settle(page)
    facts = page.locator('.know-node[data-kind="fact"]').count()
    check(facts == 9 and page.locator('.know-node[data-kind="source"]').count() == 3 and page.locator('.know-node[data-kind="guide"]').count() == 1,
          f"the guide, three sources and one dot per fact ({facts})")
    check(labels_apart(page) == [], f"the tidy ring: no name lies on another ({labels_apart(page)})")
    check(page.locator('.know-line[data-kind="learned"]').count() == 1 and "learned, kept" in page.inner_text('.know-node[data-learned]'),
          "the kept learned fact has its own line and says 'learned, kept' in words")
    page.screenshot(path=os.path.join(folder, "desktop-1-ring.png"))

    # drag a dot 120 px: it stays where it was put and its line's end follows
    selector = fact(page, 2)
    before = node(page, selector)
    page.mouse.move(before["sx"], before["sy"])
    page.mouse.down()
    page.mouse.move(before["sx"] + 60, before["sy"] - 20, steps=6)
    page.mouse.move(before["sx"] + 120, before["sy"], steps=6)
    mid = node(page, selector)
    check(abs(mid["sx"] - before["sx"] - 120) < 1.5 and abs(mid["lx"] - mid["x"]) < 0.2 and abs(mid["ly"] - mid["y"]) < 0.2,
          "while dragged the dot is under the pointer and its line ends at the dot")
    page.wait_for_timeout(150)
    page.mouse.up()
    settle(page)
    after = node(page, selector)
    check(abs(after["sx"] - before["sx"] - 120) < 1.5 and abs(after["sy"] - before["sy"]) < 1.5, f"dragged 120 px, it stays there ({after['sx'] - before['sx']:.1f}, {after['sy'] - before['sy']:.1f})")
    check(abs(after["lx"] - after["x"]) < 0.2 and abs(after["ly"] - after["y"]) < 0.2, "its line's end is at the dot after the drag")
    check(page.locator(".know-card:not([data-idle])").count() == 0, "the end of a drag does not open the card")

    # a dot dropped on another one: the other one gives way, names stay apart
    other = node(page, fact(page, 3))
    page.mouse.move(after["sx"], after["sy"])
    page.mouse.down()
    page.mouse.move(other["sx"], other["sy"] + 4, steps=8)
    page.wait_for_timeout(150)
    page.mouse.up()
    settle(page)
    check(labels_apart(page) == [], f"a dot dropped onto another: no name lies on another ({labels_apart(page)})")
    dropped = node(page, selector)
    check(abs(dropped["sx"] - other["sx"]) < 1.5 and abs(dropped["sy"] - other["sy"] - 4) < 1.5, "the dropped dot stays, the other one gives way")
    page.screenshot(path=os.path.join(folder, "desktop-2-dragged.png"))

    # pan and zoom
    start = view(page)
    box = page.locator(".know-map").bounding_box()
    page.mouse.move(box["x"] + 80, box["y"] + box["height"] - 200)
    page.mouse.down()
    page.mouse.move(box["x"] + 180, box["y"] + box["height"] - 150, steps=5)
    page.mouse.up()
    panned = view(page)
    check(abs(panned["shift"][0] - start["shift"][0] - 100) < 1 and abs(panned["shift"][1] - start["shift"][1] - 50) < 1, "the ground pans with the pointer")
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -240)
    check(view(page)["k"] > panned["k"] * 1.3, f"the wheel zooms in ({view(page)['k']})")
    page.click('.know-control[data-do="minus"]')
    settle(page)
    wheel_k = view(page)["k"]
    page.click('.know-control[data-do="plus"]')
    settle(page)
    check(view(page)["k"] > wheel_k * 1.2, "the + and - buttons zoom")
    moved = node(page, selector)
    check(abs(moved["x"] - dropped["x"]) < 0.2 and abs(moved["y"] - dropped["y"]) < 0.2, "panning and zooming leave the dots where they were put")
    page.click('.know-control[data-do="frame"]')
    settle(page)
    check(abs(view(page)["k"] - start["k"]) < 0.01 and labels_apart(page) == [], "the third button puts every dot back in the tidy ring")

    # the card
    limit = page.locator('.know-node[data-learned]')
    limit.click()
    page.wait_for_selector(".know-card:not([data-idle])")
    page.wait_for_timeout(250)
    card = page.inner_text(".know-card")
    check(all(words in card for words in ["What I know", "Where it comes from", "What it changes", "Forget this", "Learned · kept", "Saved at"]),
          "the card says what it knows, where from and when, what it changes, and offers 'Forget this'")
    card_box = page.locator(".know-card").bounding_box()
    dot = node(page, ".know-node[data-learned]")
    check(not (card_box["x"] <= dot["sx"] <= card_box["x"] + card_box["width"] and card_box["y"] <= dot["sy"] <= card_box["y"] + card_box["height"]),
          "the card opens beside its dot, not on it")
    check(card_box["width"] <= 300 and page.locator(".know-card #forget").bounding_box()["height"] <= 30, "the card and its button are small")
    page.screenshot(path=os.path.join(folder, "desktop-3-card.png"))
    page.click("#forget")
    check("Keep it" in page.inner_text(".know-card") and "Yes, forget" in page.inner_text(".know-card"), "'Forget this' asks once")
    page.screenshot(path=os.path.join(folder, "desktop-4-ask.png"))
    page.click("#forget-yes")
    settle(page)
    check(page.locator('.know-node[data-kind="fact"]').count() == facts - 1 and page.locator(".know-node[data-learned]").count() == 0,
          "forgotten (simulated in the sample): the dot and its line are gone")
    check(page.locator(".know-card:not([data-idle])").count() == 0 and "8 things remembered" in page.inner_text(".know-top"), "the card is closed and the count says 8")
    page.screenshot(path=os.path.join(folder, "desktop-5-forgotten.png"))

    # what the tools answered: a second, refused call in the same turn does not undo a saved tap
    said = page.evaluate("""async () => {
        const m = await import('../js/memory.js');
        const ok = { name: 'record_feedback', response: { status: 'recorded', fact: { id: 'f9' } } };
        const no = { name: 'record_feedback', response: { status: 'denied', rule: 'max_calls' } };
        const gone = { name: 'forget_fact', response: { status: 'forgotten' } };
        const twice = { name: 'forget_fact', response: { status: 'not_found' } };
        return [m.feedbackOutcome([ok, no]).kind, m.feedbackOutcome([no]).kind, m.feedbackOutcome([]).kind,
                m.forgetOutcome([gone, twice], true).kind, m.forgetOutcome([twice], false).kind];
    }""")
    check(said == ["recorded", "refused", "refused", "done", "refused"], f"a saved tap stays saved when the tool is called again and refused in the same turn ({said})")

    # still learning, an empty memory, Korean
    page.goto(f"{base}/dev/know-lab.html?dev=2")
    settle(page)
    check(page.locator('.know-line[data-kind="candidate"]').count() == 1 and "still learning" in page.inner_text('.know-node[data-status="candidate"]'),
          "a candidate has a dashed line and says 'still learning' in words")
    page.screenshot(path=os.path.join(folder, "desktop-6-still-learning.png"))
    page.goto(f"{base}/dev/know-lab.html?dev=4")
    settle(page)
    check(page.locator('.know-node').count() == 1 and page.locator('.know-node[data-kind="guide"]').count() == 1
          and page.inner_text(".know-sum").strip() == "Nothing yet. What you decide appears here." and not page.locator(".know-key").is_visible(),
          "an empty memory: only the guide and one line, 'Nothing yet. What you decide appears here.'")
    page.screenshot(path=os.path.join(folder, "desktop-7-empty.png"))
    page.goto(f"{base}/dev/know-lab.html?dev=2&lang=ko")
    settle(page)
    check("내 답변" in page.inner_text(".know-map") and "기억하는 것 9가지" in page.inner_text(".know-top") and labels_apart(page) == [], "Korean: names and words are Korean, no name lies on another")
    page.click('.know-node[data-status="candidate"]')
    page.wait_for_selector(".know-card:not([data-idle])")
    page.wait_for_timeout(250)
    card = page.inner_text(".know-card")
    check("어디서 알게 되었는지" in card and "이것을 잊어 주세요" in card and "샘플 문장" in card, "Korean: the card's labels are Korean and an {en, ko} memory sentence is shown in Korean")
    page.screenshot(path=os.path.join(folder, "desktop-8-korean.png"))
    page.close()


def touch_drag(cdp, x0, y0, x1, y1, steps=8):
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
    for i in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def phone(browser, base, folder, watch):
    print("phone 390x844, with a finger")
    context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, has_touch=True, is_mobile=True)
    page = context.new_page()
    watch(page)
    page.goto(f"{base}/dev/know-lab.html?dev=1")
    settle(page)
    check(labels_apart(page) == [], f"the tidy ring on a phone: no name lies on another ({labels_apart(page)})")
    check(page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"), "nothing reaches beyond the screen")
    page.screenshot(path=os.path.join(folder, "phone-1-ring.png"))
    cdp = context.new_cdp_session(page)
    selector = fact(page, 0)
    before = node(page, selector)
    touch_drag(cdp, before["sx"], before["sy"], before["sx"] + 60, before["sy"] - 90)
    settle(page)
    after = node(page, selector)
    check(abs(after["sx"] - before["sx"] - 60) < 2 and abs(after["sy"] - before["sy"] + 90) < 2 and abs(after["lx"] - after["x"]) < 0.2,
          f"a finger drags a dot, it stays and its line follows ({after['sx'] - before['sx']:.1f}, {after['sy'] - before['sy']:.1f})")
    # pinch out on the ground
    box = page.locator(".know-map").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + 40
    k = view(page)["k"]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx - 20, "y": cy, "id": 1}, {"x": cx + 20, "y": cy, "id": 2}]})
    for spread in (30, 40, 50, 60):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx - spread, "y": cy, "id": 1}, {"x": cx + spread, "y": cy, "id": 2}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    check(view(page)["k"] > k * 1.5, f"two fingers zoom ({k:.2f} to {view(page)['k']:.2f})")
    page.tap('.know-control[data-do="frame"]')
    settle(page)
    page.tap(".know-node[data-learned]")
    page.wait_for_selector(".know-card:not([data-idle])")
    settle(page)
    page.wait_for_timeout(250)
    card_box = page.locator(".know-card").bounding_box()
    dot = node(page, ".know-node[data-learned]")
    check(dot["sy"] < card_box["y"] and "Forget this" in page.inner_text(".know-card"), "a tap opens the card at the bottom and the dot stays in view above it")
    page.screenshot(path=os.path.join(folder, "phone-2-card.png"))
    context.close()


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="gilmate-know-")
    os.makedirs(folder, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=FRONTEND))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    errors = []

    def watch(page):
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(str(error)))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        desktop(browser, base, folder, watch)
        phone(browser, base, folder, watch)
        browser.close()
    check(not errors, f"no error in the browser console ({errors[:3]})")
    print(f"screenshots: {folder}")
    if FAILED:
        print(f"{len(FAILED)} check(s) failed")
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
