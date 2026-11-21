// Words for the data. Unknown is always said as "unknown", never left blank and never read as safe.
// The words come out in the page's language (words.js); the English ones are the keys.

import { t } from "./words.js";

/** Pick the language of an {en, ko} field. Falls back to the other language, then to "unknown". */
export function pick(field, lang) {
  if (field && typeof field === "object") {
    const value = field[lang] ?? field.en ?? field.ko;
    if (value) return { text: String(value), lang: field[lang] ? lang : field.en ? "en" : "ko" };
  }
  if (typeof field === "string" && field) return { text: field, lang: "en" };
  return { text: "unknown", lang: "en" };
}

export const ACCESS = {
  yes: { label: "Step-free entrance", tone: "route" },
  limited: { label: "Limited access", tone: "barrier" },
  no: { label: "Not accessible", tone: "blocked" },
  unknown: { label: "Access unknown", tone: "unknown" },
};

export function access(value) {
  const { label, tone } = ACCESS[value] ?? ACCESS.unknown;
  return { label: t(label), tone };
}

/** "none_mapped" is what the map data shows. It is not a promise, so the words say "mapped". */
export function stairs(value) {
  if (value === "none_mapped") return t("no stairs mapped");
  if (value === "some") return t("stairs on the way");
  return t("stairs unknown");
}

export function metres(value) {
  const n = Number(value);
  if (value === null || value === undefined || !Number.isFinite(n)) return t("distance unknown");
  if (n >= 1000) return `${(n / 1000).toFixed(1)} km`;
  return `${Math.round(n)} m`;
}

export const CATEGORY = { see: "What to see", shop: "Where to shop", eat: "Where to eat" };
export const CATEGORY_SHORT = { see: "See", shop: "Shop", eat: "Eat" };

/**
 * The time as written in the stamp itself, so the page shows the time the run was saved with.
 * A stamp is a full date and time ("2026-11-21T09:40:00") or, in the audit list, a bare "09:40:00".
 */
export function clock(stamp, { seconds = false } = {}) {
  const match = /(?:^|T|\s)(\d{2}:\d{2})(:\d{2})?/.exec(String(stamp ?? ""));
  if (match) return match[1] + (seconds && match[2] ? match[2] : "");
  const date = new Date(stamp);
  if (stamp === null || stamp === undefined || Number.isNaN(date.getTime())) return t("time unknown");
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

/** A hazard of kind "unknown_access" on a leg is about the path, at a stop it is about the entrance. */
export function hazardWord(hazard) {
  const kind = hazard?.kind;
  if (kind === "steps") return t("Steps");
  if (kind === "long_walk") return t("Long walk");
  if (kind === "unknown_access") return hazard.leg_id ? t("Path unknown") : t("Access unknown");
  return t("Check here");
}

/**
 * Where warnings or benches come from, in words. The raw references stay visible.
 * ["osm:node/1", "osm:node/2", "computed"] -> "OpenStreetMap node/1, node/2; worked out from the route"
 */
export function sourceWords(sources) {
  const texts = [...new Set((Array.isArray(sources) ? sources : [sources])
    .map((source) => (source === null || source === undefined ? "" : String(source).trim())))];
  const osm = texts.filter((text) => text.startsWith("osm:")).map((text) => text.slice(4));
  const parts = [];
  if (osm.length) parts.push(`OpenStreetMap ${osm.join(", ")}`);
  for (const text of texts) {
    if (text.startsWith("osm:")) continue;
    parts.push(text === "" ? t("source unknown") : text === "computed" ? t("worked out from the route") : text);
  }
  return parts.length ? parts.join("; ") : t("source unknown");
}

const PROFILE_WORDS = {
  walk: { short: "short walks", medium: "medium walks", long: "long walks" },
  stairs: { avoid: "no stairs", few: "a few stairs", ok: "stairs are fine" },
  rest: { often: "sitting down often", sometimes: "sitting down sometimes", rarely: "sitting down rarely" },
};

/** The answers a route was made for, as one phrase. A missing answer is said as unknown. */
export function profileWords(profile) {
  return ["walk", "stairs", "rest"].map((key) => (PROFILE_WORDS[key][profile?.[key]] ? t(PROFILE_WORDS[key][profile[key]]) : t("{key} unknown", { key }))).join(", ");
}
