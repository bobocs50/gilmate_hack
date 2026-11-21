// The talking guide (typeLine) is ported from Mercature by Glendon Chin (MIT), github.com/glendonC/mercature, src/ui/Chat.tsx: see THIRD_PARTY.md.
// Parts that more than one view uses: icons, the guide with its bubble, numbered choices, the text field,
// and the dock that holds them at the bottom of the map.

import { el, svg } from "./dom.js";
import { access } from "./text.js";
import { t } from "./words.js";

const ICONS = {
  arrowRight: ["M5 12h14M13 6l6 6-6 6"],
  arrowLeft: ["M19 12H5M11 6l-6 6 6 6"],
  arrowUp: ["M12 19V5M6 11l6-6 6 6"],
  chevronLeft: ["M14.5 6l-6 6 6 6"],
  chevronRight: ["M9.5 6l6 6-6 6"],
  plus: ["M12 5v14M5 12h14"],
  minus: ["M5 12h14"],
  fit: ["M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"],
  menu: ["M4 7h16M4 12h16M4 17h16"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "M20 20l-4-4"],
  skip: ["M6 6l6 6-6 6M13 6l6 6-6 6"],
  list: ["M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"],
  copy: ["M9 9h10v10H9z", "M5 15V5h10"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  cross: ["M6.5 6.5l11 11M17.5 6.5l-11 11"],
  // What a place is: a sight (a hall with columns), a shop (a bag), somewhere to eat (fork and knife).
  see: ["M4 20h16M6 20v-9M10 20v-9M14 20v-9M18 20v-9M3.5 11L12 5l8.5 6z"],
  shop: ["M6 8.5h12l1 11.5H5z", "M9 8.5V7a3 3 0 0 1 6 0v1.5"],
  eat: ["M7.5 3v7.5a2 2 0 0 0 2 2V21M5.5 3v5.5M9.5 3v5.5", "M17 3c-2 1.8-2.6 4.2-2.6 6.6 0 1.6 1 2.4 2.6 2.4V21"],
  noPhoto: ["M4 8h3l1.5-2h7L17 8h3v11H4z", "M12 10.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z", "M3 4l18 17"],
  photos: ["M4 8h3l1.5-2h7L17 8h3v11H4z", "M12 10.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  steps: ["M4 19h4v-4h4v-4h4V7h4"],
  bench: ["M4 11h16M5 11V8M19 11V8M6 11v6M18 11v6M4 15h16"],
  warn: ["M12 4l9 16H3z", "M12 10v4.5M12 17.2v.3"],
  // The sky of the day, for the weather mark in the top bar
  sun: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"],
  cloud: ["M7 18h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.1 11.1 3.5 3.5 0 0 0 7 18z"],
  rain: ["M7 15h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.1 8.1 3.5 3.5 0 0 0 7 15z", "M8.5 18l-.8 2.2M12.5 18l-.8 2.2M16.5 18l-.8 2.2"],
  storm: ["M7 15h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.1 8.1 3.5 3.5 0 0 0 7 15z", "M12.5 16.5l-2 3h3l-2 3"],
  snow: ["M7 15h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.1 8.1 3.5 3.5 0 0 0 7 15z", "M8.5 18.5h.01M12 20.5h.01M15.5 18.5h.01"],
  pin: ["M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0C18.5 15 12 21 12 21z", "M12 8a2.2 2.2 0 1 0 0 4.4A2.2 2.2 0 0 0 12 8z"],
};

export function icon(name) {
  return svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    (ICONS[name] ?? []).map((d) => svg("path", { d })));
}

export function accessChip(value) {
  const { label, tone } = access(value);
  return el("span", { class: "chip", "data-tone": tone }, label);
}

/**
 * The "Type in your own words" field with its round send button. `multiline`: a field that holds a few lines and
 * grows with its words (the landing's, which comes filled in); Enter sends, Shift and Enter makes a new line.
 * `onInput` is told what stands in the field after every change.
 */
export function composer({ placeholder, label, onSend, disabled = false, send = "arrowUp", sendLabel = null, value = null, multiline = false, onInput = null }) {
  const input = multiline
    ? el("textarea", { name: "words", rows: 1, placeholder, "aria-label": label, autocomplete: "off", maxlength: 400, disabled }, value ?? "")
    : el("input", { type: "text", name: "words", placeholder, "aria-label": label, autocomplete: "off", maxlength: 400, disabled, value });
  const button = el("button", { type: "submit", class: "composer-send", "aria-label": sendLabel ?? t("Send"), disabled: multiline ? disabled || !String(value ?? "").trim() : true }, icon(send));
  const form = el("form", { class: "composer", "data-off": disabled }, input, button);
  if (multiline) {
    // As high as its words, measured once it is on the page and again when the type has loaded
    const fit = () => { input.style.height = "auto"; input.style.height = `${input.scrollHeight}px`; };
    input.addEventListener("input", fit);
    input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); form.requestSubmit(); } });
    requestAnimationFrame(fit);
    document.fonts?.ready?.then(fit);
  }
  input.addEventListener("input", () => { button.disabled = disabled || !input.value.trim(); if (onInput) onInput(input.value); });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value || disabled) return;
    onSend(value);
  });
  return form;
}

