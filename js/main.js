// Gilmate page: one straight line (CONTRACT.md section 7). The text field, the map being made, the places one
// at a time with Yes and No, one open question about walking, stairs and sitting down, the route in sentences,
// and the final map. Screens are rebuilt from the state on every change; the map is kept and only told what
// to show and where to look. The walk itself happens on the phone page (frontend/js/handoff.js, when it is there).

import { el, clear } from "./dom.js";
import { clock, metres, pick, profileWords } from "./text.js";
import { readSource, loadAreas, loadRun, loadEarly, loadMap, createSession, sendTurn, readState } from "./api.js";
import { createMap } from "./map.js";
import { orderedStops, totalDistance } from "./model.js";
import { renderPlan, QUESTIONS, EXAMPLE, MIN_PLACES, MAX_PLACES, readCandidates, yesPlaces, kindWords, areaWords } from "./plan.js";
import { renderRoute } from "./route.js";
import { newProgress, rowsFromAudit, takeEvent, groupSteps, stepTimes } from "./progress.js";
import { markFromState, readForecast, drawMark } from "./weather.js";
import { createKnow } from "./know.js";
import { t, setLang, isKorean } from "./words.js";
import { readMemory, reachedMemory, rememberedAnswers, findFact, factName, localDay, forgetOutcome } from "./memory.js";

const stage = document.getElementById("stage");
const content = document.getElementById("content");
const bar = document.querySelector(".bar");
const map = createMap(document.getElementById("map"));
const knowDialog = document.getElementById("know");
const knowBody = document.getElementById("know-body");
const knowSide = document.getElementById("know-side");
const know = createKnow(knowBody, knowSide, {
  select(id) {
    const before = app.know.selected;
    app.know = { ...app.know, selected: id, confirm: null, message: null };
    renderKnow(id ? "panel" : `node:${before}`);
  },
  askForget(factId) {
    app.know = { ...app.know, confirm: factId };
    renderKnow(factId ? "keep" : "forget");
  },
  forget: (factId) => forget(factId),
});

const app = {
  source: readSource(),
  areas: [],            // the areas the page can open (data/areas.json), the default one first
  areaKey: null,        // the area the page shows now
  saved: {},            // area key -> { run, early }: what its files hold (the run only in recorded and dev mode)
  run: null,            // the saved run of the area shown (recorded and dev mode)
  view: "plan",         // plan (everything up to the route) | route
  step: "landing",      // landing | making | choose | food | remember | context | ask | working | error
  none: false,          // there is nothing to open
  noneReason: () => "", // why, said in the page's language when it is drawn
  landingNote: null,    // what the guide says on the landing screen after a place it has no map for was typed
  area: null,           // { name, bbox, supported, photo } as the backend gives it
  candidates: [],       // the places to choose from (CONTRACT.md section 7.2)
  streetPhotos: [],
  restSpots: [],        // the places to sit the map knows
  counts: null,
  said: {},             // candidate id -> "yes" | "no"
  at: 0,                // the place she is looking at
  placeNote: null,
  foodAt: null,         // the place to eat whose picture shows in the food question
  foodFull: false,      // five Yes already: the food question is skipped
  photoAt: {},          // candidate id -> the photo she is at
  progress: null,       // what the agent is doing, or a saved run's steps played back
  mapKey: "",           // what the map shows now, so it is redrawn only when that changes
  context: { busy: false, typed: null, said: null },   // the open question: her words, and what was understood
  asking: [],           // the questions her words left open, asked one at a time
  q: 0,
  answers: {},          // walk, stairs, rest -> value; wish -> her words or null
  model: null,
  routeNote: null,      // { en, ko } as Python wrote it, when the run holds one
  routeSub: "note",     // "note" (the route in sentences) | null (the final map)
  noteLang: null,
  copied: null,
  handoff: null,        // openHandoff from frontend/js/handoff.js, when that file is there
  audit: [],
  lang: "en",           // en | ko: English until she writes in Korean or uses the switch
  langChosen: false,    // she used the switch herself, so her writing no longer changes the language
  mapDrawn: false,
  workingText: "",
  error: "",
  retry: null,
  sessionId: null,      // live: the one session of this page; her memory is read through it before she types
  sessionError: null,
  memory: null,         // { facts, feedback } as the backend keeps it under "user:memory", or null when unknown
  memoryNote: () => "", // why there is no memory to show, said in the page's language when it is drawn
  today: localDay(),    // a limit that is still being learned counts only on its day
  know: { selected: null, confirm: null, busy: false, message: null },
};
let timer = 0;          // the one pending step of a replay, or the pause before the route is built
// For the page check only: ?pace=20 tells a saved run's steps twenty times faster than they really took.
const PACE = Math.max(1, Number(new URLSearchParams(location.search).get("pace")) || 8);   // published copy: fast replay by default

