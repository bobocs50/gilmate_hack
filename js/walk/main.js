// The walk on a phone: one stop at a time, one thing to press.
//
// The route comes out of the link (after "#", see link.js). A link ending in "#run", or no "#" at all,
// reads the saved run instead, and the page says so. Nothing is shown that the route does not hold.
// Once the page is open it needs no network: the route is in memory and the photos are fetched ahead.

import { el, clear } from "../dom.js";
import { decode, isRouteText, routeFromState, canSqueeze, webAddress } from "./link.js";
import { t, said, setLang, getLang } from "./words.js";
import { drawStrip } from "./strip.js";
import { copyText } from "./copy.js";

const root = document.getElementById("walk");
const APP = "gilmate";
const USER = "traveller";       // memory is kept per user id (CONTRACT.md section 6.1)

const app = {
  route: null,
  from: null,            // "link" | "run"
  step: 0,               // 0 .. stops - 1 are the stops; stops is the route note
  taps: {},              // leg id -> { verdict, state: "kept" | "sent" | "unreachable" | "refused", reason }
  sending: null,         // leg id of the answer on its way
  found: new Map(),      // photo id -> address, read from the saved files or the live session
  photos: new Map(),     // stop id -> { state: "loading" | "ok" | "none" | "failed", photo, image }
  files: null,           // the area's saved run, places and map: the files the link's "?area=" names
  map: null,             // the area's street map when it could be read
  copied: null,
  problem: null,         // [line, small line] instead of a route
};

// ---- start --------------------------------------------------------------------------------

