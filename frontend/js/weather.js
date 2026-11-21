// The weather of the day for the area being visited, as one small mark in the top bar: a line icon, the
// average temperature of the hours still to come until the evening, and one word ("18° · Sunny").
// From the backend's own verdict when the state holds one (CONTRACT.md section 9); otherwise today's forecast
// is read straight from Open-Meteo for the middle of the area (no key; only the area's coordinates are sent).
// When neither answers nothing is shown. The words come from fixed rules with the limits of gilmate/weather.py;
// no model is asked.

import { el } from "./dom.js";
import { icon } from "./parts.js";
import { t } from "./words.js";

const FORECAST = "https://api.open-meteo.com/v1/forecast";
const TIMEOUT_MS = 4000;
const EVENING = 21;                                   // the last hour that counts for the day's average
const RAIN_LIKELY_PCT = 60, RAIN_POSSIBLE_PCT = 30, RAIN_LIKELY_MM = 1.0, VERY_HOT_C = 35, HOT_C = 30;
const THUNDER = [95, 96, 99];                         // WMO weather codes as Open-Meteo gives them
const SNOW = [71, 73, 75, 77, 85, 86];
const FOG = [45, 48];

const number = (value) => (typeof value === "number" && Number.isFinite(value) ? value : null);
const hourOf = (time) => Number(String(time).slice(11, 13));

/**
 * The mark for a list of hours: { temp, word, icon } or null when no hour holds a temperature.
 * hours: [{ time: "YYYY-MM-DDTHH:MM", temperature_c, feels_like_c, rain_chance_pct, rain_mm, weather_code }].
 * `from`: "YYYY-MM-DDTHH", the hour it is now at the place; hours before it do not count. `said`: the backend's
 * own verdict ({ rain, heat }), which then decides the word.
 */
export function markFromHours(hours, from = null, said = null) {
  const known = (Array.isArray(hours) ? hours : []).filter((hour) => hour && typeof hour.time === "string" && number(hour.temperature_c) !== null);
  const ahead = from ? known.filter((hour) => hour.time.slice(0, 13) >= from) : known;
  const day = ahead.filter((hour) => hourOf(hour.time) <= EVENING);
  const use = day.length ? day : ahead;
  if (!use.length) return null;
  const temp = Math.round(use.reduce((sum, hour) => sum + hour.temperature_c, 0) / use.length);
  const any = (test) => use.some(test);
  const codes = use.map((hour) => number(hour.weather_code)).filter((code) => code !== null);
  const likely = said ? said.rain === "likely" : any((hour) => (number(hour.rain_chance_pct) ?? 0) >= RAIN_LIKELY_PCT || (number(hour.rain_mm) ?? 0) >= RAIN_LIKELY_MM);
  const possible = said ? said.rain === "possible" : any((hour) => (number(hour.rain_chance_pct) ?? 0) >= RAIN_POSSIBLE_PCT || (number(hour.rain_mm) ?? 0) >= 0.1);
  const veryHot = said ? said.heat === "very_hot" : any((hour) => (number(hour.feels_like_c) ?? 0) >= VERY_HOT_C);
  const hot = said ? said.heat === "hot" : any((hour) => (number(hour.feels_like_c) ?? 0) >= HOT_C);
  let word, mark;
  if (codes.some((code) => THUNDER.includes(code))) [word, mark] = ["Thunderstorm", "storm"];
  else if (codes.some((code) => SNOW.includes(code))) [word, mark] = ["Snow", "snow"];
  else if (likely) [word, mark] = ["Rain likely", "rain"];
  else if (veryHot) [word, mark] = ["Very hot", "sun"];
  else if (hot) [word, mark] = ["Hot", "sun"];
  else if (possible) [word, mark] = ["Rain possible", "rain"];
  else if (!codes.length) return null;                 // a temperature alone is no condition: nothing is said
  else {
    // The sky of most of these hours
    const count = (test) => codes.filter(test).length;
    const fog = count((code) => FOG.includes(code)), cloudy = count((code) => code === 2 || code === 3), clear = count((code) => code <= 1);
    const dark = hourOf(use[0].time) >= 19 || hourOf(use[0].time) < 5;
    if (fog > cloudy && fog > clear) [word, mark] = ["Fog", "cloud"];
    else if (cloudy > clear) [word, mark] = ["Cloudy", "cloud"];
    else [word, mark] = [dark ? "Clear" : "Sunny", "sun"];
  }
  return { temp, word, icon: mark };
}

/** The mark from the backend's `weather` (section 9.1). Its hours are already the ones still to come today. */
export function markFromState(weather) {
  if (!weather || typeof weather !== "object") return null;
  return markFromHours(weather.hours, null, { rain: weather.rain ?? null, heat: weather.heat ?? null });
}

/** Today's forecast for the middle of the area, read in the browser. Returns the mark or null. Never throws. */
export async function readForecast(area) {
  const box = Array.isArray(area?.bbox) && area.bbox.length === 4 && area.bbox.every((value) => number(value) !== null) ? area.bbox : null;
  if (!box) return null;
  const [south, west, north, east] = box;
  const url = `${FORECAST}?latitude=${((south + north) / 2).toFixed(4)}&longitude=${((west + east) / 2).toFixed(4)}`
    + "&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code&timezone=auto&forecast_days=1";
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) return null;
    const data = await res.json();
    const hourly = data?.hourly;
    if (!hourly || !Array.isArray(hourly.time)) return null;
    const at = (name, index) => (Array.isArray(hourly[name]) ? number(hourly[name][index]) : null);
    const hours = hourly.time.map((time, index) => ({ time, temperature_c: at("temperature_2m", index), feels_like_c: at("apparent_temperature", index),
      rain_chance_pct: at("precipitation_probability", index), rain_mm: at("precipitation", index), weather_code: at("weather_code", index) }));
    const offset = number(data.utc_offset_seconds);
    if (offset === null) return null;
    return markFromHours(hours, new Date(Date.now() + offset * 1000).toISOString().slice(0, 13));
  } catch {
    return null;
  }
}

/** Draws the mark into its place in the top bar, or hides the place when there is none. */
export function drawMark(node, mark) {
  if (!node) return;
  node.hidden = !mark;
  if (!mark) { node.replaceChildren(); return; }
  node.replaceChildren(icon(mark.icon), el("span", { class: "sr-only" }, t("Today's weather"), ": "), el("span", {}, `${mark.temp}° · ${t(mark.word)}`));
}