const act = {
  search(text) { startArea(text); },
  // A card under "Last runs": that area, asked for with its own example sentence.
  open(key) { const area = entryOf(key) ?? app.areas[0]; startArea(area?.example ?? t(EXAMPLE), area?.key ?? null); },
  retry() { if (app.retry) app.retry(); },
  skipReplay,
  openPlace(id) { const index = app.candidates.findIndex((place) => place.id === id); if (index >= 0 && app.view === "plan" && app.step !== "landing") { if (isFood(app.candidates[index])) { app.foodAt = id; askFood(); } else goToPlace(index); } },
  sayPlace,
  sayFood,
  // "Yes": her remembered answers are this session's answers. "Change": she tells me again.
  stillTrue() { app.answers = { wish: null, ...remembered() }; askMissing(); },
  changeAnswers() { app.answers = {}; askContext(); },
  tellContext,
  answer(key, value) {
    app.answers[key] = value;
    if (app.q < app.asking.length - 1) { app.q += 1; render(); return; }
    makeRoute();
  },
  showFinalMap() { app.routeSub = null; render(); },
  noteLang(value) { app.noteLang = value; app.copied = null; render(); },
  async copyNote(text) {
    try { await navigator.clipboard.writeText(text); app.copied = "done"; } catch { app.copied = "failed"; }
    render();
  },
  // The walk happens on the phone: the handoff module shows how to open the route there.
  startRoute() {
    if (typeof app.handoff !== "function") return;
    // What the handoff asks for (frontend/js/handoff.js): the route, its note, the places, the page's language,
    // and on a live page the agent's address and the session, so answers on the phone reach the agent.
    // The first area is the one the phone page reads by itself; another one is named in the link ("?area=").
    app.handoff({ spatial_model: app.model, route_note: app.routeNote, candidates: app.candidates, language: app.lang,
      area: app.areaKey && app.areaKey !== app.areas[0]?.key ? app.areaKey : null,
      source: app.source.kind === "live" ? app.source : null, sessionId: app.source.kind === "live" ? app.sessionId : null });
  },
  openKnow,
};

init();

async function init() {
  document.getElementById("view-tabs").addEventListener("click", (event) => {
    const target = event.target.closest("[data-go]");
    if (!target) return;
    if (target.dataset.go === "know") openKnow(); else if (knowDialog.open) knowDialog.close();
  });
  document.getElementById("lang").addEventListener("click", (event) => {
    const target = event.target.closest("[data-lang]");
    if (!target) return;
    app.lang = target.dataset.lang;
    app.langChosen = true;
    render();
  });
  // When she writes in Korean, the page turns Korean. This runs before the form's own handler, so the answer
  // to what she wrote is already drawn in Korean. The switch above turns it back.
  document.addEventListener("submit", (event) => {
    const words = event.target.querySelector?.("input, textarea")?.value;
    if (!app.langChosen && app.lang !== "ko" && isKorean(words)) {
      app.lang = "ko";
      setLang("ko");
    }
  }, true);
  document.getElementById("start-over").addEventListener("click", () => startOver());
  document.getElementById("know-close").addEventListener("click", () => knowDialog.close());
  knowDialog.addEventListener("click", (event) => { if (event.target === knowDialog) knowDialog.close(); });
  knowDialog.addEventListener("close", () => markTabs());
  // Nothing on the page opens the list of the agent's steps at the moment; it draws itself when it is opened.
  const dialog = document.getElementById("audit");
  dialog.addEventListener("toggle", () => { if (dialog.open) renderAudit(); });
  document.getElementById("audit-close").addEventListener("click", () => dialog.close());
  // Number keys choose an answer, as the numbers beside the answers suggest. A key press is not animated.
  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, textarea, dialog") || event.metaKey || event.ctrlKey || event.altKey) return;
    // Not before the guide has said its sentence: until then the answers are not on the screen
    const button = content.querySelector(`.dock[data-ready] .choice[data-key="${CSS.escape(event.key)}"]:not(:disabled)`);
    if (button) button.click();
  });
  new ResizeObserver(() => { stage.style.setProperty("--bar-h", `${bar.offsetHeight}px`); lookAt(); }).observe(bar);
  window.addEventListener("resize", lookAt);
  // The phone handoff is another worker's file. When it is there, the final map offers "Start the route".
  import("./handoff.js").then((module) => { app.handoff = typeof module.openHandoff === "function" ? module.openHandoff : null; if (app.model) render(); }).catch(() => { app.handoff = null; });

  const source = app.source;
  app.areas = await loadAreas(source);
  app.areaKey = app.areas[0].key;
  if (source.kind === "bad_api") {
    app.none = true;
    app.noneReason = () => t("The address after ?api= is not a web address, so no run is available. Use, for example, ?api=http://localhost:8000.");
    app.memoryNote = () => t("No agent is named, so nothing is known about what I remember.");
  } else {
    if (source.kind === "live") {
      // The page runs on the live agents whenever their server answers. When it does not, the saved run is shown.
      app.memoryNote = () => t("I am still reading what I remember.");
      await readLiveMemory();
      if (app.sessionError) app.source = { kind: "recorded" };
    }
  }
  if (app.source.kind === "recorded" || app.source.kind === "dev") {
    const source = app.source;
    // Every area's saved run is read at once, so pressing a card needs no waiting.
    const runs = await Promise.all(app.areas.map((area) => loadRun(source, area)));
    app.areas.forEach((area, index) => { app.saved[area.key] = { run: runs[index].data && typeof runs[index].data === "object" ? runs[index].data : null, early: null }; });
    const loaded = runs[0];
    if (app.saved[app.areaKey].run) {
      showSaved(app.areaKey);
      app.memoryNote = () => (source.kind === "dev" ? t("This development sample holds no memory.")
        : t("The saved run holds no memory, so there is nothing to show here. Memory is kept by the live agent."));
      // A sample pretends it is the day it was written for; a real run is read against today's date.
      if (source.kind === "dev" && /^\d{4}-\d{2}-\d{2}$/.test(loaded.data._today ?? "")) app.today = loaded.data._today;
    } else {
      app.memoryNote = () => t("There is no run, so nothing is known about what I remember.");
      app.none = !app.areas.some((area) => app.saved[area.key].run);
      app.noneReason = () => (loaded.broken
        ? t("The file {file} could not be read, so there is no run to show.", { file: source.kind === "dev" ? source.sample : app.areas[0].run ?? "data/run.json" })
        : source.kind === "dev" ? t("There is no run to show: the development sample {sample} is missing.", { sample: source.sample })
        : t("There is no run yet, so no places are shown. No run has been saved in data/run.json, and the address of this page names no live agent (add ?api=http://localhost:8000 to it)."));
    }
  }
  render();

  if (app.source.kind !== "bad_api") {
    // The places Python builds without the model: real data the page may draw at once (section 7.2).
    const first = app.areas[0];
    const [, ...early] = await Promise.all([drawMap(first), ...app.areas.map((area) => loadEarly(app.source, area))]);
    app.areas.forEach((area, index) => {
      const data = early[index].data;
      app.saved[area.key] = { run: null, ...app.saved[area.key], early: data && typeof data === "object" ? data : null };
    });
    takeEarly();
    if (app.source.kind === "recorded" && app.areas.some((area) => hasSaved(area.key))) app.none = false;
    render();
  }
}

