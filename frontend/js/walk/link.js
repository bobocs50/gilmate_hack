// The route as it travels from the desk to the phone: in the link itself, after the "#".
//
//   routeFromState(state)   the session state (CONTRACT.md sections 1 and 7.2) cut down to what the walk needs
//   encode(route)           that route as text for the link: short lists, deflated, written in the 43 characters
//                           a QR code stores most tightly (digits, capitals and $*+-./:), all allowed after "#"
//   decode(text)            the route again, every value checked, because a link can come from anyone
//
// Nothing here invents a value: what the state does not hold stays null and the phone says "unknown".
// Photo bytes never travel. A photo is its address, or only its id when the address is too long for a QR code.
// Authors and licences do not travel either: the phone page shows no credit line (they are in CREDITS.md).

const ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ$*+-./:";
const BASE = ALPHABET.length;
const START = "R1";     // route, format 1
const END = "E";        // a link must not end in "." or ":"; chat apps cut those off
const LONGEST_PHOTO_ADDRESS = 120;

const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
const text = (value) => (typeof value === "string" && value ? value : null);
const pair = (value) => (value && typeof value === "object" && (text(value.en) || text(value.ko)) ? { en: text(value.en), ko: text(value.ko) } : null);

// ---- the session state, cut down ----------------------------------------------------------

function photo(found, kind) {
  if (!found || typeof found !== "object") return null;
  // A street photo is shown large, so its larger copy is asked; a place's own photo has a small copy in the page folder.
  const address = kind === "street" ? text(found.url) ?? text(found.thumb_url) : text(found.thumb_url) ?? text(found.url);
  if (!address && !text(found.id)) return null;
  return {
    kind,                                   // "street": taken near the stop; "place": a photo of the place itself
    id: text(found.id),
    url: address,
    distance_m: isNumber(found.distance_m) ? found.distance_m : null,
  };
}

function nearest(photos) {
  if (!Array.isArray(photos) || !photos.length) return null;
  return [...photos].sort((a, b) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity))[0];
}

/**
 * `state` is the session state or the page's own object: the route is read from `spatial_model` (or `model`),
 * the note from `route_note` (or `routeNote`), the places' own photos and kinds from `candidates`.
 * Returns null when there is no route.
 */
export function routeFromState(state, { lang = null, live = null } = {}) {
  const model = state?.spatial_model ?? state?.model ?? null;
  if (!model || !Array.isArray(model.stops) || !model.stops.length) return null;
  const candidates = Array.isArray(state.candidates) ? state.candidates : [];
  const note = state.route_note ?? state.routeNote ?? null;

  const stops = [...model.stops].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).map((stop) => {
    const place = candidates.find((candidate) => candidate.id === stop.option_id) ?? null;
    return {
      id: String(stop.id),
      name: text(stop.name),
      lat: isNumber(stop.lat) ? stop.lat : null,
      lon: isNumber(stop.lon) ? stop.lon : null,
      access: text(stop.access) ?? "unknown",
      category: text(stop.category),
      kind: pair(place?.kind),
      street: photo(nearest(stop.photos), "street"),
      place: photo(place?.photos?.[0], "place"),
    };
  });

  return {
    area: text(model.area?.name),
    made: text(model.generated_at),
    recorded: text(state.recorded_at) ?? text(state.run?.recorded_at),
    review: text(model.review?.status),
    lang: lang === "ko" ? "ko" : "en",
    stops,
    legs: (model.legs ?? []).map((leg) => ({
      id: String(leg.id),
      from: String(leg.from),
      to: String(leg.to),
      distance_m: isNumber(leg.distance_m) ? leg.distance_m : null,
      kind: text(leg.kind),
      stairs: text(leg.stairs) ?? "unknown",
      fits_profile: typeof leg.fits_profile === "boolean" ? leg.fits_profile : null,
      line: (leg.line ?? []).filter((point) => Array.isArray(point) && isNumber(point[0]) && isNumber(point[1])).map(([lon, lat]) => [lon, lat]),
    })),
    hazards: (model.hazards ?? []).map((hazard) => ({
      leg_id: text(hazard.leg_id), stop_id: text(hazard.stop_id), kind: text(hazard.kind), detail: pair(hazard.detail),
    })),
    benches: (model.benches ?? []).map((bench) => ({
      leg_id: text(bench.leg_id),
      lat: isNumber(bench.lat) ? bench.lat : null,
      lon: isNumber(bench.lon) ? bench.lon : null,
      off_route_m: isNumber(bench.off_route_m) ? bench.off_route_m : null,
    })),
    note: pair(note),
    live: live && text(live.api) && text(live.session) ? { api: live.api, session: live.session, root: text(live.root) } : null,
  };
}

