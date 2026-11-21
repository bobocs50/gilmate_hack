// Reading helpers for what Gilmate remembers about her (CONTRACT.md section 6.1, state key "user:memory").
// No drawing, no fetching. The backend writes the memory; this file only turns it into words,
// in the page's language (words.js). English sentences are the keys; the names stay data-free.

import { metres, CATEGORY_SHORT } from "./text.js";
import { t } from "./know/words.js";

export const MEMORY_KEY = "user:memory";
export const LIMIT = "walk_limit_m";

// The three sources of the knowledge graph. `keys` is the order in which a source's facts stand behind it;
// a fact with another key comes after them, in the order it was saved.
export const GROUPS = [
  { id: "answers", name: "Your answers", about: "What you told me when I asked my questions.", keys: ["walk", "stairs", "rest", "food", "wish"], room: 5 },
  { id: "day", name: "Your day", about: "What I learned from your taps after a walk.", keys: [LIMIT], room: 2 },
  { id: "picks", name: "Your picks", about: "The places you chose.", keys: ["see", "shop", "eat"], room: 3 },
];
// Where a fact stands when its source is none of the three. Drawn only when such a fact exists.
export const OTHER = { id: "other", name: "Other", about: "Kept, but its source is not one I know.", keys: [] };

const ANSWER_NAMES = {
  walk: { short: "Short walks", medium: "Medium walks", long: "Long walks" },
  stairs: { avoid: "Avoids stairs", few: "A few stairs are fine", ok: "Stairs are fine" },
  rest: { often: "Sits down often", sometimes: "Sits down sometimes", rarely: "Rarely sits down" },
  food: { sushi: "Likes sushi", ramen: "Likes ramen", surprise: "Any food" },
};
const ANSWER_TOPICS = { walk: "Walking", stairs: "Stairs", rest: "Sitting down", food: "Food", wish: "Wish" };

/** The memory in a session state or a saved run, or null when it holds none. Rows that are not objects are left out. */
export function readMemory(state) {
  const stored = state?.[MEMORY_KEY];
  if (!stored || typeof stored !== "object") return null;
  const rows = (list) => (Array.isArray(list) ? list.filter((row) => row && typeof row === "object") : []);
  return { facts: rows(stored.facts), feedback: rows(stored.feedback) };
}

/**
 * The part of the memory this visit has reached: a new visit starts with nothing, and a fact is shown only once
 * the step that produces it has been passed. Nothing is added: every fact shown is one the memory holds.
 * visit: { answers: { key: value } as told in this visit, yes: [names of the places she said Yes to],
 *          route: the route has been made, live: the memory is the live agent's }
 * Her answers come with the answer she gave, a pick with its Yes, the day's facts with the route. Once the live
 * agent has made the route, its memory is this visit's own and is shown whole.
 */
export function reachedMemory(memory, visit) {
  if (!memory) return memory;
  const whole = Boolean(visit?.live && visit?.route);
  const told = visit?.answers ?? {};
  const yes = new Set(visit?.yes ?? []);
  const facts = memory.facts.filter((fact) => {
    if (whole) return true;
    const group = groupOf(fact);
    if (group === "answers") return fact.key in told && (visit.route || (told[fact.key] ?? null) === (fact.value ?? null));
    if (group === "picks") return yes.has(fact.value);
    return Boolean(visit?.route);
  });
  return { facts, feedback: visit?.route ? memory.feedback : [] };
}

export function findFact(memory, factId) {
  return (memory?.facts ?? []).find((fact) => fact.id === factId) ?? null;
}

function groupOf(fact) {
  if (GROUPS.some((group) => group.id === fact.group)) return fact.group;
  return { answer: "answers", feedback: "day", pick: "picks" }[fact.source] ?? null;
}

/**
 * The facts sorted into the three sources, each on the place of its key, plus the facts that have no place
 * (a key this page does not know). Those are listed under the map, so that nothing kept stays hidden.
 * placed: [{ group, slots: [fact|null, ...] }], unplaced: [fact]
 */