// ---- the agent turns (live) or the saved run (recorded) ------------------------------------

// Live: what is remembered about her is per-user state, and the server shows it in any of her sessions.
// So the page opens its session at once and reads it there, before she has typed anything.
async function readLiveMemory() {
  try {
    app.sessionId = await createSession(app.source.api);
    takeState(await readState(app.source.api, app.sessionId));
  } catch (error) {
    app.memory = null;
    const why = readable(error);
    app.sessionError = why;
    app.memoryNote = () => t("What I remember could not be read. {why}", { why });
  }
  renderKnow();
}

function remembered() {
  return rememberedAnswers(knowMemory(), QUESTIONS);      // a new visit starts with nothing remembered
}

function buildProfile() {
  const profile = { language: app.lang, wish: app.answers.wish ?? null };
  for (const question of QUESTIONS) profile[question.key] = app.answers[question.key] ?? question.careful;
  return profile;
}

// Everything about the area that a state or a saved file holds: the places, the photos, the benches, the counts.
function takePlaces(data) {
  const places = readCandidates(data);
  if (places.length) app.candidates = places;
  if (data.area && typeof data.area === "object") app.area = { ...(app.area ?? {}), ...data.area };
  if (Array.isArray(data.street_photos)) app.streetPhotos = data.street_photos;
  if (Array.isArray(data.rest_spots)) app.restSpots = data.rest_spots;
  if (data.counts && typeof data.counts === "object") app.counts = data.counts;
  if (data.route_note && typeof data.route_note === "object") app.routeNote = data.route_note;
  takeWeather(data);
}

// The weather mark in the top bar: from the backend's verdict when the data holds one, otherwise today's
// forecast for the area is read once in the browser. Neither: the mark stays empty.
function takeWeather(data) {
  // The mark belongs to one area: another area starts with none.
  const where = Array.isArray(app.area?.bbox) ? app.area.bbox.join(",") : null;
  if (where !== app.dayMarkWhere) Object.assign(app, { dayMarkWhere: where, dayMark: null, dayMarkAsked: false });
  const mark = markFromState(data?.weather);
  if (mark) { app.dayMark = mark; return; }
  if (app.dayMark || app.dayMarkAsked || !where) return;
  app.dayMarkAsked = true;
  readForecast(app.area).then((found) => { if (found && !app.dayMark && app.dayMarkWhere === where) { app.dayMark = found; render(); } });
}

// ---- the areas (CONTRACT.md section 8.1) -----------------------------------------------------

function entryOf(key) {
  return app.areas.find((area) => area.key === key) ?? null;
}

/**
 * Python decides this in a live run (the "start" turn). Without the agent the page knows its areas by their words:
 * the area whose word stands first in the text is the one asked for; no word, no area.
 */
function namedArea(text) {
  const lower = String(text).toLowerCase();
  let best = null;
  for (const area of app.areas) {
    for (const word of Array.isArray(area.words) ? area.words : []) {
      const at = lower.indexOf(String(word).toLowerCase());
      if (at >= 0 && (!best || at < best.at)) best = { at, area };
    }
  }
  return best?.area ?? null;
}

// The places Python builds without the model, when the area shown has none yet; otherwise only its picture.
function takeEarly() {
  const early = app.saved[app.areaKey]?.early;
  if (!early) return;
  if (!app.candidates.length) takePlaces(early);
  else if (early.area?.photo && !app.area?.photo) app.area = { ...(app.area ?? {}), photo: early.area.photo };
}

function hasSaved(key) {
  const saved = app.saved[key];
  return Boolean(saved?.run) || readCandidates(saved?.early).length > 0;
}

// Another area: nothing of the one before stays, not its places, not her answers to them.
function clearArea(key) {
  app.areaKey = key;
  Object.assign(app, { area: null, candidates: [], streetPhotos: [], restSpots: [], counts: null, routeNote: null, said: {}, photoAt: {}, at: 0, mapKey: "" });
}

// The area as its saved files hold it: the run, and the places Python builds without the model.
function showSaved(key) {
  const run = app.saved[key]?.run ?? null;
  clearArea(key);
  app.run = run;
  app.audit = Array.isArray(run?.audit) ? run.audit : [];
  app.memory = run ? readMemory(run) : null;
  if (run) takePlaces(run);
  takeEarly();
}

// The map is set up again from the area's own file: each has its own origin and bearing, and a place
// becomes metres with the origin of the same file, so no other area's map may stay loaded.
async function drawMap(area) {
  const drawn = await loadMap(app.source, area);
  app.mapDrawn = drawn.data ? map.setData(drawn.data) : false;
  app.mapKey = "";
}

// "Shibuya in Tokyo and Hongdae in Seoul": every area there is a map for.
function areaList() {
  const names = app.areas.map((area) => { const words = areaWords(area); return words.city ? t("{place} in {city}", words) : words.place; });
  return names.length > 1 ? t("{first} and {last}", { first: names.slice(0, -1).join(", "), last: names[names.length - 1] }) : names[0];
}