// ---- short lists --------------------------------------------------------------------------

const E5 = 100000;                                  // five decimals of a degree: about one metre
const whole = (degrees) => (isNumber(degrees) ? Math.round(degrees * E5) : null);
const degrees = (value) => (isNumber(value) ? value / E5 : null);

function packPhoto(found) {
  if (!found) return 0;
  const short = found.url && found.url.length <= LONGEST_PHOTO_ADDRESS ? found.url : "";
  return [found.id ?? "", short, found.distance_m];
}

function unpackPhoto(list, kind) {
  if (!Array.isArray(list)) return null;
  return { kind, id: text(list[0]), url: text(list[1]), distance_m: isNumber(list[2]) ? list[2] : null };
}

// A point that leaves the straight line between its kept neighbours by less than three metres is left out.
// The line is only drawn on the phone; a walk's length is its own number and is never measured from it.
function thin(line, metres = 3) {
  if (line.length < 3) return line;
  const east = 111320 * Math.cos((line[0][1] * Math.PI) / 180);
  const flat = line.map(([lon, lat]) => [lon * east, lat * 111320]);
  const keep = new Set([0, line.length - 1]);
  const split = (first, last) => {
    const [ax, ay] = flat[first];
    const [bx, by] = flat[last];
    const length = Math.hypot(bx - ax, by - ay) || 1;
    let far = -1;
    let most = metres;
    for (let i = first + 1; i < last; i += 1) {
      const off = Math.abs((bx - ax) * (flat[i][1] - ay) - (by - ay) * (flat[i][0] - ax)) / length;
      if (off > most) { most = off; far = i; }
    }
    if (far === -1) return;
    keep.add(far);
    split(first, far);
    split(far, last);
  };
  split(0, line.length - 1);
  return line.filter((_, index) => keep.has(index));
}

// The first point as it is, every further point as its step from the one before.
function packLine(line) {
  const flat = [];
  let before = [0, 0];
  for (const [lon, lat] of thin(line)) {
    const point = [whole(lon), whole(lat)];
    flat.push(point[0] - before[0], point[1] - before[1]);
    before = point;
  }
  return flat;
}

function unpackLine(flat) {
  if (!Array.isArray(flat) || flat.length % 2 || !flat.every(isNumber)) return [];
  const line = [];
  let lon = 0;
  let lat = 0;
  for (let i = 0; i < flat.length; i += 2) {
    lon += flat[i];
    lat += flat[i + 1];
    line.push([lon / E5, lat / E5]);
  }
  return line;
}

export function pack(route) {
  return [
    1, route.area, route.made, route.recorded, route.review, route.lang,
    route.stops.map((stop) => [stop.id, stop.name, whole(stop.lat), whole(stop.lon), stop.access, stop.category,
      stop.kind?.en ?? "", stop.kind?.ko ?? "", packPhoto(stop.street), packPhoto(stop.place)]),
    route.legs.map((leg) => [leg.id, leg.from, leg.to, leg.distance_m, leg.kind, leg.stairs,
      leg.fits_profile === null ? null : Number(leg.fits_profile), packLine(leg.line)]),
    route.hazards.map((hazard) => [hazard.leg_id ?? "", hazard.stop_id ?? "", hazard.kind, hazard.detail?.en ?? "", hazard.detail?.ko ?? ""]),
    route.benches.map((bench) => [bench.leg_id, whole(bench.lat), whole(bench.lon), bench.off_route_m]),
    route.note ? [route.note.en ?? "", route.note.ko ?? ""] : 0,
    route.live ? [route.live.api, route.live.session, route.live.root ?? ""] : 0,
  ];
}

