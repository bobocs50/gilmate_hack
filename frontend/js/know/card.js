// The small card that opens beside a pressed dot: what it knows, where from and when, what it changes,
// and "Forget this". Words only; know.js puts it on the page and keeps it beside its dot.

import { el } from "../dom.js";
import { metres, clock, pick } from "../text.js";
import { t } from "./words.js";
import { GROUPS, OTHER, LIMIT, groupFacts, factName, factKind, factState, isLearned, tooFarTaps, findFact } from "../memory.js";

export const GUIDE = "guide";

/** The inside of the card for view.selected, or null when nothing is pressed. */
export function cardFor(view) {
  const { memory, selected } = view;
  if (!selected) return null;
  const close = el("button", { type: "button", class: "know-x", id: "know-panel-close", "aria-label": t("Close this card"), on: { click: () => view.act.select(null) } },
    el("span", { "aria-hidden": "true" }, "×"));
  const head = (meta, title) => [
    el("div", { class: "know-card-head" }, el("p", { class: "know-meta" }, meta), close),
    title ? el("h3", { class: "know-title" }, title) : null,
  ];

  if (selected === GUIDE) {
    const count = memory ? memory.facts.length : 0;
    return { label: t("About Gilmate"), parts: [
      head(t("The guide"), "Gilmate"),
      el("p", { class: "know-text" }, memory
        ? (count === 1 ? t("I keep 1 thing about you, so I do not have to ask you twice.") : t("I keep {count} things about you, so I do not have to ask you twice.", { count }))
        : view.memoryNote || t("Nothing is known about what I remember.")),
      el("p", { class: "know-text know-quiet" }, t("I only keep what you answered, what you picked and what you tapped after a walk. Nothing from web pages and nothing I made up.")),
    ] };
  }

  const group = [...GROUPS, OTHER].find((item) => item.id === selected);
  if (group) {
    const facts = groupFacts(memory).find((item) => item.group.id === group.id)?.facts ?? [];
    return { label: t(group.name), parts: [
      head(t("Where it comes from"), t(group.name)),
      el("p", { class: "know-text" }, t(group.about)),
      facts.length
        ? el("ul", { class: "know-list" }, facts.map((fact) => el("li", {},
            el("button", { type: "button", class: "know-row", on: { click: () => view.act.select(fact.id) } },
              el("span", {}, factName(fact)),
              el("span", { class: "know-quiet" }, factState(memory, fact, view.today).short || t("kept"))))))
        : el("p", { class: "know-text know-quiet" }, t("Nothing is kept here yet.")),
    ] };
  }

  const fact = findFact(memory, selected);
  if (!fact) {
    return { label: t("About this"), parts: [head(t("Not kept"), null), el("p", { class: "know-text" }, t("This is no longer in my memory."))] };
  }

  const state = factState(memory, fact, view.today);
  const stateWord = fact.status === "candidate" ? (state.stale ? t("Still learning · not in use today") : t("Still learning"))
    : fact.status === "kept" ? (isLearned(fact) ? t("Learned · kept") : t("Kept"))
    : t("State unknown");
  const stateKind = fact.status === "candidate" ? "candidate" : fact.status === "kept" ? (isLearned(fact) ? "learned" : "fact") : "unknown";

  return { label: t("About: {name}", { name: factName(fact) }), parts: [
    head(factKind(fact), factName(fact)),
    el("p", { class: "know-status", "data-kind": stateKind }, el("i", { "aria-hidden": "true" }), stateWord),
    el("dl", { class: "know-facts" },
      el("div", {}, el("dt", {}, t("What I know")), el("dd", {}, whatIKnow(fact)), el("dd", { class: "know-quiet" }, state.long)),
      el("div", {}, el("dt", {}, t("Where it comes from")),
        given(view, fact.evidence, t("Where this comes from was not saved.")),
        el("dd", { class: "know-quiet" }, t("Saved at {time}. The day is not saved with it.", { time: clock(fact.at) })),
        fact.key === LIMIT ? tapList(memory) : null),
      el("div", {}, el("dt", {}, t("What it changes")),
        given(view, fact.effect, t("What this changes was not saved.")),
        fact.key === LIMIT ? el("dd", { class: "know-quiet" }, changedWalks(view, fact)) : null)),
    forgetPart(view, fact),
  ] };
}

