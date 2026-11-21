// The handoff: the route leaves the desk and goes onto the phone.
//
//   import { openHandoff } from "./handoff.js";
//   openHandoff({ spatial_model, route_note, candidates, language, source, sessionId });
//
// The first three are the session state's (CONTRACT.md sections 1 and 7.2). `language` is the page's.
// `source` ({ kind, api, root }, as js/api.js reads it) and `sessionId` are for a live page: with them the
// link also names the live session, and "Fine" / "Too far" on the phone are sent to the agent. Without them
// the answers stay on the phone, and the page says so.
//
// A small card on the final map: a QR code, the link written out, "Copy link" and a close cross.
// The link opens walk.html with the route in the link itself (js/walk/link.js), so the phone needs only the
// static page. The QR code is drawn here (js/vendor/qrcode.js); nothing is sent anywhere.
//
// The phone must be able to reach the address in the link. A page opened at 127.0.0.1 takes the computer's
// network address from "?lan=http://192.168.1.5:8765", which scripts/demo.sh --phone puts there.

import { el, svg } from "./dom.js";
import qrcode from "./vendor/qrcode.js";
import { routeFromState, encode, canSqueeze, webAddress } from "./walk/link.js";
import { t, setLang } from "./walk/words.js";
import { copyText } from "./walk/copy.js";

const BIGGEST_CODE = 34;       // QR version; larger codes are too fine to scan from a laptop screen
const QUIET = 4;               // modules of white around the code

/**
 * Shows the card and returns { kind, link, close }.
 * kind: "in_link" the route is in the link; "saved_run" the link opens the saved run;
 *       "too_large" the link holds the route but no QR code could be drawn; "none" there is no route.
 * options: { host: element to put the card into, base: address of the page folder as the phone reaches it }
 */
export async function openHandoff(state, options = {}) {
  const host = options.host ?? document.body;
  for (const old of host.querySelectorAll(".handoff, .handoff-pill")) old.remove();
  ensureStyles();
  const lang = setLang(state?.lang ?? state?.language ?? document.documentElement.lang);

  const code = el("div", { class: "handoff-code" });
  const written = el("p", { class: "handoff-link", translate: "no" });
  const note = el("p", { class: "handoff-note", role: "status" });
  const copyWord = el("span", { role: "status" }, t("Copy link"));
  const copy = el("button", { type: "button", class: "handoff-copy", disabled: true }, copyIcon(), copyWord);
  const close = el("button", { type: "button", class: "handoff-close", "aria-label": t("Close") }, crossIcon());
  // Folded, the card gives the map back and waits as a small pill at the top right; pressing the pill unfolds it.
  const fold = el("button", { type: "button", class: "handoff-fold", "aria-label": t("Fold") }, foldIcon());
  const pill = el("button", { type: "button", class: "handoff-pill", lang, "aria-label": t("Open your route on your phone"), tabindex: "-1" }, qrIcon(), el("span", {}, t("Phone")));
  const card = el("aside", { class: "handoff", role: "dialog", "aria-label": t("Open your route on your phone"), lang },
    el("div", { class: "handoff-head" }, el("h2", { class: "handoff-title" }, t("Open your route on your phone")), el("div", { class: "handoff-tools" }, fold, close)),
    code, written, note, copy);
  const setFolded = (folded) => {
    card.toggleAttribute("data-folded", folded);
    card.inert = folded;
    pill.toggleAttribute("data-shown", folded);
    pill.tabIndex = folded ? 0 : -1;
    (folded ? pill : fold).focus({ preventScroll: true });
  };
  fold.addEventListener("click", () => setFolded(true));
  pill.addEventListener("click", () => setFolded(false));

  const onKey = (event) => { if (event.key === "Escape") shut(); };
  function shut() {
    card.remove();
    pill.remove();
    document.removeEventListener("keydown", onKey);
  }
  close.addEventListener("click", shut);
  document.addEventListener("keydown", onKey);
  host.append(card, pill);

  const made = await makeLink(state, options, lang);
  if (made.link) {
    written.textContent = made.link;
    copy.disabled = false;
    copy.addEventListener("click", async () => {
      const done = await copyText(made.link, written);
      copyWord.textContent = done ? t("Copied") : t("Not copied: select the link instead");
    });
  } else {
    written.remove();
    copy.remove();
  }
  if (made.code) code.append(drawCode(made.code));
  else code.remove();
  note.textContent = [made.words, made.local ? t("This address only works on this computer. Start with scripts/demo.sh --phone.") : null].filter(Boolean).join(" ");
  card.dataset.kind = made.kind;
  return { kind: made.kind, link: made.link ?? null, close: shut };
}

// ---- the link -----------------------------------------------------------------------------

function isLocal(hostname) {
  return hostname === "localhost" || hostname === "[::1]" || /^127\./.test(hostname);
}