export function placeFacts(memory) {
  const facts = memory?.facts ?? [];
  const placed = GROUPS.map((group) => ({
    group, slots: group.keys.map((key) => facts.find((fact) => groupOf(fact) === group.id && fact.key === key) ?? null),
  }));
  const onMap = placed.flatMap((item) => item.slots);
  return { placed, unplaced: facts.filter((fact) => !onMap.includes(fact)) };
}

/**
 * Every fact of the memory under its source: [{ group, facts }]. Nothing is left out: a fact whose source is
 * none of the three stands under OTHER, which is in the list only then. Several facts may share a key
 * (she may pick two places to eat); each is its own entry.
 */
export function groupFacts(memory) {
  const sorted = GROUPS.map((group) => ({ group, facts: [] }));
  const other = { group: OTHER, facts: [] };
  for (const fact of memory?.facts ?? []) (sorted.find((item) => item.group.id === groupOf(fact)) ?? other).facts.push(fact);
  for (const item of sorted) {
    const rank = (fact) => { const at = item.group.keys.indexOf(fact.key); return at < 0 ? item.group.keys.length : at; };
    item.facts = item.facts.map((fact, index) => [fact, index]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(([fact]) => fact);
  }
  return other.facts.length ? [...sorted, other] : sorted;
}

/** The short name under a node, for example "Avoids stairs" or "Walks up to 500 m". A place name stays as it is. */
export function factName(fact) {
  const { key, value } = fact;
  if (ANSWER_NAMES[key]) return ANSWER_NAMES[key][value] ? t(ANSWER_NAMES[key][value]) : t("{topic}: {value}", { topic: t(ANSWER_TOPICS[key]), value: said(value) });
  if (key === "wish") return value ? t("Wish: {wish}", { wish: value }) : t("No wish");
  if (key === LIMIT) return isNumber(value) ? t("Walks up to {distance}", { distance: metres(value).replace(" ", "\u00a0") }) : t("Walking limit unknown");
  if (CATEGORY_SHORT[key] || groupOf(fact) === "picks") return value ? String(value) : t("Place unknown");
  return t("{topic}: {value}", { topic: key ?? t("Fact"), value: said(value) });
}

/** What kind of thing the fact is, for the line above its name in the panel. */
export function factKind(fact) {
  if (ANSWER_TOPICS[fact.key]) return t("Your answer · {topic}", { topic: t(ANSWER_TOPICS[fact.key]) });
  if (fact.key === LIMIT) return t("Learned from your taps · Walking limit");
  if (CATEGORY_SHORT[fact.key]) return t("Your pick · {kind}", { kind: t(CATEGORY_SHORT[fact.key]) });
  if (groupOf(fact) === "picks") return t("Your pick");
  return t("Kept fact");
}

function said(value) {
  return value === null || value === undefined || value === "" ? t("unknown") : String(value);
}

function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function isLearned(fact) {
  return fact.source === "feedback";
}

/** The local day as the backend writes it in the feedback rows: "2026-11-21". */
export function localDay(date = new Date()) {
  const two = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`;
}

/** The "too far" taps a learned limit came from, oldest first. */
export function tooFarTaps(memory) {
  return (memory?.feedback ?? []).filter((row) => row.verdict === "too_far");
}

/**
 * The state of a fact in words. `short` goes under the node, `long` into the panel.
 * A limit that is still being learned counts only on the day of its newest "too far" tap. The fact itself
 * carries no date, so that day is read from the feedback rows; without a row the page says it does not know.
 */
export function factState(memory, fact, today) {
  if (fact.status === "candidate") {
    const taps = tooFarTaps(memory);
    const day = fact.key === LIMIT && taps.length ? String(taps[taps.length - 1].at ?? "").slice(0, 10) : "";
    if (fact.key !== LIMIT) return { short: t("still learning"), long: t("Still learning: this is not kept for good yet.") };
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
      return { short: t("still learning"), long: t("Still learning. Whether it counts today is unknown: no tap with a date is saved with it.") };
    }
    if (day === today) {
      return { short: t("still learning"), long: t("Still learning. It counts for routes made today. A second “too far” would keep it.") };
    }
    return { short: t("still learning, not in use today"), stale: true,
      long: t("Still learning, and not in use today: it comes from one tap on {day} and counted only on that day. A second “too far” would keep it.", { day }) };
  }
  if (fact.status === "kept") {
    return isLearned(fact)
      ? { short: t("learned, kept"), long: t("Learned and kept: it counts for every route until you forget it.") }
      : { short: "", long: t("Kept until you change or forget it.") };
  }
  return { short: t("state unknown"), long: t("State unknown.") };
}

/** Her remembered answers as { key: value }, only values the questions know. `wish` may be null (she skipped it). */
export function rememberedAnswers(memory, questions) {
  const known = {};
  for (const question of questions) {
    const fact = (memory?.facts ?? []).find((row) => groupOf(row) === "answers" && row.key === question.key);
    if (!fact) continue;
    if (question.key === "wish") {
      if (fact.value === null || typeof fact.value === "string") known.wish = fact.value || null;
    } else if (question.answers.some(([, value]) => value === fact.value)) {
      known[question.key] = fact.value;
    }
  }
  return known;
}

/** One line per remembered answer for "Still true?": [{ topic, words }]. */
export function answerLines(memory, questions) {
  const known = rememberedAnswers(memory, questions);
  return questions.filter((question) => question.key in known).map((question) => ({
    topic: t(ANSWER_TOPICS[question.key]),
    words: question.key === "wish" ? (known.wish ? `“${known.wish}”` : t("None")) : t(ANSWER_NAMES[question.key][known[question.key]]),
  }));
}

// ---- what the tools answered (CONTRACT.md section 6.2), in words ----------------------------------

// A turn may hold several answers of one tool: the model sometimes calls it a second time and is refused then.
// The step is done when one answer says so; only when none does, the last answer is the reason given.
function toolAnswer(results, name, done) {
  const mine = (results ?? []).filter((result) => result.name === name && result.response && typeof result.response === "object")
    .map((result) => result.response);
  return mine.find((answer) => answer.status === done) ?? (mine.length ? mine[mine.length - 1] : null);
}

// A refusal is said as it is: the policy table ("denied"), the tool itself ("rejected"), or a fact that is gone.
function refusal(answer) {
  if (answer.status === "denied") return answer.rule ? t("A rule of the agent refused this step (rule: {rule}).", { rule: answer.rule }) : t("A rule of the agent refused this step.");
  if (answer.status === "rejected") return answer.reason ? t("The agent refused it: {reason}.", { reason: answer.reason }) : t("The agent refused it and gave no reason.");
  if (answer.status === "not_found") return t("It is not in my memory any more.");
  return t("The agent answered “{status}”.", { status: answer.status ?? "" });
}

/** { kind: "recorded", fact|null } or { kind: "refused", text } */
export function feedbackOutcome(results) {
  const answer = toolAnswer(results, "record_feedback", "recorded");
  if (!answer) return { kind: "refused", text: t("Not saved: the agent finished without recording your answer.") };
  if (answer.status === "recorded") return { kind: "recorded", fact: answer.fact && typeof answer.fact === "object" ? answer.fact : null };
  return { kind: "refused", text: t("Not saved. {why}", { why: refusal(answer) }) };
}

/** { kind: "done" } or { kind: "refused", text }. `gone`: the fact is no longer in the memory read after the turn. */
export function forgetOutcome(results, gone) {
  const answer = toolAnswer(results, "forget_fact", "forgotten");
  if (answer?.status === "forgotten" || (!answer && gone)) return { kind: "done" };
  if (!answer) return { kind: "refused", text: t("Not forgotten: the agent finished without doing it.") };
  return { kind: "refused", text: t("Not forgotten. {why}", { why: refusal(answer) }) };
}
