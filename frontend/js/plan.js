// The first half of the line, in the order of CONTRACT.md section 7: the landing screen with its text field,
// the map being made, the places one at a time with Yes and No, then the questions about walking, stairs and
// sitting down: one open question in her own words (or "Still true?" when the answers are remembered), and only
// what her words left open is asked with answers to press. The route follows by itself.
// Every screen is the map with the guide docked at its bottom, and as few things to press as it can have.

import { el } from "./dom.js";
import { pick, CATEGORY_SHORT } from "./text.js";
import { accessChip, composer, icon, choices, quiet, dock } from "./parts.js";
import { LIMIT, answerLines, factName, factState } from "./memory.js";
import { groupSteps, stepWords, stepDots } from "./progress.js";
import { dayWeather } from "./model.js";
import { t, LANDING } from "./words.js";

// What can be typed to open a place there is a map for.
export const EXAMPLE = LANDING.example;

/** An area's name as the page says it: "Hongdae, Seoul" is the place "Hongdae" in the city "Seoul". */
export function areaWords(area) {
  const [place, ...rest] = String(area?.name ?? "").split(",").map((part) => part.trim()).filter(Boolean);
  return { place: place ? t(place) : t("Name unknown"), city: rest.length ? t(rest.join(", ")) : null };
}

export const QUESTIONS = [
  { key: "walk", ask: "How far can you walk at a time?", careful: "short",
    answers: [["Short walks", "short"], ["A while", "medium"], ["No problem", "long"]] },
  { key: "stairs", ask: "Are stairs a problem for you?", careful: "avoid",
    answers: [["Yes, avoid them", "avoid"], ["A few are fine", "few"], ["No problem", "ok"]] },
  { key: "rest", ask: "Do you need to sit down along the way?", careful: "often",
    answers: [["Often", "often"], ["Sometimes", "sometimes"], ["Not really", "rarely"]] },
];

export const MIN_PLACES = 2;
export const MAX_PLACES = 5;

/** The places of a run in the shape of section 7.2. An older run has `options`; they are read as places without photos. */
export function readCandidates(run) {
  if (Array.isArray(run?.candidates)) return run.candidates.filter((place) => place && typeof place === "object" && place.id);
  if (!Array.isArray(run?.options)) return [];
  return run.options.filter((option) => option && option.id).map((option) => ({ ...option, kind: null, description: option.summary ?? null, photos: [] }));
}

export function yesPlaces(app) {
  return app.candidates.filter((place) => app.said[place.id] === "yes");
}

/** What a place is, in words: its kind from the data, otherwise its group. */
export function kindWords(place, lang) {
  const kind = pick(place.kind, lang);
  if (kind.text !== "unknown") return kind;
  return { text: t(CATEGORY_SHORT[place.category] ?? "Place"), lang };
}

/** At most `count` sentences of a text: a card says little. */
export function sentences(text, count = 2) {
  const parts = String(text).match(/[^.!?。]+[.!?。]+(\s|$)|[^.!?。]+$/g) ?? [String(text)];
  return parts.slice(0, count).join("").trim();
}

export function renderPlan(app, act) {
  if (app.step === "landing") return renderLanding(app, act);
  if (app.step === "making") return renderMaking(app, act);
  if (app.step === "choose") return renderPlace(app, act);
  if (app.step === "remember") return renderRemembered(app, act);
  if (app.step === "context") return renderContext(app, act);
  if (app.step === "ask") return renderAsk(app, act);
  if (app.step === "working") return renderWorking(app);
  return renderError(app, act);
}

// ---- 1. Landing: the text field and the last runs -----------------------------------------------

let typedOnLanding = null;      // null: she has not changed the field, so it holds the demo's sentence