async function readJson(path, { timeout = 8000 } = {}) {
  try {
    const res = await fetch(path, { signal: AbortSignal.timeout(timeout) });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// The files of the area the link names with "?area=" (data/areas.json, CONTRACT.md section 8.1), or of the area
// the route itself names. Without either, or when that file cannot be read, they are the first area's.
const FILES = { run: "data/run.json", candidates: "data/candidates.json", map: "data/map.json" };
let listed = null;

async function filesOf(name = null) {
  listed ??= await readJson("data/areas.json");
  const asked = new URLSearchParams(location.search).get("area");
  const areas = Array.isArray(listed?.areas) ? listed.areas : [];
  const area = areas.find((entry) => entry?.key === asked) ?? areas.find((entry) => name && entry?.name === name) ?? null;
  const own = (path, first) => (typeof path === "string" && /^data\/[\w./-]+\.json$/.test(path) && !path.includes("..") ? path : first);
  return { run: own(area?.run, FILES.run), candidates: own(area?.candidates, FILES.candidates), map: own(area?.map, FILES.map) };
}

async function start() {
  const written = decodeURIComponent(location.hash.slice(1));
  app.route = null;
  app.problem = null;
  let saved = null;

  if (isRouteText(written)) {
    if (!canSqueeze()) app.problem = [t("This browser is too old to open the route from the link."), null];
    else {
      try {
        app.route = await decode(written);
        app.from = "link";
      } catch {
        app.problem = [t("This link could not be read as a route."), t("Scan the code again on the computer, or copy the whole link.")];
      }
    }
  } else if (written === "" || written === "run") {
    saved = await readJson((await filesOf()).run);
    app.route = saved ? routeFromState(saved) : null;
    app.from = "run";
    if (!app.route) app.problem = [t("No saved run could be read, so there is no route to show."), null];
  } else {
    app.problem = [t("This link could not be read as a route."), t("Scan the code again on the computer, or copy the whole link.")];
  }

  if (!app.route) { render(); return; }
  app.files = await filesOf(app.route.area);
  setLang(app.route.lang);
  remember();
  render();

  await findPhotos(saved);
  loadPhotos();
  // The street map is a help, not a need: the strip is drawn without it first.
  readJson(app.files.map).then((map) => {
    if (map && map.origin && Array.isArray(map.ways)) { app.map = map; render(); }
  });
}

// ---- what the phone keeps: the step and the answers, per route ------------------------------

function key() {
  return `gilmate-walk:${app.route.made ?? ""}:${app.route.stops.map((stop) => stop.id).join(",")}`;
}

function remember() {
  try {
    const kept = JSON.parse(localStorage.getItem(key()) ?? "null");
    if (kept && typeof kept === "object") {
      app.taps = kept.taps && typeof kept.taps === "object" ? kept.taps : {};
      app.step = Math.min(Math.max(Number(kept.step) || 0, 0), app.route.stops.length);
      return;
    }
  } catch { /* nothing kept */ }
  app.taps = {};
  app.step = 0;
}

function keep() {
  try { localStorage.setItem(key(), JSON.stringify({ step: app.step, taps: app.taps })); } catch { /* a private tab keeps nothing */ }
}

function go(step) {
  app.step = step;
  app.copied = null;
  keep();
  // The phone's own back gesture goes one stop back; the page has no button for it.
  history.pushState({ step }, "");
  render();
  scrollTo(0, 0);
}

addEventListener("popstate", (event) => {
  if (!app.route) return;
  app.step = Math.min(Math.max(Number(event.state?.step) || 0, 0), app.route.stops.length);
  keep();
  render();
});
addEventListener("hashchange", start);

// ---- photos -------------------------------------------------------------------------------

// A link carries a long photo address only as the photo's id. The addresses are read from the files the
// page folder holds (and from the live session when the link names one), wherever a photo has that id.
async function findPhotos(saved) {
  const missing = app.route.stops.some((stop) => stop.street && !stop.street.url && stop.street.id);
  if (!missing) return;
  const collect = (value) => {
    if (Array.isArray(value)) value.forEach(collect);
    else if (value && typeof value === "object") {
      const address = typeof value.url === "string" ? value.url : value.thumb_url;
      if (typeof value.id === "string" && typeof address === "string" && !app.found.has(value.id)) app.found.set(value.id, address);
      Object.values(value).forEach(collect);
    }
  };
  const live = app.route.live;
  const sources = await Promise.all([
    live ? readJson(`${live.api}/apps/${APP}/users/${USER}/sessions/${encodeURIComponent(live.session)}`, { timeout: 4000 }) : null,
    saved ?? readJson(app.files.run),
    readJson(app.files.candidates),
  ]);
  sources.forEach(collect);
}

// A photo is shown from an https address or from the page's own photo folder, nothing else.
function photoAddress(photo) {
  const address = photo.url ?? app.found.get(photo.id) ?? null;
  if (!address) return null;
  if (/^data\/(?:[\w-]+\/)?photos\/[\w.-]+$/.test(address)) return address;
  return webAddress(address);
}

// Every stop's photo is fetched now, so the walk goes on without network. The stop's street photo first;
// when it cannot be loaded, the photo of the place itself.
function loadPhotos() {
  for (const stop of app.route.stops) {
    const choices = [stop.street, stop.place].filter(Boolean).map((photo) => ({ photo, address: photoAddress(photo) })).filter((choice) => choice.address);
    if (!choices.length) {
      app.photos.set(stop.id, { state: stop.street || stop.place ? "failed" : "none" });
      continue;
    }
    app.photos.set(stop.id, { state: "loading" });
    const attempt = (index) => {
      if (index >= choices.length) { app.photos.set(stop.id, { state: "failed" }); showPhoto(stop); return; }
      const image = new Image();
      image.alt = "";
      image.decoding = "async";
      image.onload = () => { app.photos.set(stop.id, { state: "ok", photo: choices[index].photo, image }); showPhoto(stop); };
      image.onerror = () => attempt(index + 1);
      image.src = choices[index].address;
    };
    attempt(0);
  }
  render();
}

function showPhoto(stop) {
  if (app.route.stops[app.step] === stop) render();
}

function photoFigure(stop) {
  const found = app.photos.get(stop.id) ?? { state: "loading" };
  if (found.state === "ok") {
    const { photo } = found;
    const what = photo.kind === "place" ? t("Photo of the place")
      : photo.distance_m !== null ? t("Street photo taken {distance} m from here", { distance: Math.round(photo.distance_m) }) : t("Street photo taken near here");
    // The photo alone: what it is goes to a screen reader. Authors and licences are in CREDITS.md.
    found.image.alt = what;
    return el("figure", { class: "walk-photo", "data-state": "ok" }, found.image);
  }
  return el("figure", { class: "walk-photo", "data-state": found.state },
    found.state === "loading" ? null : el("p", {}, found.state === "none" ? t("No photo found") : t("The photo could not be loaded")));
}

// ---- the words for the data ---------------------------------------------------------------

const ACCESS = {
  yes: "Wheelchair access listed on the map",
  limited: "Limited wheelchair access listed on the map",
  no: "Listed on the map as not wheelchair accessible",
};

function metres(value) {
  return value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m`;
}

function stairsWords(value) {
  return value === "none_mapped" ? t("No stairs mapped") : value === "some" ? t("Stairs on the way") : t("Stairs unknown");
}

function clock(stamp) {
  return /(?:T|\s)(\d{2}:\d{2})/.exec(String(stamp ?? ""))?.[1] ?? null;
}

// The warnings of a walk or a stop, each said once.
function warnings(hazards) {
  const lines = [];
  for (const hazard of hazards) {
    const detail = said(hazard.detail);
    if (detail && !lines.some((line) => line.text === detail.text)) lines.push(detail);
  }
  return lines.map((line) => el("p", { class: "walk-warn", lang: line.lang }, line.text));
}

// ---- answers: Fine / Too far ----------------------------------------------------------------

async function answer(leg, verdict) {
  const live = app.route.live;
  if (!live) {
    app.taps[leg.id] = { verdict, state: "kept" };
    keep();
    render();
    return;
  }
  app.sending = leg.id;
  render();
  app.taps[leg.id] = { verdict, ...(await sendAnswer(live, leg.id, verdict)) };
  app.sending = null;
  keep();
  render();
}

// One "feedback" turn to the live agent (CONTRACT.md section 6.2). The tool's own answer decides what is said.
async function sendAnswer(live, legId, verdict) {
  let text;
  try {
    const res = await fetch(`${live.api}/run_sse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(45000),
      body: JSON.stringify({
        appName: APP, userId: USER, sessionId: live.session, streaming: false,
        newMessage: { role: "user", parts: [{ text: JSON.stringify({ step: "feedback", leg_id: legId, verdict }) }] },
      }),
    });
    if (!res.ok) return { state: "unreachable" };
    text = await res.text();
  } catch {
    return { state: "unreachable" };
  }
  const answers = [];
  for (const frame of text.replace(/\r\n/g, "\n").split("\n\n")) {
    const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
    if (!data) continue;
    let event;
    try { event = JSON.parse(data); } catch { continue; }
    for (const part of event.content?.parts ?? []) {
      const tool = part.functionResponse ?? part.function_response;
      if (tool?.name === "record_feedback" && tool.response) answers.push(tool.response);
    }
  }
  if (answers.some((one) => one.status === "recorded")) return { state: "sent" };
  const last = answers[answers.length - 1];
  return { state: "refused", reason: last ? String(last.reason ?? last.rule ?? last.status ?? "") : "" };
}