// A memory sentence as the backend saved it: a plain string is shown as given, an {en, ko} pair in the page's
// language. Nothing is translated here; a sentence that exists in one language only is shown in that one.
function given(view, field, missing) {
  const words = pick(field, view.lang);
  return words.text === "unknown" ? el("dd", {}, missing) : el("dd", { lang: words.lang, "data-given": true }, words.text);
}

function whatIKnow(fact) {
  if (fact.key === "wish") return fact.value ? t("Your wish, in your words: “{wish}”", { wish: fact.value }) : t("You have no wish.");
  if (fact.key === LIMIT) return t("{name} at a time.", { name: factName(fact) });
  if (fact.group === "picks" || fact.source === "pick") return t("You picked {name}.", { name: factName(fact) });
  return `${factName(fact)}.`;
}

// The taps the limit came from carry the day; the fact itself does not.
function tapList(memory) {
  const taps = tooFarTaps(memory);
  if (!taps.length) return el("dd", { class: "know-quiet" }, t("No “too far” tap is saved with it."));
  const words = taps.map((tap) => t("{day} at {time}, after a {distance} walk", {
    day: String(tap.at ?? "").slice(0, 10) || t("day unknown"), time: clock(tap.at), distance: metres(tap.distance_m),
  })).join("; ");
  return el("dd", { class: "know-quiet" }, taps.length === 1 ? t("Your “too far” tap: {taps}.", { taps: words }) : t("Your “too far” taps: {taps}.", { taps: words }));
}

function changedWalks(view, fact) {
  const ids = Array.isArray(fact.changed_legs) ? fact.changed_legs : [];
  if (!ids.length) return t("No walk of a route is marked as changed by it.");
  const stops = new Map((view.model?.stops ?? []).map((stop) => [stop.id, stop.name]));
  const legs = view.model?.legs ?? [];
  const walks = ids.map((id) => {
    const leg = legs.find((item) => item.id === id);
    if (!leg) return t("walk {id}", { id });
    return t("{from} to {to} ({distance})", { from: stops.get(leg.from) ?? t("a stop"), to: stops.get(leg.to) ?? t("the next stop"), distance: metres(leg.distance_m) });
  }).join("; ");
  return ids.length === 1 ? t("It changed how this walk was judged on the last route made with it: {walks}.", { walks })
    : t("It changed how these walks were judged on the last route made with it: {walks}.", { walks });
}

function forgetPart(view, fact) {
  const what = fact.group === "answers" ? t("I will ask you this question again before the next plan.")
    : fact.key === LIMIT ? t("The limit and the “too far” taps it came from are deleted. Your answer about walking counts again.")
    : fact.group === "picks" ? t("Only this note is deleted. A route that is already made stays as it is.")
    : t("This one thing is deleted.");
  const pill = (attrs, words) => el("button", { type: "button", class: "know-pill", ...attrs }, words);

  if (!view.canForget) {
    return el("div", { class: "know-forget" },
      pill({ id: "forget", disabled: true, "aria-describedby": "forget-note" }, t("Forget this")),
      el("p", { class: "know-quiet", id: "forget-note" }, view.forgetOff));
  }
  if (view.busy) {
    return el("div", { class: "know-forget" },
      pill({ id: "forget", disabled: true }, t("Forget this")),
      el("p", { class: "know-quiet", role: "status" }, t("Forgetting it")));
  }
  if (view.confirm === fact.id) {
    return el("div", { class: "know-forget", "data-ask": true },
      el("p", { class: "know-ask", id: "forget-note" }, t("Forget “{name}”? {what}", { name: factName(fact), what })),
      el("div", { class: "know-pills" },
        pill({ id: "forget-no", "data-quiet": true, on: { click: () => view.act.askForget(null) } }, t("Keep it")),
        pill({ id: "forget-yes", "data-strong": true, "aria-describedby": "forget-note", on: { click: () => view.act.forget(fact.id) } }, t("Yes, forget"))));
  }
  return el("div", { class: "know-forget" },
    pill({ id: "forget", "aria-describedby": "forget-note", on: { click: () => view.act.askForget(fact.id) } }, t("Forget this")),
    el("p", { class: "know-quiet", id: "forget-note" }, what));
}