function renderLanding(app, act) {
  const none = app.none ? app.noneReason() : null;
  // The field comes filled in with the demo's sentence, in the page's language, so one press makes the map.
  // What she types instead is kept while the page draws itself anew.
  const search = composer({ placeholder: t(EXAMPLE), label: t("Where would you like to go?"), send: "search", sendLabel: t("Make the map"), onSend: act.search,
    multiline: true, value: typedOnLanding ?? t(LANDING.demo), onInput: (words) => { typedOnLanding = words; } });
  search.classList.add("search");
  search.id = "search";

  // One card per area with a saved run (CONTRACT.md section 8.1). A card shows a photo of its area only when
  // the data holds one. No stand-in picture.
  const cards = app.areas.filter((area) => area.run).map((area, index) => {
    const held = area.photo ?? (area.key === app.areaKey ? app.area?.photo : null);
    const photo = held && typeof held === "object" && (held.thumb_url || held.url) ? held : null;
    const words = areaWords(area);
    return el("button", { type: "button", class: "ready-card", id: index === 0 ? "start-button" : `start-${area.key}`, "data-photo": photo ? true : null, disabled: Boolean(none), on: { click: () => act.open(area.key) } },
      photo ? el("img", { src: photo.thumb_url || photo.url, alt: t("Photo of {area}", { area: words.place }), loading: "eager", decoding: "async" }) : null,
      el("span", { class: "ready-label" },
        el("span", { class: "ready-name" }, words.place),
        words.city ? el("span", { class: "ready-sub" }, words.city) : null));
  });
  return el("section", { class: "screen landing" },
    el("div", { class: "landing-main" },
      el("h1", {}, LANDING.headline.map((line) => el("span", {}, t(line), " "))),
      search,
      el("p", { class: "start-label" }, t("Last runs")),
      el("div", { class: "ready-row" }, cards)),
    dock({ line: none ?? (app.landingNote ? app.landingNote() : t(LANDING.bubble)), lineAttrs: { role: "status" } }));
}

// ---- 2. The map being made: the guide tells one step at a time ----------------------------------

// What the data holds, for the steps' sentences and the line under the title. Only Mapillary's and KartaView's
// photos are street-level; photos from Wikimedia Commons with coordinates are not called that.
export function knownCounts(app) {
  const sources = app.counts?.photo_sources && typeof app.counts.photo_sources === "object" ? app.counts.photo_sources : null;
  const streetPhotos = sources ? (Number(sources.mapillary) || 0) + (Number(sources.kartaview) || 0)
    : app.streetPhotos.filter((photo) => photo.source === "mapillary" || photo.source === "kartaview").length;
  const day = dayWeather(app);
  return { places: app.candidates.length, streetPhotos, benches: app.restSpots.length, weather: day ? pick(day.worst?.text ?? day.summary, app.lang).text : null };
}

// The step that is running, as one sentence. Nothing else is on the screen: no list, no panel.
function narration(app) {
  const steps = groupSteps(app.progress);
  const at = app.progress.kind === "live" ? steps.length - 1 : Math.min(app.progress.at, steps.length - 1);
  return { steps, at, words: at >= 0 ? stepWords(steps[at], knownCounts(app)) : null };
}

function renderMaking(app, act) {
  const known = knownCounts(app);
  const replay = app.progress && app.progress.kind !== "live";
  const where = areaWords(app.area?.name ? app.area : app.areas.find((area) => area.key === app.areaKey));
  const told = app.progress ? narration(app) : { steps: [], at: -1, words: null };
  // One line under the title, with what the data holds. Live it is there once the places are.
  const countsLine = app.candidates.length ? [
    known.places === 1 ? t("1 place") : t("{count} places", { count: known.places }),
    known.streetPhotos ? (known.streetPhotos === 1 ? t("1 street photo") : t("{count} street photos", { count: known.streetPhotos })) : t("No street photos available"),
    known.benches ? (known.benches === 1 ? t("1 bench") : t("{count} benches", { count: known.benches })) : null,
  ].filter(Boolean).join(" · ") : null;

  return el("section", { class: "screen making" },
    el("header", { class: "making-head" },
      el("h1", {}, where.place),
      where.city ? el("p", { class: "making-where" }, where.city) : null,
      countsLine ? el("p", { class: "making-counts", id: "making-counts" }, countsLine) : null),
    replay ? el("button", { type: "button", class: "quiet making-skip", id: "making-skip", on: { click: act.skipReplay } }, icon("skip"), el("span", {}, t("Skip"))) : null,
    dock({ line: told.words ?? app.workingText, lineAttrs: { role: "status" }, under: stepDots(told.steps.length, told.at), working: true }));
}