function tapWords(tap) {
  const first = tap.verdict === "fine" ? t("You said: fine.") : t("You said: too far.");
  if (tap.state === "sent") return [first, t("Saved by your guide.")];
  if (tap.state === "unreachable") return [first, t("The guide could not be reached. Kept on this phone, not sent.")];
  if (tap.state === "refused") return [first, t("The guide did not save it ({reason}). Kept on this phone.", { reason: tap.reason || t("no reason given") })];
  return [first, t("Kept on this phone, not sent.")];
}

// ---- the screens --------------------------------------------------------------------------

function header() {
  const route = app.route;
  const where = route ? [route.area,
    app.from === "link" ? t("Route from the link") : clock(route.recorded) ? t("Saved run, {time}", { time: clock(route.recorded) }) : t("Saved run")].filter(Boolean).join(" · ") : "";
  return el("header", { class: "walk-bar" }, el("span", { class: "walk-mark" }, "gilmate"), el("span", { class: "walk-where" }, where));
}

function render() {
  document.documentElement.lang = getLang();
  clear(root);
  if (!app.route) {
    root.append(header(), el("main", { class: "walk-plain", role: app.problem ? "alert" : "status" },
      app.problem ? [el("p", {}, app.problem[0]), app.problem[1] ? el("p", { class: "walk-small" }, app.problem[1]) : null] : el("p", {}, t("Opening your route"))));
    return;
  }
  const stops = app.route.stops;
  root.append(header(), app.step >= stops.length ? noteScreen() : stopScreen(stops[app.step], app.step));
}

