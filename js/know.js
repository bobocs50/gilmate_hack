// The knowledge graph (CONTRACT.md section 6.3): what Gilmate remembers about her, drawn only from "user:memory".
// The guide sits in the middle, the sources stand around it and every remembered fact is a small dot behind its
// source with its name under it. It starts as a tidy ring. Every dot can be dragged with mouse or finger and stays
// where it was put, its lines following; the ground pans and zooms (wheel, pinch, the small + / - buttons).
// Pressing a dot opens a small card beside it. A fact that is not in the memory is simply not drawn.
//
// Pieces: know/layout.js (the ring, the spring, keeping names apart), know/card.js (the card's words),
// know/words.js (Korean). Only transform and opacity move; with "reduce motion" everything is placed at once.

import { el, svg, clear } from "./dom.js";
import { t, setKnowLang } from "./know/words.js";
import { groupFacts, factName, factState, isLearned } from "./memory.js";
import { ringLayout, separate, springStep, fitView, clamp } from "./know/layout.js";
import { cardFor, GUIDE } from "./know/card.js";

const ZOOM = [0.4, 2.5];
const ZOOM_STEP = 1.35;
const DOT_TILE = 18;         // px between the grey dots of the ground at zoom 1
const NARROW = 600;          // px of ground width below which the card sits at the bottom
const RADIUS = { guide: 15, source: 6, fact: 5 };

/**
 * createKnow(host, panelHost, act) -> { render(view) }
 * host:      the element the graph fills. It needs a height; the graph asks for at least 420 px.
 * panelHost: the element the card is put into, or null: then the graph keeps the card inside itself.
 * view: { memory, memoryNote, today, lang, source, model, selected, confirm, busy, message, canForget, forgetOff }
 * act:  { select(id|null), askForget(factId|null), forget(factId) }
 */