export function unpack(packed) {
  if (!Array.isArray(packed) || packed[0] !== 1) throw new Error("unknown format");
  const [, area, made, recorded, review, lang, stops, legs, hazards, benches, note, live] = packed;
  if (!Array.isArray(stops) || !stops.length || !stops.every(Array.isArray)) throw new Error("no stops");
  const lists = (value) => (Array.isArray(value) ? value.filter(Array.isArray) : []);
  return {
    area: text(area), made: text(made), recorded: text(recorded), review: text(review), lang: lang === "ko" ? "ko" : "en",
    stops: stops.map((s) => ({
      id: String(s[0]), name: text(s[1]), lat: degrees(s[2]), lon: degrees(s[3]), access: text(s[4]) ?? "unknown", category: text(s[5]),
      kind: pair({ en: s[6], ko: s[7] }), street: unpackPhoto(s[8], "street"), place: unpackPhoto(s[9], "place"),
    })),
    legs: lists(legs).map((l) => ({
      id: String(l[0]), from: String(l[1]), to: String(l[2]), distance_m: isNumber(l[3]) ? l[3] : null, kind: text(l[4]),
      stairs: text(l[5]) ?? "unknown", fits_profile: l[6] === 1 ? true : l[6] === 0 ? false : null, line: unpackLine(l[7]),
    })),
    hazards: lists(hazards).map((h) => ({ leg_id: text(h[0]), stop_id: text(h[1]), kind: text(h[2]), detail: pair({ en: h[3], ko: h[4] }) })),
    benches: lists(benches).map((b) => ({ leg_id: text(b[0]), lat: degrees(b[1]), lon: degrees(b[2]), off_route_m: isNumber(b[3]) ? b[3] : null })),
    note: Array.isArray(note) ? pair({ en: note[0], ko: note[1] }) : null,
    live: Array.isArray(live) && webAddress(live[0]) && text(live[1]) ? { api: webAddress(live[0]), session: live[1], root: text(live[2]) } : null,
  };
}

/** Only http and https addresses are ever asked. */
export function webAddress(value) {
  try {
    const url = new URL(String(value));
    return url.protocol === "http:" || url.protocol === "https:" ? url.href.replace(/\/+$/, "") : null;
  } catch {
    return null;
  }
}

// ---- bytes as text ------------------------------------------------------------------------

// Two bytes become three characters (43 x 43 x 43 is more than 65536), a last single byte becomes two.
export function bytesToText(bytes) {
  let out = "";
  for (let i = 0; i + 1 < bytes.length; i += 2) {
    const value = bytes[i] * 256 + bytes[i + 1];
    out += ALPHABET[Math.floor(value / (BASE * BASE))] + ALPHABET[Math.floor(value / BASE) % BASE] + ALPHABET[value % BASE];
  }
  if (bytes.length % 2) {
    const value = bytes[bytes.length - 1];
    out += ALPHABET[Math.floor(value / BASE)] + ALPHABET[value % BASE];
  }
  return out;
}

export function textToBytes(written) {
  const digits = [...written].map((char) => ALPHABET.indexOf(char));
  if (digits.includes(-1) || digits.length % 3 === 1) throw new Error("not a route link");
  const bytes = [];
  let i = 0;
  for (; i + 2 < digits.length; i += 3) {
    const value = (digits[i] * BASE + digits[i + 1]) * BASE + digits[i + 2];
    if (value > 65535) throw new Error("not a route link");
    bytes.push(value >> 8, value & 255);
  }
  if (i < digits.length) {
    const value = digits[i] * BASE + digits[i + 1];
    if (value > 255) throw new Error("not a route link");
    bytes.push(value);
  }
  return Uint8Array.from(bytes);
}

async function through(bytes, stream) {
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(stream)).arrayBuffer());
}

/** True when this browser can read and write the link (Safari 16.4, Chrome 103, Firefox 113, or newer). */
export function canSqueeze() {
  return typeof CompressionStream === "function" && typeof DecompressionStream === "function";
}

/** The route as the text that follows "#" in the link. */
export async function encode(route) {
  const bytes = new TextEncoder().encode(JSON.stringify(pack(route)));
  return START + bytesToText(await through(bytes, new CompressionStream("deflate-raw"))) + END;
}

export function isRouteText(written) {
  return typeof written === "string" && written.startsWith(START) && written.endsWith(END) && written.length > START.length + END.length;
}

/** The route from the text after "#". Throws when the text is not a route. */
export async function decode(written) {
  if (!isRouteText(written)) throw new Error("not a route link");
  const squeezed = textToBytes(written.slice(START.length, -END.length));
  const bytes = await through(squeezed, new DecompressionStream("deflate-raw"));
  return unpack(JSON.parse(new TextDecoder().decode(bytes)));
}