function notSupported(text) {
  app.step = "landing";
  app.landingNote = () => t(app.areas.length > 1 ? "I have no map for “{text}”: only {areas} have one today." : "I have no map for “{text}”: only {areas} has one today.", { text, areas: areaList() });
  render();
}

// She typed where she wants to go, or pressed the card. The map is made: live by the agent, told step by step
// as its events arrive; in a saved run the run's own steps are played back.
async function startArea(text, key = null) {
  clearTimeout(timer);
  app.retry = () => startArea(text, key);
  app.landingNote = null;
  if (app.none) { render(); return; }
  app.workingText = t("Reading your request");
  const named = key ? entryOf(key) : namedArea(text);
  if (app.source.kind !== "live") {
    if (!named) { notSupported(text); return; }
    if (!hasSaved(named.key)) {
      app.step = "landing";
      app.landingNote = () => t("No run of {area} has been saved, so there is nothing to show for it.", { area: areaWords(named).place });
      render();
      return;
    }
    if (named.key !== app.areaKey) { showSaved(named.key); await drawMap(named); }
    app.step = "making";
    replay("map", rowsFromAudit(planRows(app.audit)), startChoosing);
    return;
  }
  // While the agent reads the request the map shows the area her words seem to name. The agent's answer decides.
  if (named && named.key !== app.areaKey) { clearArea(named.key); takeEarly(); await drawMap(named); }
  app.step = "making";
  app.progress = newProgress("live", "map");
  render();
  try {
    if (!app.sessionId) throw new Error(app.sessionError ?? t("The agent server could not be reached. Check that it is running and allows this page."));
    const progress = app.progress;
    const { state } = await sendTurn(app.source.api, app.sessionId, { step: "start", text }, app.source.root, (event) => {
      if (takeEvent(progress, event) && app.step === "making") render();
    });
    takeState(state);
    // Her request may already say how she walks: the state then holds her answers and what the guide says back.
    app.told = state.profile && typeof state.profile === "object" && Array.isArray(state.profile_missing)
      ? { text, profile: state.profile, missing: state.profile_missing, said: state.understood ?? null } : null;
    if (state.area && state.area.supported === false) { notSupported(text); return; }
    // A state without a key is the first area. Its map is the file the state names.
    const area = entryOf(state.area?.key) ?? app.areas[0];
    if (area.key !== app.areaKey) { clearArea(area.key); await drawMap({ ...area, map: state.area?.map ?? area.map }); }
    takePlaces(state);
    if (!readCandidates(state).length) throw new Error(t("The agent finished without any places in the session state."));
    startChoosing();
  } catch (error) {
    fail(error);
  }
}

function fail(error) {
  app.step = "error";
  app.error = readable(error);
  render();
}

// The steps of a saved run that made the map: everything before the places were chosen.
function planRows(rows) {
  const end = rows.findIndex((row) => ["record_said", "record_picks", "router", "critic", "propose_route"].includes(row.tool) || ["router", "critic", "companion"].includes(row.agent));
  return end < 0 ? rows : rows.slice(0, end);
}

// The steps that built the route. They end where the walk begins: the companion's answers and her taps come later.
function routeRows(rows) {
  const start = rows.findIndex((row) => ["record_picks", "router", "critic", "propose_route"].includes(row.tool) || ["router", "critic"].includes(row.agent));
  if (start < 0) return [];
  const rest = rows.slice(start);
  const end = rest.findIndex((row) => ["companion", "record_feedback", "forget_fact"].includes(row.tool) || row.agent === "companion");
  return end < 0 ? rest : rest.slice(0, end);
}

// Tells the saved run's steps at the pace of the run itself: each step as long as it really took by its rows'
// clock times, at least three seconds, the whole at most about a minute. Then the line goes on.
function replay(flow, rows, then) {
  app.progress = { ...newProgress("replay", flow), rows, at: 0, then };
  const times = stepTimes(groupSteps(app.progress));
  if (!times.length) { app.progress.then = null; then(); return; }
  const step = () => {
    if (app.progress.at >= times.length - 1) { app.progress.then = null; then(); return; }
    app.progress.at += 1;
    render();
    timer = setTimeout(step, times[app.progress.at] / PACE);
  };
  render();
  timer = setTimeout(step, times[0] / PACE);
}

function skipReplay() {
  clearTimeout(timer);
  const then = app.progress?.then;
  if (!then) return;
  app.progress.then = null;
  then();
}

// What the map shows while it is being made: each kind of thing appears when its step is reached.
function reached() {
  if (app.step !== "making" || !app.progress) return null;
  const steps = groupSteps(app.progress);
  const upTo = app.progress.kind === "live" ? steps.length : app.progress.at + 1;
  const keys = steps.slice(0, upTo).map((step) => step.key);
  return { places: keys.includes("places"), dots: keys.includes("photos"), spots: keys.includes("benches") };
}

// ---- choosing ------------------------------------------------------------------------------

// Before the first place the guide says what is coming: "These are the 12 best places I found in Shibuya."
function startChoosing() {
  if (!app.candidates.length) { fail(new Error(t("I found no places, so there is nothing to choose from."))); return; }
  const area = areaWords(app.area?.name ? app.area : entryOf(app.areaKey)).place;
  const intro = () => t("These are the {count} best places I found in {area}.", { count: app.candidates.length, area });
  // While the guide says the intro, the Yes / No below it are not about anything yet: they wait for the place's own line.
  intro.hold = true;
  nextChoice();
  if (app.step !== "choose" && app.step !== "food") return;
  app.placeNote = intro;
  render();
  // The intro is short, and a press or a key ends it at once; that press or key chooses nothing.
  const end = (event) => {
    window.removeEventListener("pointerdown", end, true);
    window.removeEventListener("keydown", end, true);
    if (app.placeNote !== intro) return;
    if (event) { event.stopPropagation(); event.preventDefault(); }
    clearTimeout(timer);
    app.placeNote = null;
    render();
  };
  window.addEventListener("pointerdown", end, true);
  window.addEventListener("keydown", end, true);
  timer = setTimeout(() => end(null), 1400);
}

