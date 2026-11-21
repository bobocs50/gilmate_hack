// What the agent is doing, told by the guide one step at a time. Live, the steps come from the turn's own
// event stream as it arrives; in a saved run they are that run's audit rows, played back.
// The real rows are grouped into a handful of steps with counts, so no sentence is said twice and no tool or
// agent name is printed. A row that fits no step is folded into the step that is running; nothing is added
// that no row stands for.

import { el } from "./dom.js";
import { t } from "./words.js";

// The steps of making the map and of building the route, in the order they are told, with the tools each covers.
const GROUPS = {
  map: [
    ["request", ["read_request", "start_area", "read_area"]],
    ["search", ["search_places", "search_options", "search"]],
    ["screen", ["screen_results"]],
    ["places", ["find_place", "find_places", "find_candidates", "list_places", "save_options", "save_candidates"]],
    ["photos", ["place_photos", "street_photos", "find_photos", "fetch_photos"]],
    ["benches", ["rest_spots"]],
    ["check", ["ground_candidates", "describe_candidates", "descriptions_checked", "describe_place", "map_ready"]],
    ["weather", ["weather_today"]],
  ],
  route: [
    ["picks", ["record_picks"]],
    ["weather", ["weather_today"]],
    ["walks", ["walking_route", "propose_route", "router"]],
    ["benches", ["rest_spots"]],
    ["review", ["critic", "read_draft", "submit_review", "route_facts"]],
  ],
};

/** A new list of rows. `kind`: "live" | "replay" (a saved run or a sample, played back). `flow`: "map" | "route". */
export function newProgress(kind, flow) {
  return { kind, flow, rows: [], at: 0, then: null };
}

/** The audit rows of a saved run (CONTRACT.md section 1) as rows that are already over. */
export function rowsFromAudit(rows) {
  return (rows ?? []).map((row) => ({
    tool: row.tool ?? null,
    state: ["blocked", "withheld"].includes(row.decision) ? row.decision : "done",
    // Python writes one row when a step ended (it names what happened in `rule`), beside the plain row of the call itself (section 7.4).
    told: Boolean(row.rule) && row.decision === "allowed",
    // The search rows say how many results passed the screening and how many were kept away from the agent.
    screened: row.rule === "screened" ? numbers(row.detail) : null,
    // Python's own row for a forecast that no source answered (section 9.3): unknown, and said so.
    missing: row.rule === "weather_not_available",
    at: seconds(row.t),
  }));
}

// "category=see; passed=12; withheld=0" -> { passed: 12, withheld: 0 }. Only numbers the row itself holds.
function numbers(detail) {
  const found = {};
  for (const [, key, value] of String(typeof detail === "string" ? detail : "").matchAll(/(\w+)=(\d+)/g)) found[key] = Number(value);
  return found;
}

// "11:36:13" -> seconds of the day, or null.
function seconds(clock) {
  const match = /(\d{2}):(\d{2}):(\d{2})/.exec(String(clock ?? ""));
  return match ? Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]) : null;
}

/** Live: one event of the stream. A tool call is a row; its answer says how it ended. Returns true when something changed. */
export function takeEvent(progress, event) {
  let changed = false;
  for (const part of event?.content?.parts ?? []) {
    const call = part.functionCall ?? part.function_call;
    const answer = part.functionResponse ?? part.function_response;
    if (call && typeof call.name === "string") {
      progress.rows.push({ id: call.id ?? null, tool: call.name, state: "running", told: false });
      changed = true;
    }
    if (answer && typeof answer.name === "string") {
      const row = progress.rows.find((item) => item.state === "running" && (answer.id ? item.id === answer.id : item.tool === answer.name));
      if (row) {
        const status = answer.response && typeof answer.response === "object" ? answer.response.status : null;
        row.state = status === "denied" || status === "blocked" || status === "rejected" ? "blocked" : "done";
        changed = true;
      }
    }
  }
  return changed;
}

/**
 * The rows as steps: [{ key, count, withheld, blocked }], each step once, in the order it first happened.
 * `count` is how many times the step's work was done (a search, a place looked up).
 */