export function createKnow(host, panelHost, act) {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)");
  const at = { k: 1, tx: 0, ty: 0 };       // the ground's zoom and shift: screen = world * k + t
  const nodes = new Map();                 // id -> { id, kind, name, parent, x, y, vx, vy, tx, ty, w, h, r, user, button, ... }
  let groups = [];                         // [{ id, facts: [id] }] for the ring
  let view = null;
  let laid = false;                        // the first tidy ring has been made
  let touched = false;                     // she moved a dot, or panned or zoomed
  let frame = 0;
  let last = 0;
  let tween = null;                        // a short glide of the ground: { from, to, start, ms }
  let drag = null;                         // the dot under her finger
  let gesture = null;                      // panning or pinching the ground
  const pointers = new Map();
  let swallowClickUntil = 0;
  let shown = null;                        // the id the card shows
  let cardBox = { w: 0, h: 0, x: 0, y: 0 };
  let tileNow = 0;

  const lines = svg("svg", { class: "know-lines", "aria-hidden": "true" });
  const world = el("div", { class: "know-world" }, lines);
  const dots = el("div", { class: "know-dots", "aria-hidden": "true" });
  const ground = el("div", { class: "know-map", role: "group" }, dots, world);
  const top = el("div", { class: "know-top" });
  const key = el("ul", { class: "know-key" });
  const zoomIn = control("plus", () => zoomBy(ZOOM_STEP));
  const zoomOut = control("minus", () => zoomBy(1 / ZOOM_STEP));
  const tidy = control("frame", () => tidyUp());
  const zoom = el("div", { class: "know-zoom", role: "group" }, zoomIn, zoomOut, tidy);
  const ownLayer = panelHost ? null : el("div", { class: "know-side" });
  const layer = panelHost ?? ownLayer;
  const cardIn = el("div", { class: "know-card-in" });
  const card = el("aside", { class: "know-panel know-card", "data-tone": "dark", "data-idle": true, tabindex: "-1" }, cardIn);
  card.inert = true;
  const root = el("div", { class: "know-graph", "data-settled": "true" }, ground, top, key, zoom, ownLayer);

  new ResizeObserver(() => resized()).observe(ground);
  ground.addEventListener("pointerdown", groundDown);
  ground.addEventListener("pointermove", groundMove);
  ground.addEventListener("pointerup", (event) => groundUp(event, false));
  ground.addEventListener("pointercancel", (event) => groundUp(event, true));
  ground.addEventListener("wheel", wheel, { passive: false });
  const onEscape = (event) => {
    if (event.key !== "Escape" || !view?.selected) return;
    event.preventDefault();
    event.stopPropagation();
    act.select(null);
  };
  root.addEventListener("keydown", onEscape);
  card.addEventListener("keydown", onEscape);

  // ---- drawing from the memory ------------------------------------------------------------------

  function render(given) {
    view = { ...given, act };
    setKnowLang(view.lang);
    if (root.parentNode !== host) host.replaceChildren(root);
    if (card.parentNode !== layer) layer.replaceChildren(card);
    ground.setAttribute("aria-label", t("Map of what Gilmate knows"));
    reconcile(modelOf(view));
    drawTop();
    drawCard();
    markNear();
    arrange();
  }

  // Everything that is drawn, in reading order: the guide, then each source followed by its facts.
  function modelOf({ memory, today }) {
    const list = [{ id: GUIDE, kind: "guide", name: "Gilmate", parent: null }];
    groups = [];
    if (!memory) return list;
    for (const { group, facts } of groupFacts(memory)) {
      if (!facts.length) continue;                         // a source stands there from its first fact on
      groups.push({ id: group.id, facts: facts.map((fact) => String(fact.id)) });
      list.push({ id: group.id, kind: "source", name: t(group.name), state: facts.length ? "" : t("nothing yet"), empty: !facts.length, parent: GUIDE, line: "source" });
      for (const fact of facts) {
        const learned = isLearned(fact);
        list.push({
          id: String(fact.id), kind: "fact", name: factName(fact), state: factState(memory, fact, today).short,
          learned, status: fact.status, parent: group.id,
          line: fact.status === "candidate" ? "candidate" : learned && fact.status === "kept" ? "learned" : "fact",
        });
      }
    }
    return list;
  }

  // Dots that are still in the memory keep their element and their place; new ones are made, gone ones removed.
  function reconcile(model) {
    const seen = new Set();
    model.forEach((item, index) => {
      let node = nodes.get(item.id);
      if (!node) {
        node = makeNode(item, index);
        nodes.set(item.id, node);
      }
      Object.assign(node, { state: "", empty: false, learned: false, status: null, line: null }, item);
      paint(node);
      const here = world.children[index + 1] ?? null;      // the first child is the drawing of the lines
      if (here !== node.button) world.insertBefore(node.button, here);
      seen.add(item.id);
    });
    for (const [id, node] of nodes) {
      if (seen.has(id)) continue;
      node.button.remove();
      node.stroke?.remove();
      nodes.delete(id);
    }
  }

  function makeNode(item, index) {
    const dot = el("span", { class: "know-dot", "aria-hidden": "true" }, item.kind === "guide" ? el("span", { class: "know-face" }) : null);
    const nameWords = el("span", { class: "know-name" });
    const stateWords = el("span", { class: "know-state" });
    const label = el("span", { class: "know-label" }, nameWords, stateWords);
    const button = el("button", { type: "button", class: "know-node", "data-node": item.id, style: `--i:${index}` }, dot, label);
    const stroke = item.parent ? svg("line", { class: "know-line", style: `--i:${index}` }) : null;
    if (stroke) lines.append(stroke);
    const node = { id: item.id, x: 0, y: 0, vx: 0, vy: 0, tx: 0, ty: 0, w: 0, h: 0, r: 5, user: false, placed: false, button, label, nameWords, stateWords, stroke };
    button.addEventListener("click", (event) => {
      if (performance.now() < swallowClickUntil) {       // the end of a drag is not a press
        swallowClickUntil = 0;
        event.preventDefault();
        return;
      }
      act.select(view.selected === node.id ? null : node.id);
    });
    button.addEventListener("pointerdown", (event) => nodeDown(event, node));
    button.addEventListener("pointermove", nodeMove);
    button.addEventListener("pointerup", (event) => nodeUp(event, false));
    button.addEventListener("pointercancel", (event) => nodeUp(event, true));
    button.addEventListener("keydown", (event) => nodeKey(event, node));
    return node;
  }

  function paint(node) {
    const { button } = node;
    flag(button, "data-kind", node.kind);
    flag(button, "data-learned", node.learned);
    flag(button, "data-status", node.status);
    flag(button, "data-empty", node.empty);
    button.setAttribute("aria-pressed", view.selected === node.id ? "true" : "false");
    if (node.nameWords.textContent !== node.name) node.nameWords.textContent = node.name;
    if (node.stateWords.textContent !== (node.state || "")) node.stateWords.textContent = node.state || "";
    node.stateWords.hidden = !node.state;
    node.r = RADIUS[node.kind] ?? 5;
    if (node.stroke) flag(node.stroke, "data-kind", node.line);
  }

  // The pressed dot, its source and its facts stay clear; the rest steps back a little.
  function markNear() {
    const selected = view.selected && nodes.has(view.selected) ? nodes.get(view.selected) : null;
    flag(root, "data-focus", Boolean(selected));
    for (const node of nodes.values()) {
      const near = selected && (node === selected || node.parent === selected.id || selected.parent === node.id);
      flag(node.button, "data-near", Boolean(near));
      if (node.stroke) flag(node.stroke, "data-near", Boolean(selected && (node === selected || node.parent === selected.id)));
    }
  }

  function drawTop() {
    const { memory } = view;
    const count = memory ? memory.facts.length : 0;
    flag(root, "data-empty", count === 0);                  // nothing yet: only the guide and one quiet line
    const sum = !memory ? el("p", { class: "know-sum" }, view.memoryNote || t("Nothing is known about what Gilmate remembers."))
      : count === 0 ? el("p", { class: "know-sum know-none" }, t("Nothing yet. What you decide appears here."))
      : el("p", { class: "know-sum" },
          el("b", {}, count === 1 ? t("1 thing remembered") : t("{count} things remembered", { count })),
          el("span", {}, t("Only from your own answers, picks and taps.")));
    clear(top).append(...[
      view.source?.kind === "dev" ? el("p", { class: "know-tag", title: t("Development sample. This memory was written for layout work, it is not about a real person.") }, t("Development sample")) : null,
      sum,
      count ? el("p", { class: "know-hint" }, t("Drag a dot to move it, press it to read it.")) : null,
      view.message ? el("p", { class: "know-message", role: "status", "data-kind": view.message.kind }, view.message.text) : null,
    ].filter(Boolean));
    key.setAttribute("aria-label", t("What the map shows"));
    clear(key).append(
      el("li", {}, el("i", { "data-kind": "fact" }), t("answered or picked")),
      el("li", {}, el("i", { "data-kind": "learned" }), t("learned, kept")),
      el("li", {}, el("i", { "data-kind": "candidate" }), t("still learning")));
    zoom.setAttribute("aria-label", t("Knowledge graph"));
    for (const [button, words] of [[zoomIn, t("Zoom in")], [zoomOut, t("Zoom out")], [tidy, t("Put every dot back in its place")]]) {
      button.setAttribute("aria-label", words);
      button.title = words;
    }
  }

  // ---- places ------------------------------------------------------------------------------------

  // Gives every new dot its place, keeps names apart and lets everything come to rest.
  // tidy: every dot goes back to the ring. dropped: the dot she has just let go of, which does not give way.
  function arrange({ tidy = false, dropped = null, sudden = false } = {}) {
    const width = ground.clientWidth;
    const height = ground.clientHeight;
    if (!width || !height) return;                         // not on screen yet; the size observer calls again
    flag(root, "data-narrow", width < NARROW);
    const all = [...nodes.values()];
    for (const node of all) {
      node.w = node.label.offsetWidth;
      node.h = node.label.offsetHeight;
    }
    const fresh = all.filter((node) => !node.placed);
    const first = !laid;
    if (tidy || fresh.length) {
      const spots = ringLayout(groups, { width, height });
      spots.set(GUIDE, [0, 0]);
      // With a new dot the ring is another one: every dot she has not moved herself takes its new place.
      for (const node of tidy ? all : all.filter((one) => !one.placed || !one.user)) {
        [node.tx, node.ty] = spots.get(node.id) ?? [0, 0];
        if (tidy) node.user = false;
      }
    }
    for (const node of all) node.fixed = dropped ? node === dropped : node.user;
    separate(all);
    for (const node of fresh) {
      // A new dot comes out from its source; at the very start the whole ring opens a little.
      const from = first ? [node.tx * 0.86, node.ty * 0.86] : (() => { const parent = nodes.get(node.parent); return parent ? [parent.x, parent.y] : [node.tx, node.ty]; })();
      [node.x, node.y] = from;
      node.placed = true;
      if (!first) appear(node);
    }
    if (first) {
      Object.assign(at, fitView(all, { width, height }, padding(width)));
      laid = true;
      root.setAttribute("data-arrive", "");
      window.setTimeout(() => root.removeAttribute("data-arrive"), 900);
    } else if (!touched && (tidy || fresh.length)) {
      glide(fitView(all, { width, height }, padding(width)), sudden ? 0 : 260);
    }
    if (still.matches || sudden) for (const node of all) Object.assign(node, { x: node.tx, y: node.ty, vx: 0, vy: 0 });
    measureCard();
    reveal();
    draw();
    run();
  }

  // A dot that was added after the first ring fades in while the spring lets it settle.
  function appear(node) {
    for (const part of [node.button, node.stroke]) {
      if (!part) continue;
      part.setAttribute("data-new", "");
      window.setTimeout(() => part.removeAttribute("data-new"), 700);
    }
  }

  // Room for the words at the top and the key at the bottom.
  function padding(width) {
    return width < NARROW ? [78, 8, 84, 8] : [64, 28, 56, 28];
  }

  function resized() {
    if (!view) return;
    if (!laid || !touched) arrange({ tidy: laid, sudden: true });
    else { measureCard(); draw(); }
  }

  function tidyUp() {
    touched = false;
    arrange({ tidy: true });
  }

  // ---- movement ------------------------------------------------------------------------------------

  function run() {
    if (frame) return;
    last = performance.now();
    root.removeAttribute("data-settled");
    frame = requestAnimationFrame(tick);
  }

  function tick(now) {
    frame = 0;
    const dt = clamp((now - last) / 1000, 0.001, 0.034);
    last = now;
    let moving = false;
    for (const node of nodes.values()) {
      if (drag?.node === node && drag.moved) continue;
      const a = springStep(node, dt / 2);
      const b = springStep(node, dt / 2);
      if (a || b) moving = true;
    }
    if (tween) {
      const p = tween.ms ? clamp((now - tween.start) / tween.ms, 0, 1) : 1;
      const eased = 1 - (1 - p) ** 3;
      for (const name of ["k", "tx", "ty"]) at[name] = tween.from[name] + (tween.to[name] - tween.from[name]) * eased;
      if (p >= 1) tween = null;
      else moving = true;
    }
    draw();
    if (moving) frame = requestAnimationFrame(tick);
    else root.setAttribute("data-settled", "true");
  }

  function glide(to, ms = 200) {
    if (still.matches || !ms) {
      tween = null;
      Object.assign(at, to);
      draw();
      return;
    }
    tween = { from: { ...at }, to, start: performance.now(), ms };
    run();
  }

  function draw() {
    world.style.transform = `translate(${at.tx.toFixed(2)}px, ${at.ty.toFixed(2)}px) scale(${at.k.toFixed(4)})`;
    let tile = DOT_TILE * at.k;
    while (tile < 11) tile *= 2;
    if (Math.abs(tile - tileNow) > 0.01) {
      tileNow = tile;
      dots.style.backgroundSize = `${tile.toFixed(2)}px ${tile.toFixed(2)}px`;
    }
    dots.style.transform = `translate(${(((at.tx % tile) + tile) % tile).toFixed(2)}px, ${(((at.ty % tile) + tile) % tile).toFixed(2)}px)`;
    for (const node of nodes.values()) {
      node.button.style.transform = `translate(${node.x.toFixed(2)}px, ${node.y.toFixed(2)}px)`;
      node.button.dataset.x = node.x.toFixed(1);
      node.button.dataset.y = node.y.toFixed(1);
      if (!node.stroke) continue;
      const parent = nodes.get(node.parent);
      if (!parent) continue;
      node.stroke.setAttribute("x1", parent.x.toFixed(1));
      node.stroke.setAttribute("y1", parent.y.toFixed(1));
      node.stroke.setAttribute("x2", node.x.toFixed(1));
      node.stroke.setAttribute("y2", node.y.toFixed(1));
    }
    root.dataset.zoom = at.k.toFixed(3);
    root.dataset.shift = `${at.tx.toFixed(1)},${at.ty.toFixed(1)}`;
    placeCard();
  }

  // ---- a dot under the hand ------------------------------------------------------------------------

  function nodeDown(event, node) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if (drag || gesture) return;                                  // one finger at a time
    drag = { node, id: event.pointerId, sx: event.clientX, sy: event.clientY, ox: node.x, oy: node.y, moved: false, px: event.clientX, py: event.clientY, pt: event.timeStamp, vx: 0, vy: 0 };
    node.button.setPointerCapture(event.pointerId);
  }

  function nodeMove(event) {
    if (!drag || event.pointerId !== drag.id) return;
    const { node } = drag;
    const dx = event.clientX - drag.sx;
    const dy = event.clientY - drag.sy;
    if (!drag.moved) {
      if (Math.hypot(dx, dy) < (event.pointerType === "mouse" ? 4 : 8)) return;
      drag.moved = true;
      tween = null;
      node.button.setAttribute("data-dragging", "");
      root.setAttribute("data-dragging", "");
    }
    const dt = Math.max(1, event.timeStamp - drag.pt) / 1000;
    drag.vx = 0.6 * drag.vx + 0.4 * ((event.clientX - drag.px) / at.k / dt);
    drag.vy = 0.6 * drag.vy + 0.4 * ((event.clientY - drag.py) / at.k / dt);
    drag.px = event.clientX;
    drag.py = event.clientY;
    drag.pt = event.timeStamp;
    node.x = node.tx = drag.ox + dx / at.k;
    node.y = node.ty = drag.oy + dy / at.k;
    node.vx = 0;
    node.vy = 0;
    draw();
  }

  function nodeUp(event, cancelled) {
    if (!drag || event.pointerId !== drag.id) return;
    const { node, moved } = drag;
    const quiet = event.timeStamp - drag.pt > 90;                 // she held it still before letting go
    const speed = quiet || cancelled ? [0, 0] : [drag.vx, drag.vy];
    drag = null;
    node.button.removeAttribute("data-dragging");
    root.removeAttribute("data-dragging");
    if (!moved) return;                                           // a press: the click that follows opens the card
    swallowClickUntil = performance.now() + 400;
    node.user = true;
    touched = true;
    // It stays where she let go. A light spring: it runs on a little with the hand's speed and comes back.
    node.vx = clamp(speed[0], -1400, 1400) * 0.5;
    node.vy = clamp(speed[1], -1400, 1400) * 0.5;
    arrange({ dropped: node });
  }

  // With the keyboard: the arrow keys move the dot that has the focus.
  function nodeKey(event, node) {
    const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
    if (!step) return;
    event.preventDefault();
    const far = event.shiftKey ? 48 : 12;
    node.tx += step[0] * far;
    node.ty += step[1] * far;
    node.user = true;
    touched = true;
    arrange({ dropped: node, sudden: true });
  }

  // ---- the ground under the hand: panning, pinching, the wheel ---------------------------------------------

  function groundDown(event) {
    if (event.target.closest(".know-node")) return;
    if (drag || pointers.size >= 2) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    ground.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    tween = null;
    startGesture(pointers.size === 1 ? false : true);
  }

  function startGesture(moved) {
    const points = [...pointers.values()];
    const middle = middleOf(points);
    gesture = { k: at.k, tx: at.tx, ty: at.ty, cx: middle.x, cy: middle.y, spread: spreadOf(points), moved: gesture?.moved || moved };
  }

  function groundMove(event) {
    if (!gesture || !pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const points = [...pointers.values()];
    const middle = middleOf(points);
    if (points.length === 1) {
      const dx = middle.x - gesture.cx;
      const dy = middle.y - gesture.cy;
      if (!gesture.moved && Math.hypot(dx, dy) < 4) return;
      gesture.moved = true;
      at.tx = gesture.tx + dx;
      at.ty = gesture.ty + dy;
    } else {
      gesture.moved = true;
      const box = ground.getBoundingClientRect();
      const k = clamp(gesture.k * (spreadOf(points) / (gesture.spread || 1)), ZOOM[0], ZOOM[1]);
      // The point of the graph that was between her fingers stays between them.
      const wx = (gesture.cx - box.left - gesture.tx) / gesture.k;
      const wy = (gesture.cy - box.top - gesture.ty) / gesture.k;
      at.k = k;
      at.tx = middle.x - box.left - wx * k;
      at.ty = middle.y - box.top - wy * k;
    }
    touched = true;
    flag(ground, "data-panning", true);
    draw();
  }

  function groundUp(event, cancelled) {
    if (!pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    if (pointers.size) {
      startGesture(true);
      return;
    }
    const pressed = gesture && !gesture.moved && !cancelled;
    gesture = null;
    flag(ground, "data-panning", false);
    if (pressed && view?.selected) act.select(null);              // a press on the empty ground closes the card
  }

  function wheel(event) {
    event.preventDefault();
    const box = ground.getBoundingClientRect();
    const unit = event.deltaMode === 1 ? 16 : 1;
    const factor = Math.exp(-event.deltaY * unit * (event.ctrlKey ? 0.012 : 0.0022));
    tween = null;
    Object.assign(at, zoomed(at, factor, event.clientX - box.left, event.clientY - box.top));
    touched = true;
    draw();
  }

  function zoomBy(factor) {
    touched = true;
    const base = tween ? tween.to : at;
    glide(zoomed(base, factor, ground.clientWidth / 2, ground.clientHeight / 2), 200);
  }

  // The zoom changes around the point [px, py] of the ground, which stays where it is.
  function zoomed(from, factor, px, py) {
    const k = clamp(from.k * factor, ZOOM[0], ZOOM[1]);
    return { k, tx: px - (px - from.tx) * (k / from.k), ty: py - (py - from.ty) * (k / from.k) };
  }

  // ---- the card ----------------------------------------------------------------------------------------------

  function drawCard() {
    const made = cardFor(view);
    const before = shown;
    const hadFocus = card.contains(document.activeElement) ? document.activeElement.id || "card" : null;
    const fromGraph = root.contains(document.activeElement);
    if (!made) {
      shown = null;
      card.setAttribute("data-idle", "");
      card.inert = true;
      layer.dataset.open = "false";
      if (hadFocus && before) nodes.get(before)?.button.focus({ preventScroll: true });
      return;
    }
    shown = view.selected;
    clear(cardIn).append(...made.parts.flat(Infinity).filter(Boolean));
    card.setAttribute("aria-label", made.label);
    card.removeAttribute("data-idle");
    card.inert = false;
    layer.dataset.open = "true";
    if (before !== shown) card.scrollTop = 0;
    // The focus follows what she did: into a newly opened card, and back onto the button that took the place of the one she pressed.
    if (hadFocus) (card.querySelector(`#${CSS.escape(hadFocus)}`) ?? card.querySelector("#forget-no") ?? card.querySelector("#forget:not(:disabled)") ?? card).focus({ preventScroll: true });
    else if (before !== shown && fromGraph) card.focus({ preventScroll: true });
  }

  function measureCard() {
    if (!shown) return;
    const box = ground.getBoundingClientRect();
    const frameBox = layer.getBoundingClientRect();
    const narrow = root.hasAttribute("data-narrow");
    card.style.width = narrow ? `${Math.max(200, Math.round(box.width - 16))}px` : "";
    card.style.maxHeight = `${Math.round(narrow ? box.height * 0.58 : box.height - 62)}px`;
    cardBox = { w: card.offsetWidth, h: card.offsetHeight, x: box.left - frameBox.left, y: box.top - frameBox.top, width: box.width, height: box.height };
  }

  // The card stays beside its dot while the dot or the ground moves. On a narrow ground it sits at the bottom.
  function placeCard() {
    if (!shown) return;
    const node = nodes.get(shown);
    const { w, h, width, height } = cardBox;
    let x = (width - w) / 2;
    let y = height - h - 8;
    let origin = "50% 100%";
    if (node && !root.hasAttribute("data-narrow")) {
      const nx = node.x * at.k + at.tx;
      const ny = node.y * at.k + at.ty;
      const gap = Math.max(16 + node.r * at.k, (node.w / 2) * at.k + 12);      // clear of the dot and of its name
      const fitsRight = nx + gap + w <= width - 10;
      const fitsLeft = nx - gap - w >= 10;
      const right = fitsRight || (!fitsLeft && nx < width / 2);
      x = clamp(right ? nx + gap : nx - gap - w, 10, Math.max(10, width - w - 10));
      y = clamp(ny - 30, 10, Math.max(10, height - h - 52));                    // the zoom buttons stay free
      origin = `${right ? 0 : w}px ${clamp(ny - y, 0, h).toFixed(0)}px`;
    }
    card.style.transform = `translate(${Math.round(x + cardBox.x)}px, ${Math.round(y + cardBox.y)}px)`;
    cardIn.style.transformOrigin = origin;
  }

  // On a narrow ground the card covers the lower part: the pressed dot is brought into the part that stays free.
  function reveal() {
    if (!shown || !root.hasAttribute("data-narrow") || drag) return;
    const node = nodes.get(shown);
    if (!node) return;
    const free = cardBox.height - cardBox.h - 8;
    const nx = node.tx * at.k + at.tx;
    const ny = node.ty * at.k + at.ty;
    const bottom = ny + (node.r + node.h + 10) * at.k;
    if (ny >= 70 && bottom <= free - 6 && nx >= 50 && nx <= cardBox.width - 50) return;
    glide({ k: at.k, tx: at.tx + (clamp(nx, 70, cardBox.width - 70) - nx), ty: at.ty + (clamp(free / 2, 80, Math.max(80, free - 40)) - ny) }, 240);
  }

  return { render };
}

function control(icon, onPress) {
  const paths = { plus: "M12 6v12M6 12h12", minus: "M6 12h12", frame: "M5 9V6a1 1 0 0 1 1-1h3M15 5h3a1 1 0 0 1 1 1v3M19 15v3a1 1 0 0 1-1 1h-3M9 19H6a1 1 0 0 1-1-1v-3" };
  return el("button", { type: "button", class: "know-control", "data-do": icon, on: { click: onPress } },
    svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
      svg("path", { d: paths[icon] })));
}

// Sets an attribute to a value, or takes it away when the value is false, null or empty.
function flag(node, name, value) {
  if (value === false || value === null || value === undefined || value === "") node.removeAttribute(name);
  else node.setAttribute(name, value === true ? "" : String(value));
}

function middleOf(points) {
  return { x: points.reduce((sum, point) => sum + point.x, 0) / points.length, y: points.reduce((sum, point) => sum + point.y, 0) / points.length };
}

function spreadOf(points) {
  return points.length < 2 ? 0 : Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
}