// Food is chosen once: the places to eat are not asked one at a time but together, after the sights and shops.
const isFood = (place) => place?.category === "eat";
function foodPlaces() { return app.candidates.filter(isFood); }

function firstOpen(from) {
  const count = app.candidates.length;
  for (let i = 0; i < count; i += 1) {
    const index = (from + i) % count;
    if (!isFood(app.candidates[index]) && !app.said[app.candidates[index].id]) return index;
  }
  return -1;
}

// The next thing to ask: a sight or shop not answered, else the food question, else the line goes on.
function nextChoice(from = 0) {
  const next = firstOpen(from);
  if (next >= 0) { goToPlace(next); return; }
  const food = foodPlaces();
  if (food.length && food.some((place) => !app.said[place.id])) {
    if (yesPlaces(app).length >= MAX_PLACES) {
      for (const place of food) app.said[place.id] = "no";
      clearTimeout(timer);
      app.step = "food";
      app.foodFull = true;
      render();
      timer = setTimeout(() => { app.foodFull = false; placesDone(); }, 1000);
      return;
    }
    askFood();
    return;
  }
  placesDone();
}

function askFood() {
  clearTimeout(timer);
  app.view = "plan";
  app.step = "food";
  app.foodFull = false;
  render();
}

// One place to eat is Yes and the others No; "No food stop" (id null) is No for all of them.
function sayFood(id) {
  app.placeNote = null;
  for (const place of foodPlaces()) app.said[place.id] = place.id === id ? "yes" : "no";
  placesDone();
}

function goToPlace(index) {
  clearTimeout(timer);
  app.view = "plan";
  app.step = "choose";
  app.at = Math.min(index, app.candidates.length - 1);
  render();
}

// Yes puts the place on her list, No dims it; she can change her mind by pressing the place on the map.
// The next place comes by itself; with five Yes, or when every place is answered, the line goes on by itself.
function sayPlace(id, choice) {
  app.placeNote = null;
  if (choice === "yes" && app.said[id] !== "yes" && yesPlaces(app).length >= MAX_PLACES) { placesDone(); return; }
  app.said[id] = choice;
  if (isFood(app.candidates.find((place) => place.id === id))) { placesDone(); return; }
  if (yesPlaces(app).length >= MAX_PLACES) { for (const place of foodPlaces()) if (!app.said[place.id]) app.said[place.id] = "no"; placesDone(); return; }
  nextChoice(app.at + 1);
}

function placesDone() {
  if (yesPlaces(app).length < MIN_PLACES) {
    // A route needs two places: the ones answered No are asked again.
    for (const place of app.candidates) if (app.said[place.id] === "no") delete app.said[place.id];
    app.placeNote = () => t("I need at least two places for a route. Here they are again.");
    nextChoice(0);
    return;
  }
  if (Object.keys(remembered()).length) { app.step = "remember"; render(); return; }
  askContext();
}

// ---- what the guide should know: one open question ------------------------------------------

// "Anything I should know?" She tells it in her own words. On a saved run nothing can be sent: the saved
// answer is shown as if typed, and the line goes on.
function askContext() {
  clearTimeout(timer);
  app.view = "plan";
  app.step = "context";
  app.context = { busy: false, typed: null, said: null };
  if (app.source.kind !== "live") {
    const saved = app.run?.profile && typeof app.run.profile === "object" ? app.run.profile : {};
    app.answers = { wish: saved.wish ?? null };
    for (const question of QUESTIONS) if (question.answers.some(([, value]) => value === saved[question.key])) app.answers[question.key] = saved[question.key];
    const saidBack = app.run?.understood && typeof app.run.understood[app.lang] === "string" ? app.run.understood[app.lang] : null;
    const words = saidBack || understood();
    app.context = { busy: false, typed: typeof app.run?.context?.text === "string" ? app.run.context.text : words, said: words };
    render();
    timer = setTimeout(askMissing, 1800);
    return;
  }
  if (app.told) {      // she said it in her request: it is not asked again, the guide says back what it understood
    const told = app.told.profile;
    app.answers = { wish: typeof told.wish === "string" && told.wish ? told.wish : null };
    for (const question of QUESTIONS) {
      if (!app.told.missing.includes(question.key) && question.answers.some(([, value]) => value === told[question.key])) app.answers[question.key] = told[question.key];
    }
    const said = app.told.said && typeof app.told.said[app.lang] === "string" ? app.told.said[app.lang] : null;
    const words = said || understood();
    if (words) {
      app.context = { busy: false, typed: app.told.text, said: words };
      render();
      timer = setTimeout(askMissing, 3600);
      return;
    }
  }
  render();
}

// What was understood, as one sentence: "Short walks, no stairs, sitting down often."
function understood() {
  const known = Object.fromEntries(QUESTIONS.filter((question) => app.answers[question.key]).map((question) => [question.key, app.answers[question.key]]));
  if (!Object.keys(known).length) return null;
  const words = profileWords(known).split(", ").filter((part) => !/unknown|알 수 없음/.test(part)).join(", ");
  return words ? `${words.charAt(0).toUpperCase()}${words.slice(1)}.` : null;
}

