// The note's scroll fade is ported from Mercature by Glendon Chin (MIT), github.com/glendonC/mercature, src/ui/Chat.tsx: see THIRD_PARTY.md.
// The end of the line: the route in sentences, then the final map. The walk itself happens on the phone page;
// when its handoff module is there the final map offers "Start the route", otherwise there is nothing to press.

import { el } from "./dom.js";
import { pick, stairs, metres, hazardWord } from "./text.js";
import { choices, dock, icon } from "./parts.js";
import { orderedStops, legFrom, legHazards, legBenches, stopHazards, totalDistance } from "./model.js";
import { t, inLang } from "./words.js";

export function renderRoute(app, act) {
  const stops = orderedStops(app.model);
  const total = totalDistance(app.model);
  // First the route in sentences, as a note beside the map; then the final map with one thing to do.
  if (app.routeSub === "note") {
    return el("section", { class: "screen" }, dock({
      content: routeNote(app, act),
      actions: choices([{ label: t("Show my route"), lead: true, id: "route-map", onPick: act.showFinalMap }], { label: t("What next") }),
      line: t("Here is your route in sentences."),
      lineAttrs: { "aria-live": "polite" }, done: true,
    }));
  }
  return el("section", { class: "screen" }, dock({
    // The walk happens on the phone. Without the handoff this is simply the finished map.
    actions: typeof app.handoff === "function" ? choices([{ label: t("Start the route"), lead: true, id: "start-walk", onPick: act.startRoute }], { label: t("What next") }) : null,
    line: total === null ? t("Your route has {count} stops. The total distance is unknown.", { count: stops.length })
      : t("Your route is {distance} on foot, with {count} stops.", { distance: metres(total), count: stops.length }),
    lineAttrs: { "aria-live": "polite" },
  }));
}

/** The route in plain sentences, in the language of the tab. Only numbers and texts the spatial model holds. */
export function noteText(app, lang) {
  return inLang(lang, () => {
    const model = app.model;
    const stops = orderedStops(model);
    const total = totalDistance(model);
    const name = (stop) => stop?.name ?? t("Name unknown");
    const lines = [total === null
      ? t("{from} to {to}, {count} stops. The total distance is unknown.", { from: name(stops[0]), to: name(stops[stops.length - 1]), count: stops.length })
      : t("{from} to {to}, {distance} on foot, {count} stops.", { from: name(stops[0]), to: name(stops[stops.length - 1]), distance: metres(total), count: stops.length })];
    stops.forEach((stop, index) => {
      const leg = legFrom(model, stop.id);
      if (!leg) return;
      const parts = [t("{n}. {from} to {to}: {distance}, {stairs}.", { n: index + 1, from: name(stop), to: name(stops[index + 1]), distance: metres(leg.distance_m), stairs: stairs(leg.stairs) })];
      if (leg.kind !== "routed") parts.push(t("Not routed: a straight line, no mapped path."));
      const note = pick(leg.note, lang);
      if (note.text !== "unknown") parts.push(note.text);
      for (const hazard of legHazards(model, leg)) {
        const detail = pick(hazard.detail, lang);
        parts.push(`${hazardWord(hazard)}: ${detail.text === "unknown" ? t("no detail saved") : detail.text}`);
      }
      const benches = legBenches(model, leg).length;
      parts.push(benches === 0 ? t("No benches mapped on this stretch.") : benches === 1 ? t("1 bench mapped on this stretch.") : t("{count} benches mapped on this stretch.", { count: benches }));
      lines.push(parts.join(" "));
    });
    for (const stop of stops) {
      for (const hazard of stopHazards(model, stop)) {
        const detail = pick(hazard.detail, lang);
        lines.push(`${name(stop)}: ${hazardWord(hazard)}. ${detail.text === "unknown" ? t("no detail saved") : detail.text}`);
      }
    }
    const review = model.review ?? {};
    lines.push(review.status === "verified" ? t("The checker confirmed this route.")
      : review.status === "partly_unverified" ? t("The checker did not confirm everything on this route.") : t("Whether this route was checked is unknown."));
    return lines;
  });
}

// A light note, as in Mercature: the sentences, the two languages under them, and Copy.
function routeNote(app, act) {
  const lang = app.noteLang ?? app.lang;
  // Python writes the note with the route (section 7.2, one sentence per line). A run without one gets the
  // same sentences put together here from the spatial model, and nothing else.
  const written = typeof app.routeNote?.[lang] === "string" && app.routeNote[lang].trim() ? app.routeNote[lang].split("\n").map((line) => line.trim()).filter(Boolean) : null;
  const lines = written ?? noteText(app, lang);
  const copied = app.copied;
  const text = el("div", { class: "note-text", lang, tabindex: "0" }, lines.map((line) => el("p", {}, line)));
  // The fade at the bottom of the note lifts when she has scrolled to its end.
  // Ported from Mercature by Glendon Chin (MIT), src/ui/Chat.tsx useScrollFade: see THIRD_PARTY.md.
  const atEnd = () => text.toggleAttribute("data-end", text.scrollTop + text.clientHeight >= text.scrollHeight - 2);
  text.addEventListener("scroll", atEnd, { passive: true });
  requestAnimationFrame(atEnd);
  return el("section", { class: "note", "aria-label": t("Route note") },
    text,
    el("div", { class: "note-foot" },
      el("div", { class: "note-langs", role: "group", "aria-label": t("Language of the note") },
        [["en", "EN"], ["ko", "KO"]].map(([value, label]) => el("button", { type: "button", class: "note-lang", "aria-pressed": lang === value ? "true" : "false", "data-note-lang": value, on: { click: () => act.noteLang(value) } }, label))),
      el("button", { type: "button", class: "note-copy", id: "note-copy", on: { click: () => act.copyNote(lines.join("\n")) } }, icon(copied === "done" ? "check" : "copy"),
        el("span", { role: "status" }, copied === "done" ? t("Copied") : copied === "failed" ? t("Not copied: select the text instead") : t("Copy")))));
}