// ---- 3. One place at a time: Yes or No ----------------------------------------------------------

function renderPlace(app, act) {
  const place = app.candidates[app.at];
  const said = app.said[place.id];
  return el("section", { class: "screen" }, dock({
    content: placeCard(app, place),
    actions: choices([
      { label: t("Yes"), lead: true, id: "place-yes", pressed: said === "yes", onPick: () => act.sayPlace(place.id, "yes") },
      { label: t("No"), id: "place-no", pressed: said === "no", onPick: () => act.sayPlace(place.id, "no") },
    ], { label: t("Your answer"), row: true }),
    line: app.placeNote ? app.placeNote() : t("Would you like to go to {name}?", { name: place.name ?? t("Name unknown") }),
    lineAttrs: { "aria-live": "polite" },
  }));
}

// The rating Python took from Google Maps (CONTRACT.md, the Places section), as one short line:
// "4.9 · 17,274 ratings on Google". Only the fact's own numbers; a place without that fact has no line.
function ratingLine(place) {
  const fact = (Array.isArray(place.facts) ? place.facts : []).find((item) => item && item.label === "Google Maps rating" && typeof item.value === "string" && item.value.trim());
  if (!fact) return null;
  const match = /^(\d(?:[.,]\d+)?) out of 5 \(([\d.,\s]+) ratings? on Google Maps\)$/.exec(fact.value.trim());
  if (!match) return fact.value.trim();
  return match[2].trim() === "1" ? t("{rating} · 1 rating on Google", { rating: match[1] }) : t("{rating} · {count} ratings on Google", { rating: match[1], count: match[2].trim() });
}

/** A short card: the photos, the name, what it is and its access in one grey line, and two sentences. */
function placeCard(app, place) {
  const kind = kindWords(place, app.lang);
  const description = pick(place.description, app.lang);
  const rating = ratingLine(place);
  return el("article", { class: "panel spot", "data-tone": "dark", "aria-label": place.name ?? t("Name unknown") },
    photoStrip(app, place),
    el("div", { class: "spot-head" },
      el("p", { class: "meta" }, t("Place {n} of {count}", { n: app.at + 1, count: app.candidates.length })),
      el("h2", { class: "title" }, place.name ?? t("Name unknown")),
      el("p", { class: "spot-kind" }, el("span", { lang: kind.lang }, kind.text), " · ", accessChip(place.place?.access)),
      rating ? el("p", { class: "spot-rating" }, rating) : null),
    description.text === "unknown" ? el("p", { class: "spot-text", "data-none": true }, t("No description found."))
      : el("p", { class: "spot-text", lang: description.lang }, sentences(description.text)));
}

/**
 * The photos of a place, one at a time, with next and previous. Who took each, when and under which licence is
 * in CREDITS.md at the root of the repository. A place without one says "No photo found".
 */