// Live: her words go to the agent as the "context" turn; the state then holds what could be told from them
// and what could not. When the turn is not answered, nothing was understood and the three things are asked.
async function tellContext(text) {
  app.context = { busy: true, typed: text, said: null };
  render();
  let profile = {};
  try {
    const { state } = await sendTurn(app.source.api, app.sessionId, { step: "context", text }, app.source.root);
    takeState(state);
    profile = state.profile && typeof state.profile === "object" ? state.profile : {};
    const missing = Array.isArray(state.missing) ? state.missing : Array.isArray(profile.missing) ? profile.missing : null;
    if (missing) for (const key of missing) delete profile[key];
  } catch {
    profile = {};      // nothing could be told from her words: they are kept as her wish and the questions are asked
  }
  app.answers = { wish: typeof profile.wish === "string" && profile.wish ? profile.wish : text };
  for (const question of QUESTIONS) if (question.answers.some(([, value]) => value === profile[question.key])) app.answers[question.key] = profile[question.key];
  app.context = { busy: false, typed: text, said: understood() };
  render();
  timer = setTimeout(askMissing, app.context.said ? 1600 : 0);
}

// Only what is still open is asked, one thing at a time. With nothing open the route is built.
function askMissing() {
  clearTimeout(timer);
  app.asking = QUESTIONS.filter((question) => !app.answers[question.key]);
  app.q = 0;
  if (!app.asking.length) { makeRoute(); return; }
  app.step = "ask";
  render();
}

// ---- the route -----------------------------------------------------------------------------

async function makeRoute() {
  clearTimeout(timer);
  app.retry = makeRoute;
  app.view = "plan";
  app.step = "working";
  app.workingText = t("Building your walking route");
  if (app.source.kind !== "live") {
    if (!app.run?.spatial_model) { fail(new Error(t("A route needs the live agent, and no saved route is here to show."))); return; }
    replay("route", rowsFromAudit(routeRows(app.audit)), () => showRoute(app.run.spatial_model));
    return;
  }
  app.progress = newProgress("live", "route");
  render();
  try {
    const progress = app.progress;
    const picks = yesPlaces(app).map((place) => place.id);
    const { state } = await sendTurn(app.source.api, app.sessionId, { step: "route", picks, profile: buildProfile() }, app.source.root, (event) => {
      if (takeEvent(progress, event) && app.step === "working") render();
    });
    takeState(state);
    if (!state.spatial_model) throw new Error(t("The agent finished without a route in the session state."));
    app.routeNote = state.route_note && typeof state.route_note === "object" ? state.route_note : null;
    showRoute(state.spatial_model);
  } catch (error) {
    fail(error);
  }
}

function showRoute(model) {
  if (!model || !Array.isArray(model.stops) || !model.stops.length) { fail(new Error(t("The run has no route to show."))); return; }
  app.model = model;
  app.routeSub = "note";      // the route in sentences comes first, then the final map
  app.view = "route";
  render();
}

// "Forget this" in the knowledge graph. The memory is read again after the turn and everything is drawn from what is left.
async function forget(factId) {
  const fact = findFact(app.memory, factId);
  if (!fact || app.source.kind !== "live" || !app.sessionId || app.know.busy) return;
  const name = factName(fact);
  app.know = { ...app.know, busy: true, confirm: null, message: null };
  renderKnow();
  let focus = "panel";
  try {
    const { state, results } = await sendTurn(app.source.api, app.sessionId, { step: "forget", fact_id: factId }, app.source.root);
    takeState(state);
    const outcome = forgetOutcome(results, !findFact(app.memory, factId));
    if (outcome.kind === "done") {
      if (fact.group === "answers") delete app.answers[fact.key];
      const text = fact.group === "answers" ? t("Forgotten: {name}. I will ask you about it again.", { name }) : t("Forgotten: {name}.", { name });
      app.know = { selected: null, confirm: null, busy: false, message: { kind: "done", text } };
      focus = "close";
    } else {
      app.know = { ...app.know, busy: false, message: { kind: "refused", text: outcome.text } };
    }
  } catch (error) {
    app.know = { ...app.know, busy: false, message: { kind: "refused", text: t("Not forgotten. {why}", { why: readable(error) }) } };
  }
  renderKnow(focus);
}

// Everything the page keeps from a session state: the audit rows and her memory.
// A state that was read and has no memory in it means the agent remembers nothing about her.
function takeState(state) {
  if (Array.isArray(state?.audit)) app.audit = state.audit;
  takeWeather(state);
  app.memory = readMemory(state) ?? { facts: [], feedback: [] };
}

function readable(error) {
  if (error instanceof TypeError) return t("The agent server could not be reached. Check that it is running and allows this page.");
  return error?.message ? String(error.message) : t("Unknown error.");
}

// The wordmark: back to the text field. What was chosen and told on this page is dropped; her memory is not touched.
function startOver() {
  clearTimeout(timer);
  if (knowDialog.open) knowDialog.close();
  Object.assign(app, { view: "plan", step: "landing", landingNote: null, said: {}, at: 0, placeNote: null, answers: {}, asking: [], q: 0,
    context: { busy: false, typed: null, said: null }, model: null, routeSub: "note", progress: null, copied: null });
  render();
}

// ---- drawing --------------------------------------------------------------------------------

function isNarrow() {
  return matchMedia("(max-width: 699px)").matches;
}

function markTabs() {
  for (const tab of document.querySelectorAll("#view-tabs [data-go]")) {
    tab.setAttribute("aria-pressed", (tab.dataset.go === "know") === knowDialog.open ? "true" : "false");
  }
  markKnowNew();
}