export function groupSteps(progress) {
  const groups = GROUPS[progress.flow] ?? GROUPS.map;
  const steps = [];
  let current = null;
  for (const row of progress.rows) {
    let key = groups.find(([, tools]) => tools.includes(row.tool))?.[0] ?? null;
    // The screening of the search results is its own step: the rows that say what passed, and every result
    // that was kept away from the agent, whichever tool wrote the row.
    if ((row.screened || row.state === "withheld") && groups.some(([name]) => name === "screen")) key = "screen";
    if (key) {
      current = steps.find((step) => step.key === key);
      if (!current) { current = { key, calls: 0, told: 0, withheld: 0, blocked: 0, kept: null, missing: false, at: row.at ?? null, end: row.at ?? null }; steps.push(current); }
    }
    if (!current) continue;                      // nothing has started yet that this row could belong to
    if (key) { if (row.told) current.told += 1; else current.calls += 1; }
    if (row.screened) { current.kept = (current.kept ?? 0) + (row.screened.passed ?? 0); current.withheld += row.screened.withheld ?? 0; }
    if (row.state === "withheld") current.withheld += 1;
    if (key && row.missing) current.missing = true;
    if (row.state === "blocked") current.blocked += 1;
    if (row.at !== null && row.at !== undefined) current.end = row.at;
  }
  // A step's work is counted once: by its calls when there are any, otherwise by the rows Python wrote for it.
  return steps.map((step) => ({ key: step.key, count: step.calls || step.told, withheld: step.withheld, blocked: step.blocked, kept: step.kept, missing: step.missing, at: step.at, end: step.end }));
}

/**
 * How long each step of a saved run is told, in ms: as long as it really took by the rows' own clock times,
 * at least `floor` each, and the whole no longer than `cap` (the long steps give way, the floor stays).
 */
export function stepTimes(steps, { floor = 3000, cap = 60000 } = {}) {
  const real = steps.map((step, index) => {
    const until = steps[index + 1]?.at ?? step.end;
    return step.at !== null && until !== null && until >= step.at ? (until - step.at) * 1000 : 0;
  });
  const over = real.map((ms) => Math.max(0, ms - floor));
  const room = Math.max(0, cap - floor * steps.length);
  const total = over.reduce((sum, ms) => sum + ms, 0);
  const scale = total > room && total > 0 ? room / total : 1;
  return over.map((ms) => floor + ms * scale);
}

/**
 * One step as a plain sentence. `known` holds the real numbers the data has: { places, streetPhotos, benches },
 * and `weather`: the worst thing in today's forecast in Python's own words, when the data holds a forecast.
 */
export function stepWords(step, known = {}) {
  const n = step.count;
  if (step.key === "request") return t("Reading your request");
  if (step.key === "search") return n === 1 ? t("Searching the web: 1 search") : n ? t("Searching the web: {count} searches", { count: n }) : t("Searching the web");
  if (step.key === "screen") return step.kept !== null ? t("Screening the results: {kept} kept, {withheld} withheld", { kept: step.kept, withheld: step.withheld })
    : step.withheld ? t("Screening the results: {withheld} withheld", { withheld: step.withheld }) : t("Screening the results");
  if (step.key === "places") return known.places ? t("Finding {count} places on the map", { count: known.places }) : t("Finding the places on the map");
  if (step.key === "photos") return known.streetPhotos ? t("Fetching street photos: {count}", { count: known.streetPhotos }) : t("Fetching photos");
  if (step.key === "benches") return known.benches ? t("Finding benches: {count}", { count: known.benches }) : t("Finding benches");
  if (step.key === "check") return step.blocked === 1 ? t("Checking the sources: 1 thing left out") : step.blocked ? t("Checking the sources: {count} things left out", { count: step.blocked }) : t("Checking what I read against the sources");
  if (step.key === "weather") return step.missing ? t("Today's weather could not be read") : known.weather ? t("Checking today's weather: {what}", { what: known.weather }) : t("Checking today's weather");
  if (step.key === "picks") return t("Noting the places you chose");
  if (step.key === "walks") return t("Working out the walks between them");
  if (step.key === "review") return step.blocked === 1 ? t("Checking the route: sent back once, then checked again") : step.blocked ? t("Checking the route: sent back {count} times, then checked again", { count: step.blocked }) : t("Checking the route");
  return t("Working");
}

/** Small dots under the bubble: one per step, the finished ones filled, the running one ringed. */
export function stepDots(count, at) {
  if (count < 2) return null;
  return el("div", { class: "step-dots", role: "img", "aria-label": t("Step {n} of {count}", { n: Math.min(at + 1, count), count }) },
    Array.from({ length: count }, (unused, index) => el("i", { "data-state": index < at ? "done" : index === at ? "now" : "next" })));
}