export function photoStrip(app, place) {
  const photos = (Array.isArray(place.photos) ? place.photos : []).filter((photo) => photo && (photo.thumb_url || photo.url));
  if (!photos.length) {
    return el("div", { class: "photo-none" }, icon("noPhoto"), el("span", {}, t("No photo found")));
  }
  const at = Math.min(app.photoAt[place.id] ?? 0, photos.length - 1);
  const track = el("div", { class: "photo-track", tabindex: photos.length > 1 ? "0" : null, "aria-label": t("Photos of {name}", { name: place.name ?? t("this place") }) },
    photos.map((photo, index) => {
      const image = el("img", { src: photo.thumb_url || photo.url, alt: t("Photo {n} of {count}: {name}", { n: index + 1, count: photos.length, name: place.name ?? t("this place") }),
        loading: index === 0 ? "eager" : "lazy", decoding: "async", draggable: "false" });
      const figure = el("figure", { class: "photo" }, image);
      image.addEventListener("error", () => figure.replaceChildren(el("p", { class: "photo-broken" }, icon("noPhoto"), t("This photo could not be loaded."))));
      return figure;
    }));
  const count = el("span", { class: "photo-count" });
  const prev = el("button", { type: "button", class: "photo-nav", "data-side": "prev", "aria-label": t("Photo before"), on: { click: () => go(-1) } }, icon("chevronLeft"));
  const next = el("button", { type: "button", class: "photo-nav", "data-side": "next", "aria-label": t("Next photo"), on: { click: () => go(1) } }, icon("chevronRight"));
  let now = at;

  function show(index) {
    now = Math.max(0, Math.min(photos.length - 1, index));
    app.photoAt[place.id] = now;
    count.textContent = `${now + 1} / ${photos.length}`;
    prev.disabled = now === 0;
    next.disabled = now === photos.length - 1;
  }
  function go(step) {
    show(now + step);
    track.scrollTo({ left: now * track.clientWidth, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  // A swipe moves the strip by itself; the counter follows the photo that came to rest.
  let settle = 0;
  track.addEventListener("scroll", () => {
    clearTimeout(settle);
    settle = setTimeout(() => { if (track.clientWidth) show(Math.round(track.scrollLeft / track.clientWidth)); }, 90);
  });
  show(at);
  if (at > 0) requestAnimationFrame(() => { track.scrollLeft = at * track.clientWidth; });

  return el("div", { class: "photos" }, el("div", { class: "photo-frame" }, track, photos.length > 1 ? [prev, next, count] : null));
}

// ---- 4. Walking, stairs, sitting down: "Still true?" or the questions --------------------------

// The answers are in the memory: say them and ask "Still true?" instead of the questions.
function renderRemembered(app, act) {
  const limit = app.memory.facts.find((fact) => fact.key === LIMIT);
  return el("section", { class: "screen" }, dock({
    content: el("dl", { class: "panel remembered", "data-tone": "dark" },
      el("p", { class: "meta" }, t("From last time")),
      answerLines(app.memory, QUESTIONS).map((line) => el("div", {}, el("dt", {}, line.topic), el("dd", {}, line.words))),
      limit ? el("div", {}, el("dt", {}, t("From your taps")),
        el("dd", {}, factName(limit), el("small", {}, factState(app.memory, limit, app.today).short))) : null),
    actions: choices([
      { label: t("Yes"), lead: true, id: "still-yes", onPick: act.stillTrue },
      { label: t("Change"), id: "still-change", onPick: act.changeAnswers },
    ], { label: t("Still true?") }),
    line: t("I remember what you told me. Still true?"),
    lineAttrs: { "aria-live": "polite" },
  }));
}

// One open question, answered in her own words. What was understood is said back in one sentence.
function renderContext(app, act) {
  const context = app.context;
  const live = app.source.kind === "live";
  return el("section", { class: "screen" }, dock({
    line: context.busy ? t("Reading what you told me")
      : context.said ?? t("Anything I should know? How far you like to walk, stairs, how often you need to sit."),
    lineAttrs: { "aria-live": "polite" },
    working: context.busy,
    under: composer({
      placeholder: t("I have a bad knee and need to sit every ten minutes"), label: t("Tell me in your own words"),
      // On a saved run nothing can be sent: the saved answer stands in the field as if typed.
      value: context.typed, disabled: context.busy || !live || Boolean(context.said), onSend: act.tellContext,
    }),
  }));
}

// What her words left open, one thing at a time, each with its answers.
function renderAsk(app, act) {
  const question = app.asking[app.q];
  return el("section", { class: "screen" }, dock({
    actions: choices(question.answers.map(([label, value], index) => ({
      label: t(label), lead: index === 0, onPick: () => act.answer(question.key, value),
    })), { label: t(question.ask) }),
    line: t(question.ask),
    lineAttrs: { "aria-live": "polite" },
  }));
}

// ---- 5. The route being made: nothing to press --------------------------------------------------

function renderWorking(app) {
  const told = app.progress ? narration(app) : { steps: [], at: -1, words: null };
  return el("section", { class: "screen" },
    dock({ line: told.words ?? app.workingText, lineAttrs: { role: "status" }, under: stepDots(told.steps.length, told.at), working: true }));
}

function renderError(app, act) {
  return el("section", { class: "screen" }, dock({
    actions: choices([{ label: t("Try again"), lead: true, id: "try-again", onPick: act.retry }]),
    line: t("That did not work: {why}", { why: app.error }),
    lineAttrs: { role: "alert" },
  }));
}