function stopScreen(stop, index) {
  const route = app.route;
  const stops = route.stops;
  const next = stops[index + 1] ?? null;
  const leg = next ? route.legs.find((one) => one.from === stop.id && one.to === next.id) ?? null : null;
  const before = index > 0 ? stops[index - 1] : null;
  const walked = before ? route.legs.find((one) => one.from === before.id && one.to === stop.id) ?? null : null;
  const kind = said(stop.kind);
  const what = [kind?.text, t(ACCESS[stop.access] ?? "Entrance access unknown")].filter(Boolean).join(" · ");
  // "Access unknown" is already said in the line above; a stop's other warnings get their own line.
  const stopWarnings = warnings(route.hazards.filter((hazard) => hazard.stop_id === stop.id && hazard.kind !== "unknown_access"));

  let walk = null;
  if (leg) {
    const name = next.name ?? t("the next stop");
    const benches = route.benches.filter((bench) => bench.leg_id === leg.id).length;
    walk = el("section", { class: "walk-leg", "aria-label": t("The walk to {name}", { name }) },
      el("ul", { class: "walk-facts" },
        el("li", {}, leg.distance_m === null ? t("Distance to {name} unknown", { name }) : t("{distance} to {name}", { distance: metres(leg.distance_m), name })),
        el("li", {}, stairsWords(leg.stairs)),
        el("li", {}, benches === 0 ? t("No bench mapped") : benches === 1 ? t("1 bench mapped") : t("{count} benches mapped", { count: benches }))),
      leg.kind && leg.kind !== "routed" ? el("p", { class: "walk-warn" }, t("Not a mapped path: a straight line")) : null,
      warnings(route.hazards.filter((hazard) => hazard.leg_id === leg.id)),
      drawStrip(route, leg, app.map, t("Map of this walk")));
  }

  // One thing to press: after a walk the two answers, otherwise "Next" (on the last stop "Done").
  const tap = walked ? app.taps[walked.id] : null;
  const asking = walked && !tap;
  const busy = walked && app.sending === walked.id;
  const foot = asking
    ? el("footer", { class: "walk-foot" },
        el("p", { class: "walk-ask", role: "status" }, busy ? t("Sending your answer") : t("How was the walk here from {from}?", { from: before.name ?? t("the stop before") })),
        el("div", { class: "walk-two" },
          el("button", { type: "button", class: "walk-button", id: "walk-fine", disabled: busy, on: { click: () => answer(walked, "fine") } }, t("Fine")),
          el("button", { type: "button", class: "walk-button", id: "walk-too-far", disabled: busy, on: { click: () => answer(walked, "too_far") } }, t("Too far"))))
    : el("footer", { class: "walk-foot" },
        tap ? el("p", { class: "walk-ask", role: "status", "data-sent": tap.state === "sent" ? "yes" : "no" }, tapWords(tap).join(" ")) : null,
        el("button", { type: "button", class: "walk-button", "data-lead": true, id: "walk-next", on: { click: () => go(index + 1) } }, next ? t("Next") : t("Done")));

  return el("main", { class: "walk-screen" },
    photoFigure(stop),
    el("div", { class: "walk-body" },
      el("p", { class: "walk-meta" }, t("Stop {n} of {count}", { n: index + 1, count: stops.length })),
      el("h1", { class: "walk-name" }, stop.name ?? t("Name unknown")),
      el("p", { class: "walk-what" }, what),
      stopWarnings,
      walk ?? el("p", { class: "walk-last" }, t("This is the last stop."))),
    foot);
}

function noteScreen() {
  const route = app.route;
  const lang = getLang();
  const note = route.note?.[lang] ?? route.note?.en ?? route.note?.ko ?? null;
  const lines = note ? note.split("\n").map((line) => line.trim()).filter(Boolean) : [];
  const unsent = Object.values(app.taps).filter((tap) => tap.state !== "sent").length;
  const text = el("div", { class: "walk-note-text", lang: route.note?.[lang] ? lang : null },
    lines.length ? lines.map((line) => el("p", {}, line)) : el("p", {}, t("No route note came with this route.")));
  const copyWord = el("span", { role: "status" }, app.copied === "done" ? t("Copied") : app.copied === "failed" ? t("Not copied: select the text instead") : t("Copy"));
  return el("main", { class: "walk-screen" },
    el("div", { class: "walk-body" },
      el("h1", { class: "walk-name" }, t("Your route note")),
      el("section", { class: "walk-note" },
        text,
        el("div", { class: "walk-note-foot" },
          el("div", { class: "walk-langs", role: "group", "aria-label": t("Language") },
            [["en", "EN"], ["ko", "KO"]].map(([value, label]) => el("button", { type: "button", class: "walk-lang", "aria-pressed": lang === value ? "true" : "false", "data-lang": value,
              on: { click: () => { setLang(value); app.copied = null; render(); } } }, label))),
          lines.length ? el("button", { type: "button", class: "walk-copy", id: "walk-copy", on: { click: async () => {
            app.copied = (await copyText(lines.join("\n"), text)) ? "done" : "failed";
            render();
          } } }, copyWord) : null)),
      unsent ? el("p", { class: "walk-small" }, unsent === 1 ? t("1 answer about a walk is kept on this phone and was not sent.")
        : t("{count} answers about the walks are kept on this phone and were not sent.", { count: unsent })) : null));
}

history.replaceState({ step: 0 }, "");
start().then(() => { if (app.route) history.replaceState({ step: app.step }, ""); });