/**
 * Numbered answers, one under the other. The number keys choose them.
 * Each: { label, onPick, lead, pressed, disabled, id, hint }. `lead` is the light one: the answer that goes on.
 */
export function choices(list, { label = null, row = false } = {}) {
  return el("ol", { class: "choices", "data-row": row, "aria-label": label }, list.filter(Boolean).map((choice, index) =>
    el("li", { style: `--i: ${index}` }, el("button", {
      type: "button", class: "choice", id: choice.id ?? null, "data-key": index + 1, "data-lead": choice.lead ? true : null,
      "aria-pressed": choice.pressed === undefined ? null : choice.pressed ? "true" : "false",
      disabled: Boolean(choice.disabled), "aria-describedby": choice.describedBy ?? null,
      // A press before the guide has said what it is about does nothing: the choices are not ready yet.
      on: { click: (event) => { const owner = event.currentTarget.closest(".dock"); if (!owner || owner.hasAttribute("data-ready")) choice.onPick(event); } },
    }, el("span", { class: "choice-key", "aria-hidden": "true" }, index + 1), el("span", { class: "choice-label" }, choice.label)))));
}

/** A quiet link with a small mark: "Skip". */
export function quiet(name, label, onPick, attrs = {}) {
  return el("button", { type: "button", class: "quiet", on: { click: onPick }, ...attrs }, name ? icon(name) : null, el("span", {}, label));
}

// The guide says its sentence: it types at 40 characters a second while the guide bobs, and her choices come
// a moment after the sentence is whole. A press on the sentence completes it at once. A sentence already said
// is not said again when the page draws itself anew, and one half said goes on from where it was.
const PER_CHAR = 25;
const SETTLE = 600;
const said = { text: null, began: 0, whole: false, stop: null };

function typeLine(dockEl, wordsEl, avatarEl, text, hold = false, plain = false) {
  const ready = () => { if (!hold) dockEl.setAttribute("data-ready", ""); };
  if (said.stop) said.stop();
  const calm = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!text || calm || plain || (said.text === text && said.whole)) {
    wordsEl.textContent = text;
    Object.assign(said, { text, whole: true, stop: null });
    ready();
    return;
  }
  if (said.text !== text) Object.assign(said, { text, began: performance.now(), whole: false });
  const typed = el("span", {});
  const rest = el("span", { class: "untyped" }, text);        // the rest keeps its room: the bubble never changes size
  wordsEl.replaceChildren(typed, rest);
  let frame = 0, timer = 0, settle = 0, over = false;
  const finish = () => {
    if (over) return;
    over = true;
    cancelAnimationFrame(frame);
    clearTimeout(timer);
    typed.textContent = text;
    rest.textContent = "";
    said.whole = true;
    avatarEl.removeAttribute("data-talking");
    settle = setTimeout(ready, SETTLE);
  };
  const step = () => {
    const n = Math.floor((performance.now() - said.began) / PER_CHAR);
    typed.textContent = text.slice(0, n);
    rest.textContent = text.slice(n);
    if (n < text.length) frame = requestAnimationFrame(step); else finish();
  };
  // A tab that paints no frames still gets its sentence
  timer = setTimeout(finish, Math.max(0, said.began + text.length * PER_CHAR + 150 - performance.now()));
  said.stop = () => { over = true; cancelAnimationFrame(frame); clearTimeout(timer); clearTimeout(settle); };
  avatarEl.setAttribute("data-talking", "");
  wordsEl.addEventListener("click", finish, { once: true });
  frame = requestAnimationFrame(step);
}

/**
 * The dock: the guide and its one sentence at the bottom of the map, the numbered choices directly above it.
 * What the sentence is about (`content`: a place, the note) stands in a narrow column at the left edge
 * (a sheet above the choices on a phone). `under` is a small thing under the bubble (the step dots).
 * While the agents work the sentence shimmers and the guide's eyes move; `done` puts a tick before it.
 * A plain sentence is typed (typeLine); the dock is marked `data-ready` when her choices may be pressed.
 */
export function dock({ content = null, actions = null, line, lineAttrs = {}, under = null, working = false, done = false, hold = false, plain = false }) {
  const work = content || actions
    ? el("div", { class: "work" },
        content ? el("div", { class: "work-content" }, content) : null,
        actions ? el("div", { class: "work-actions" }, actions) : null)
    : null;
  const avatar = el("span", { class: "guide-avatar", "data-working": working ? true : null, "aria-hidden": "true" });
  const words = el("p", { class: "line-words", "data-working": working ? true : null }, done ? el("span", { class: "line-tick", "aria-hidden": "true" }, icon("check")) : null, line);
  const dockEl = el("div", { class: "dock" },
    work,
    el("div", { class: "dialogue" }, avatar, el("div", { class: "guide-line", ...lineAttrs }, words), under));
  // `hold`: the guide is not yet talking about what the choices answer, so they stay hidden and cannot be pressed.
  // `plain`: the sentence is shown whole at once and the choices come with it (choosing places, where speed matters).
  if (typeof line === "string" && !working && !done) typeLine(dockEl, words, avatar, line, hold, plain);
  else if (!hold) dockEl.setAttribute("data-ready", "");
  return dockEl;
}