// The folder of the page as the phone reaches it: given, from "?lan=", or where this page was opened.
function phoneFolder(options) {
  const given = webAddress(options.base) ?? webAddress(new URLSearchParams(location.search).get("lan"));
  return new URL(given ? `${given}/` : new URL(".", location.href).href);
}

// A live session travels as the agent server's address and the session id. An address on this computer
// is rewritten to the network address of the page, which is where the phone finds the same computer.
function liveAddress(state, folder) {
  const source = state?.source;
  if (source?.kind !== "live" || !source.api || !state.sessionId) return null;
  let api;
  try { api = new URL(source.api); } catch { return null; }
  if (isLocal(api.hostname) && !isLocal(folder.hostname)) api.hostname = folder.hostname;
  return { api: api.href.replace(/\/+$/, ""), session: String(state.sessionId), root: source.root ?? null };
}

async function makeLink(state, options, lang) {
  const folder = phoneFolder(options);
  // Another area than the first is named in the link, so the phone page reads that area's files.
  const page = new URL(typeof state?.area === "string" && state.area ? `walk.html?area=${encodeURIComponent(state.area)}` : "walk.html", folder).href;
  const local = isLocal(folder.hostname);
  const route = routeFromState(state, { lang, live: liveAddress(state, folder) });
  if (!route) return { kind: "none", words: t("There is no route yet."), local: false };

  // The saved run can be read by the phone page itself, so a route that does not fit falls back to it.
  // A page that does not say what it shows is read as js/api.js reads its address: no ?api= and no ?dev= is the saved run.
  const asked = new URLSearchParams(location.search);
  const isSavedRun = !route.live && (state?.source ? state.source.kind === "recorded" : !asked.get("api") && !asked.get("dev"));
  const savedRun = () => {
    const link = `${page}#run`;
    return { kind: "saved_run", link, code: tryCode(`${page}#`, "", "run"), words: t("This link opens the saved run."), local };
  };

  if (!canSqueeze()) {
    return isSavedRun ? savedRun() : { kind: "none", words: t("This browser cannot put the route into a link."), local: false };
  }
  const text = await encode(route);
  const fits = tryCode(`${page}#`, text);
  if (fits) return { kind: "in_link", link: `${page}#${text}`, code: fits, words: t("The route is in this link."), local };
  if (isSavedRun) return savedRun();
  return { kind: "too_large", link: `${page}#${text}`, code: null, words: t("The route is too large for a QR code. Copy the link instead."), local };
}

// ---- the QR code --------------------------------------------------------------------------

// The address in byte mode, the route in the tighter alphanumeric mode. Null when it does not fit.
function tryCode(address, route, bytes = "") {
  try {
    const code = qrcode(0, "L");
    code.addData(address + bytes, "Byte");
    if (route) code.addData(route, "Alphanumeric");
    code.make();
    const version = (code.getModuleCount() - 17) / 4;
    return version <= BIGGEST_CODE ? code : null;
  } catch {
    return null;
  }
}

function drawCode(code) {
  const count = code.getModuleCount();
  const size = count + QUIET * 2;
  let path = "";
  for (let row = 0; row < count; row += 1) {
    for (let col = 0; col < count; col += 1) {
      if (code.isDark(row, col)) path += `M${col + QUIET} ${row + QUIET}h1v1h-1z`;
    }
  }
  return svg("svg", { viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": t("QR code of the link"), "shape-rendering": "crispEdges" },
    svg("rect", { width: size, height: size, fill: "#fff" }),
    svg("path", { d: path, fill: "#111" }));
}

// ---- small parts --------------------------------------------------------------------------

function ensureStyles() {
  if (document.querySelector("link[data-handoff]")) return;
  document.head.append(el("link", { rel: "stylesheet", href: new URL("../styles/walk.css", import.meta.url).href, "data-handoff": true }));
}

function copyIcon() {
  return svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    svg("rect", { x: 9, y: 9, width: 11, height: 11, rx: 2.5 }),
    svg("path", { d: "M5 15V6.5A2.5 2.5 0 0 1 7.5 4H15" }));
}

function foldIcon() {
  return svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    svg("path", { d: "M14 4h6v6M20 4l-7 7M10 20H4v-6" }));
}

function qrIcon() {
  return svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linejoin": "round", "aria-hidden": "true" },
    svg("rect", { x: 4, y: 4, width: 6, height: 6, rx: 1 }), svg("rect", { x: 14, y: 4, width: 6, height: 6, rx: 1 }),
    svg("rect", { x: 4, y: 14, width: 6, height: 6, rx: 1 }), svg("path", { d: "M14 14h2v2h-2zM18 18h2v2h-2zM14 18h1M19 14h1" }));
}

function crossIcon() {
  return svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "aria-hidden": "true" },
    svg("path", { d: "M6 6l12 12M18 6L6 18" }));
}
