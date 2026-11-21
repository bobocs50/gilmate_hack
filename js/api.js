// The only file that fetches. Three sources:
//   live      ?api=http://localhost:8000   talks to `adk api_server` (CONTRACT.md sections 2 and 3)
//   recorded  (default)                    reads the saved real run of an area (data/areas.json names the files)
//   dev       ?dev=1 to ?dev=4             reads a sample from dev/, invented data for layout work

const APP = "gilmate";
// Memory is kept per user id (CONTRACT.md section 6.1), so every session of this page uses the same one.
const USER = "traveller";
const SAMPLES = { 1: "dev/shape-sample.json", 2: "dev/shape-sample-2.json", 3: "dev/shape-sample-3.json", 4: "dev/shape-sample-4.json" };

export function readSource() {
  const params = new URLSearchParams(location.search);
  const api = null;   // published copy: saved runs only, never an agent server
  if (api) {
    let url = null;
    try { url = new URL(api); } catch { /* handled below */ }
    if (url && (url.protocol === "http:" || url.protocol === "https:")) {
      return { kind: "live", api: url.href.replace(/\/+$/, ""), root: params.get("root") };
    }
    return { kind: "bad_api", given: api };
  }
  const dev = params.get("dev");
  if (dev && Object.hasOwn(SAMPLES, dev)) return { kind: "dev", sample: SAMPLES[dev] };
  return { kind: "recorded" };
}

/** Returns { data } , { missing: true } or { broken: true }. Never throws. */
async function loadJson(path) {
  let res;
  try {
    res = await fetch(path, { cache: "no-store" });
  } catch {
    return { missing: true };
  }
  if (!res.ok) return { missing: true };
  try {
    return { data: await res.json() };
  } catch {
    return { broken: true };
  }
}

// The one area the page knew before data/areas.json was there. It is used when that file cannot be read,
// and for a development sample, which is one invented run of this area.
export const FIRST_AREA = { key: "shibuya", name: "Shibuya, Tokyo", words: ["shibuya", "渋谷", "시부야"], example: "I want to visit Shibuya in Tokyo",
  map: "data/map.json", candidates: "data/candidates.json", run: "data/run.json", photo: null };

// A file of an area is read only from the page's own data folder.
function dataPath(path, fallback) {
  return typeof path === "string" && /^data\/[\w./-]+\.json$/.test(path) && !path.includes("..") ? path : fallback;
}

/**
 * The areas the page can open (CONTRACT.md section 8.1): [{ key, name, words, example, map, candidates, run, photo }].
 * The default area stands first. A development sample knows only its one area.
 */
export async function loadAreas(source) {
  const read = source.kind === "dev" ? {} : await loadJson("data/areas.json");
  const areas = (Array.isArray(read.data?.areas) ? read.data.areas : []).filter((area) => area && typeof area.key === "string" && typeof area.name === "string");
  if (!areas.length) return [FIRST_AREA];
  return [...areas].sort((a, b) => (b.key === read.data.default) - (a.key === read.data.default));
}

/** The saved run of an area, or the development sample. An area without a saved run has none. */
export function loadRun(source, area = FIRST_AREA) {
  if (source.kind === "dev") return loadJson(source.sample);
  return area.run ? loadJson(dataPath(area.run, FIRST_AREA.run)) : Promise.resolve({ missing: true });
}

/**
 * The places, photos and counts as Python builds them without the model (CONTRACT.md section 7.2):
 * { area, candidates, street_photos, counts }. The page may draw from it while the first turn runs.
 * Real data only, so a development sample does not read it.
 */
export function loadEarly(source, area = FIRST_AREA) {
  return source.kind === "dev" ? Promise.resolve({ missing: true }) : loadJson(dataPath(area.candidates, FIRST_AREA.candidates));
}

/** The street map is real map data in every mode. Only layout work falls back to the older cut in dev/. */
export async function loadMap(source, area = FIRST_AREA) {
  const real = await loadJson(dataPath(area.map, FIRST_AREA.map));
  if (real.data || source.kind !== "dev") return real;
  return loadJson("dev/map-sample.json");
}

// ---- live ---------------------------------------------------------------------------------

function sessionUrl(api, sessionId) {
  return `${api}/apps/${APP}/users/${USER}/sessions/${encodeURIComponent(sessionId)}`;
}

/**
 * Creates a session and returns its id. It starts empty: her profile travels with the route turn
 * (CONTRACT.md section 7.3). The page opens it at once, to read what is remembered about her.
 */
export async function createSession(api, profile = null) {
  const sessionId = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const res = await fetch(sessionUrl(api, sessionId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile ? { profile } : {}),
  });
  if (!res.ok) throw new Error(`The agent server did not create a session (HTTP ${res.status}).`);
  return sessionId;
}

/**
 * Sends one turn (the message text is JSON), reads the event stream to its end,
 * then reads the session state. Returns { state, text, results } where text is the last
 * text the agent wrote in this turn (used for step "ask") and results are the answers of
 * the tools called in this turn, in order: [{ name, response }].
 * `onEvent` is called with every event as it arrives, so the page can show what the agent is doing.
 */
export async function sendTurn(api, sessionId, message, rootAgent, onEvent = null) {
  const res = await fetch(`${api}/run_sse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      appName: APP,
      userId: USER,
      sessionId,
      streaming: false,
      newMessage: { role: "user", parts: [{ text: JSON.stringify(message) }] },
    }),
  });
  if (!res.ok || !res.body) throw new Error(`The agent server refused the turn (HTTP ${res.status}).`);

  const events = [];
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) pushEvent(events, frame, onEvent);
  }
  pushEvent(events, buffer + decoder.decode(), onEvent);

  const failed = events.find((event) => event.error || event.errorMessage || event.errorCode);
  if (failed) {
    throw new Error(`The agent stopped with an error: ${failed.errorMessage ?? failed.error ?? failed.errorCode}`);
  }

  const state = await readState(api, sessionId);
  return { state, text: finalText(events, rootAgent), results: toolResults(events) };
}

export async function readState(api, sessionId) {
  const res = await fetch(sessionUrl(api, sessionId));
  if (!res.ok) throw new Error(`The session could not be read (HTTP ${res.status}).`);
  const session = await res.json();
  return session.state ?? {};
}

// One SSE frame is one or more "data:" lines holding one JSON event.
function pushEvent(events, frame, onEvent) {
  const data = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return;
  let event;
  try {
    event = JSON.parse(data);
  } catch {
    return;   // A frame that is not JSON carries nothing the page shows.
  }
  events.push(event);
  if (onEvent) onEvent(event);
}

// What the tools answered. A tool's answer is a "functionResponse" part: { name, response }.
function toolResults(events) {
  const results = [];
  for (const event of events) {
    for (const part of event.content?.parts ?? []) {
      const answer = part.functionResponse ?? part.function_response;
      if (answer && typeof answer.name === "string") results.push({ name: answer.name, response: answer.response ?? null });
    }
  }
  return results;
}

// The last text part of the last complete event written by the root agent.
// The root agent's name is not in the contract: it is taken from ?root=<name>,
// otherwise the last event with text that the user did not write is used.
function finalText(events, rootAgent) {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event.partial || event.author === "user") continue;
    if (rootAgent && event.author !== rootAgent) continue;
    const texts = (event.content?.parts ?? []).filter((part) => typeof part.text === "string" && part.text.trim() && !part.thought);
    if (texts.length) return texts[texts.length - 1].text.trim();
  }
  return null;
}