function render() {
  setLang(app.lang);
  document.documentElement.lang = app.lang;
  for (const node of document.querySelectorAll("[data-t]")) node.textContent = t(node.dataset.t);
  document.getElementById("lang").setAttribute("aria-label", t("Language"));
  document.getElementById("view-tabs").setAttribute("aria-label", t("View"));
  document.getElementById("start-over").setAttribute("aria-label", t("Gilmate: start over"));
  if (!app.model && app.view !== "plan") app.view = "plan";
  stage.dataset.view = app.view;
  stage.dataset.step = app.view === "plan" ? app.step : "route";
  stage.dataset.map = app.mapDrawn ? "drawn" : "none";
  document.title = placeLine();
  drawMark(document.getElementById("weather"), app.dayMark);
  markTabs();
  for (const button of document.querySelectorAll("#lang [data-lang]")) {
    button.setAttribute("aria-pressed", button.dataset.lang === app.lang ? "true" : "false");
  }

  // What was focused is rebuilt with the screen; the same control gets the focus back when it has an id.
  const focused = document.activeElement?.id && content.contains(document.activeElement) ? document.activeElement.id : null;
  clear(content).append(app.view === "plan" ? renderPlan(app, act) : renderRoute(app, act));
  if (focused) document.getElementById(focused)?.focus({ preventScroll: true });
  showOnMap();
  lookAt();
}

// Where she is, as the page's title: nothing sits under the wordmark.
function placeLine() {
  const area = areaWords(app.area?.name ? app.area : entryOf(app.areaKey)).place;
  if (app.view === "route" && app.model) {
    const total = totalDistance(app.model);
    const from = orderedStops(app.model)[0]?.name ?? t("Name unknown");
    return `Gilmate · ${total === null ? t("{area} · from {from}", { area, from }) : t("{area} · from {from}, {distance} on foot", { area, from, distance: metres(total) })}`;
  }
  return `Gilmate · ${area}`;
}

// Tells the map what to draw: the places to choose from, or the route. Only when that changed.
function showOnMap() {
  if (!map.drawn) return;
  const onRoute = app.view === "route" && app.model;
  const making = reached();
  // On the landing screen the saved run's own route is the backdrop, still and without words.
  const backdrop = !onRoute && app.step === "landing" ? app.run?.spatial_model ?? null : null;
  const choosing = !onRoute && app.step !== "landing" && !making;
  const current = choosing && app.step === "choose" ? app.candidates[app.at]?.id : null;
  const show = onRoute ? { places: false, dots: false, spots: false } : making ?? { places: true, dots: app.step !== "landing", spots: choosing };
  const key = JSON.stringify([onRoute ? "route" : backdrop ? "backdrop" : app.step === "landing" ? "landing" : "places", app.lang, onRoute ? app.model.generated_at : null, show,
    choosing ? app.candidates.map((place) => app.said[place.id] ?? "") : null, current, app.candidates.length, app.streetPhotos.length, app.restSpots.length]);
  if (key === app.mapKey) return;
  app.mapKey = key;
  map.setRoute(onRoute ? app.model : backdrop, { upright: Boolean(onRoute) });
  // Before the route every bench the map knows is a small mark; on the route the benches of the walks carry their name.
  map.setSpots(show.spots ? app.restSpots : []);
  map.setDots(show.dots ? app.streetPhotos : []);
  // On the landing screen the places are there as quiet dots; they become buttons with names once the map is made.
  map.setPlaces(show.places && !backdrop ? app.candidates.map((place) => {
    const said = app.said[place.id] ?? null;
    const kind = pick(place.kind, app.lang).text === "unknown" ? kindWords(place, app.lang).text : pick(place.kind, app.lang).text;
    const words = said === "yes" ? t("Yes, on your list") : said === "no" ? t("No, not this time") : t("Not answered yet");
    return { id: place.id, name: place.name ?? t("Name unknown"), category: place.category, lat: place.place?.lat, lon: place.place?.lon,
      state: said, current: place.id === current, label: `${place.name ?? t("Name unknown")}, ${kind}. ${words}` };
  }) : [], act.openPlace, { quiet: app.step === "landing" });
}

// Tells the map where to look and which parts of the screen are covered: the top bar, the column at the left
// edge (on a phone: the sheet at the bottom) and the guide's dock. The subject lands in the free part.
function lookAt() {
  if (!map.drawn) return;
  const width = window.innerWidth;
  const height = window.innerHeight;
  const top = bar.offsetHeight + 8;
  const narrow = isNarrow();
  const dock = content.querySelector(".dock");
  const column = narrow ? null : content.querySelector(".work-content")?.getBoundingClientRect();
  // On a phone the dock is a full-width stack; on a wide screen the card stands at the left and the dock is the small group in the middle.
  const tops = dock ? [...dock.querySelectorAll(narrow ? ".work-content, .work-actions, .dialogue" : ".work-actions, .dialogue")].map((part) => part.getBoundingClientRect().top) : [];
  const bottom = Math.max(16, height - Math.min(height, ...tops) + 12);
  const left = column ? column.right + 16 : 16;
  if (app.view === "route" && app.model) { map.focus(null, { top, right: 16, bottom, left }); return; }
  if (app.step === "landing") {
    // The words stand on the left, the map shows on the right; on a phone it lies under the words and the card, above the guide.
    const under = Math.max(top, ...[...content.querySelectorAll(".search, .ready-card")].map((part) => part.getBoundingClientRect().bottom)) + 12;
    const guide = content.querySelector(".dialogue")?.getBoundingClientRect().top ?? height;
    map.focus(null, narrow ? { top: Math.min(under, height - 200), right: 0, bottom: Math.max(16, height - guide + 8), left: 0 } : { top: 96, right: 24, bottom: 150, left: width * 0.48 });
    return;
  }
  const place = app.step === "choose" ? app.candidates[app.at] : null;
  const headBottom = content.querySelector(".making-head")?.getBoundingClientRect().bottom ?? 0;
  map.focus(place ? { place: place.id } : null, { top: Math.max(top, headBottom + 16), right: 16, bottom, left });
}

// ---- "What Gilmate knows about you" ---------------------------------------------------------

// The graph starts empty with every visit and fills as she goes: of her memory it gets only what this visit
// has reached (memory.js, reachedMemory). The stored memory itself is kept as it is.
const knowSeen = new Set();      // the facts she has seen in the graph, so the tab can say how many are new
function knowMemory() {
  return reachedMemory(app.memory, { answers: app.answers, yes: yesPlaces(app).map((place) => place.name), route: Boolean(app.model), live: app.source.kind === "live" });
}

// A small number on the "Knowledge graph" tab: the facts added since she last looked.
function markKnowNew() {
  const ids = (knowMemory()?.facts ?? []).map((fact) => String(fact.id));
  for (const id of [...knowSeen]) if (!ids.includes(id)) knowSeen.delete(id);
  if (knowDialog.open) for (const id of ids) knowSeen.add(id);
  const fresh = ids.filter((id) => !knowSeen.has(id)).length;
  const tab = document.getElementById("know-open");
  if (fresh) tab.dataset.count = String(fresh); else delete tab.dataset.count;
}

function openKnow(selected = null) {
  app.know = { selected, confirm: null, busy: false, message: null };
  // Live, after the route: a "too far" given on the phone is in the agent's memory, so it is read again.
  if (app.source.kind === "live" && app.sessionId && app.model) readState(app.source.api, app.sessionId).then((state) => { takeState(state); renderKnow(); }).catch(() => {});
  if (!knowDialog.open) knowDialog.showModal();
  markTabs();
  renderKnow(selected ? "panel" : null);
}

function renderKnow(focus = null) {
  if (!knowDialog.open) return;
  const live = app.source.kind === "live";
  const canForget = live && Boolean(app.sessionId);
  know.render({
    memory: knowMemory(), memoryNote: app.memoryNote(), today: app.today, lang: app.lang, source: app.source, model: app.model,
    ...app.know, canForget,
    forgetOff: live ? t("The agent could not be reached, so nothing can be forgotten right now.")
      : app.source.kind === "dev" ? t("Forgetting needs the live agent. This is a development sample, so the button is switched off.")
      : t("Forgetting needs the live agent. This is a saved run, so the button is switched off."),
  });
  // On a phone the panel lies over the lower part of the map: leave room and bring the pressed circle above it.
  const pressed = app.know.selected ? knowBody.querySelector(`[data-node="${CSS.escape(app.know.selected)}"]`) : null;
  if (pressed && isNarrow()) {
    knowBody.dataset.sheet = "true";
    knowBody.style.setProperty("--sheet-h", `${knowSide.offsetHeight}px`);
    pressed.scrollIntoView({ block: "start" });
  } else {
    delete knowBody.dataset.sheet;
  }
  const target = focus === "panel" ? knowSide.querySelector(".know-panel")
    : focus === "keep" ? knowSide.querySelector("#forget-no")
    : focus === "forget" ? knowSide.querySelector("#forget")
    : focus === "close" ? document.getElementById("know-close")
    : focus?.startsWith("node:") ? knowBody.querySelector(`[data-node="${CSS.escape(focus.slice(5))}"]`) : null;
  target?.focus({ preventScroll: focus !== "panel" });
}

function renderAudit() {
  const body = clear(document.getElementById("audit-body"));
  const rows = app.audit;
  if (!rows.length) {
    body.append(el("p", { class: "plain-note" }, app.source.kind === "live"
      ? t("Nothing yet. The list fills after the agent's first turn.")
      : t("No record of the agent's steps is available.")));
    return;
  }
  const count = (decision) => rows.filter((row) => row.decision === decision).length;
  const other = rows.length - count("allowed") - count("withheld") - count("blocked");
  // A node list's own append() writes the word "null" for a missing part, so the sample line is added only when there is one.
  if (app.source.kind === "dev") body.append(el("p", { class: "audit-sample" }, t("Development sample. These rows are invented, no agent ran.")));
  body.append(
    el("p", { class: "audit-sum" },
      t(rows.length === 1 ? "1 step recorded: {allowed} allowed, {withheld} withheld, {blocked} blocked." : "{count} steps recorded: {allowed} allowed, {withheld} withheld, {blocked} blocked.",
        { count: rows.length, allowed: count("allowed"), withheld: count("withheld"), blocked: count("blocked") }),
      other ? ` ${t("{other} with an unknown decision.", { other })}` : null),
    el("p", { class: "audit-sum" }, t("Withheld: a search result was kept away from the agent. Blocked: a rule refused the step.")));
  const list = el("ol", {});
  for (const row of rows) {
    const decision = ["allowed", "withheld", "blocked"].includes(row.decision) ? row.decision : "unknown";
    const word = t({ allowed: "Allowed", withheld: "Withheld", blocked: "Blocked", unknown: "Decision unknown" }[decision]);
    // A row's detail is a plain string, or one sentence in both languages (CONTRACT.md section 7.4).
    const detail = row.detail === null || row.detail === undefined || row.detail === "" ? null
      : typeof row.detail === "string" ? row.detail
      : row.detail.en || row.detail.ko ? pick(row.detail, app.lang).text : JSON.stringify(row.detail);
    list.append(el("li", { class: "audit-row", "data-decision": decision },
      el("span", { class: "audit-time" }, clock(row.t, { seconds: true })),
      el("div", { class: "audit-what" },
        el("b", {}, row.agent ?? t("agent unknown")),
        el("span", { class: "audit-tool" }, row.tool ?? t("tool unknown")),
        el("span", { class: "verdict", "data-decision": decision }, word)),
      el("p", { class: "audit-more" }, row.rule ? t("Rule: {rule}", { rule: row.rule }) : decision === "allowed" ? t("No rule named.") : t("Rule unknown.")),
      detail ? el("p", { class: "audit-more" }, detail) : null));
  }
  body.append(list);
}
