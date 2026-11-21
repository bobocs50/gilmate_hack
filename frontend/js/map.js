// Parts ported from Mercature by Glendon Chin (MIT), github.com/glendonC/mercature, src/destinations/RouteMap.tsx, GeographicMap.tsx and lens.ts: see THIRD_PARTY.md.
// The tilted street map, drawn as SVG the way Mercature does it:
// rotate the world so the bearing points up, squash the vertical axis, and for every
// building paint the walls that face the viewer and then its roof, shifted up by its height.
// Buildings are painted far to near so a near block covers the one behind it. Every ordinary block has one
// height and the blocks of a run share two groups, all walls before all roofs, so neighbours read as one city block.
// Only the blocks and streets near the route (before it: near the places) are drawn: an island on empty ground.
//
// Labels and stop markers are HTML on top of the SVG, so they keep their size when the view moves.
// Before there is a route the map shows the places to choose from: each is a button she can press.
// She can drag the map and zoom it with the wheel or two fingers on a trackpad; a new focus puts it back.

import { el, svg, clear } from "./dom.js";
import { hazardWord, metres } from "./text.js";
import { t } from "./words.js";
import { icon } from "./parts.js";
import { orderedStops, legFrom, legLine, legBenches, stopHazards } from "./model.js";

const SQUASH = 0.6;        // vertical axis, gives the leaning look
const HEIGHT_FACTOR = 1.15;
const RISE = 8;            // metres: every ordinary block is this tall, so the picture stays calm
const RISE_LANDMARK = 18;  // a named landmark stands out
const NEAR_M = 60;         // a block is drawn when a corner is this close to the route
const NEAR_PLACES_M = 90;  // or, before there is a route, this close to a place
const MAX_SCALE = 3.4;     // screen px per metre
const MOVE_MS = 520;
const NARROW = 700;        // px: under this width the screen is a phone
const PAD = 70;            // metres of street kept around the route
const PAD_NARROW = 30;

export function createMap(host) {
  let project = null;            // (east, north, height) -> [x, y] in map units
  let toMetres = null;           // (lon, lat) -> [east, north]
  let bounds = null;             // of everything drawn
  let box = null;                // current view box {x, y, w, h}
  let frame = 0;
  let marks = [];                // labels and markers now on the map: the places, or the route
  let placeMarks = [];
  let routeMarks = [];
  let placePoints = new Map();   // place id -> its point on the map
  let placeBounds = null;
  let user = { k: 1, dx: 0, dy: 0 };   // her own zoom and drag, on top of the view the page asked for
  let legBoxes = new Map();      // stop id -> bounds of that stop and the leg leaving it
  let routeBounds = null;
  let blockList = [];            // every building: its footprint in metres and what was drawn for it
  let wayList = [];              // every street: its points in metres and its line
  let routeM = [];               // the route's lines in metres
  let placesM = [];              // the places in metres
  let mapData = null;            // what setData was given, kept so a phone can turn the map
  let bearingNow = 0;            // degrees the map is drawn at
  let nearLines = null;          // what the island was last drawn around, kept while nothing else is on the map
  let lastFocus = { stopId: null, placeId: null, insets: { top: 0, right: 0, bottom: 0, left: 0 } };

  const routeLayer = svg("g", { class: "map-route" });
  const dotsLayer = svg("g", { class: "map-photo-dots" });
  const waysLayer = svg("g", { class: "map-ways" });
  const blocksLayer = svg("g", { class: "map-blocks" });
  const picture = svg("svg", { class: "map-svg", preserveAspectRatio: "xMidYMid slice" }, waysLayer, blocksLayer, dotsLayer, routeLayer);
  const spotLabels = el("div", { class: "map-layer map-spots" });
  let spotMarks = [];
  const placeLabels = el("div", { class: "map-layer" });
  const routeLabels = el("div", { class: "map-layer" });
  const labels = el("div", { class: "map-labels" }, spotLabels, placeLabels, routeLabels);
  // The far part of the map fades into the ground.
  const haze = el("div", { class: "map-haze" });
  const credit = el("span", { class: "map-credit" }, "© OpenStreetMap");
  drag();

  new ResizeObserver(() => { if (project) moveTo(targetBox(), false); }).observe(host);

  /** Draws streets and buildings. Returns false when the data cannot be drawn. */
  function setData(data, turned = null) {
    const origin = data?.origin;
    if (!origin || !Array.isArray(data.buildings) || !Array.isArray(data.ways)) return false;
    // Another area's map: the island of the last one means nothing here.
    if (data !== mapData) { nearLines = null; routeM = []; placesM = []; }
    mapData = data;
    bearingNow = turned ?? (Number(data.bearing_deg) || 0);
    const bearing = (bearingNow * Math.PI) / 180;
    const cos = Math.cos(bearing);
    const sin = Math.sin(bearing);
    const rotate = (p) => [p[0] * cos - p[1] * sin, p[0] * sin + p[1] * cos];
    project = (east, north, height = 0) => {
      const [x, y] = rotate([east, north]);
      return [x, -y * SQUASH - height * SQUASH * HEIGHT_FACTOR];
    };
    toMetres = (lon, lat) => [(lon - origin.lon) * origin.m_per_deg_lon, (lat - origin.lat) * origin.m_per_deg_lat];
    bounds = emptyBounds();
    const wayBounds = emptyBounds();

    // Streets first: wide ones under narrow ones, steps as a dashed grey line.
    // A few streets run far out of the neighbourhood, so they do not count for the bounds.
    clear(waysLayer);
    wayList = [];
    blockList = [];
    const ways = data.ways.filter((way) => Array.isArray(way.pts) && way.pts.length >= 2);
    ways.sort((a, b) => (Number(b.width) || 0) - (Number(a.width) || 0));
    for (const way of ways) {
      const points = way.pts.map((p) => project(p[0], p[1]));
      points.forEach((p) => grow(wayBounds, p));
      const kind = way.kind === "steps" ? "steps" : way.kind === "path" ? "path" : "street";
      const width = kind === "steps" ? 2.5 : Math.max(2, Number(way.width) || 4) * 0.8;
      const line = svg("polyline", { class: `map-way map-way-${kind}`, points: pointList(points), "stroke-width": width.toFixed(1) });
      wayList.push({ pts: way.pts, el: line });
      waysLayer.append(line);
    }

    // Buildings, far to near.
    clear(blocksLayer);
    const blocks = [];
    for (const building of data.buildings) {
      if (!Array.isArray(building.pts) || building.pts.length < 3) continue;
      const rotated = building.pts.map(rotate);
      const depth = rotated.reduce((sum, p) => sum + p[1], 0) / rotated.length;
      blocks.push({ building, depth });
    }
    blocks.sort((a, b) => b.depth - a.depth);
    // Ordinary blocks share two groups, every wall before every roof, so a wall that stands against a
    // neighbour is covered by that neighbour's roof. A landmark is taller: it has its own group and ends the run.
    let run = null;
    for (const { building } of blocks) {
      if (building.landmark) {
        const own = svg("g", { class: "map-run" });
        blocksLayer.append(own);
        drawBlock(building, rotate, own, own);
        run = null;
      } else {
        if (!run) { run = { walls: svg("g", { class: "map-run" }), roofs: svg("g", { class: "map-run" }) }; blocksLayer.append(run.walls, run.roofs); }
        drawBlock(building, rotate, run.walls, run.roofs);
      }
    }
    if (!Number.isFinite(bounds.minX)) bounds = wayBounds;
    if (!Number.isFinite(bounds.minX)) return false;

    host.replaceChildren(picture, haze, labels, credit);
    host.dataset.drawn = "true";
    moveTo(targetBox(), false);
    return true;
  }

  function drawBlock(building, rotate, wallsInto, roofsInto) {
    const height = building.landmark ? RISE_LANDMARK : RISE;
    const drawn = [];
    const kind = building.landmark ? "landmark" : "block";
    // Wind the footprint the same way round for every building, so "faces the viewer" is one test.
    let pts = building.pts;
    let rotated = pts.map(rotate);
    let area = 0;
    for (let i = 0; i < rotated.length; i += 1) {
      const a = rotated[i];
      const b = rotated[(i + 1) % rotated.length];
      area += a[0] * b[1] - b[0] * a[1];
    }
    if (area < 0) {
      pts = [...pts].reverse();
      rotated = pts.map(rotate);
    }
    const walls = [];
    for (let i = 0; i < pts.length; i += 1) {
      const j = (i + 1) % pts.length;
      const nx = rotated[j][1] - rotated[i][1];
      const ny = -(rotated[j][0] - rotated[i][0]);
      const length = Math.hypot(nx, ny) || 1;
      if (ny / length >= -0.05) continue;             // this wall faces away
      const tone = nx / length > 0.35 ? "lit" : nx / length < -0.35 ? "shade" : "mid";
      const quad = [
        project(pts[i][0], pts[i][1]),
        project(pts[j][0], pts[j][1]),
        project(pts[j][0], pts[j][1], height),
        project(pts[i][0], pts[i][1], height),
      ];
      walls.push({ depth: Math.min(rotated[i][1], rotated[j][1]), quad, tone });
    }
    walls.sort((a, b) => b.depth - a.depth);
    for (const wall of walls) {
      const side = svg("polygon", { class: `map-${kind}-wall map-wall-${wall.tone}`, points: pointList(wall.quad) });
      drawn.push(side);
      wallsInto.append(side);
    }
    const roof = pts.map((p) => project(p[0], p[1], height));
    roof.forEach((p) => grow(bounds, p));
    const top = svg("polygon", { class: `map-${kind}-roof`, points: pointList(roof) });
    drawn.push(top);
    roofsInto.append(top);
    blockList.push({ pts: building.pts, els: drawn });
  }

  // On a phone a route that lies across the screen is small. The bearing, a quarter turn either way of the
  // map's own, at which the route fits largest; the map's own unless another shows it at least 5% larger.
  function uprightBearing(model) {
    const own = Number(mapData.bearing_deg) || 0;
    const points = [];
    const add = (lon, lat) => { if (Number.isFinite(Number(lon)) && Number.isFinite(Number(lat)) && lon !== null && lat !== null) points.push(toMetres(Number(lon), Number(lat))); };
    for (const stop of orderedStops(model)) {
      add(stop.lon, stop.lat);
      const leg = legFrom(model, stop.id);
      if (leg) for (const p of legLine(model, leg)) add(p[0], p[1]);
    }
    if (points.length < 2) return own;
    const freeW = host.clientWidth || 1;
    const freeH = (host.clientHeight || 1) * 0.6;
    const fit = (degrees) => {
      const cos = Math.cos((degrees * Math.PI) / 180);
      const sin = Math.sin((degrees * Math.PI) / 180);
      const b = emptyBounds();
      for (const p of points) grow(b, [p[0] * cos - p[1] * sin, p[0] * sin + p[1] * cos]);
      return Math.min(freeW / (b.maxX - b.minX + PAD_NARROW * 2), freeH / ((b.maxY - b.minY) * SQUASH + PAD_NARROW * 2 * SQUASH));
    };
    let best = own;
    let bestFit = fit(own) * 1.05;
    for (let turn = -90; turn <= 90; turn += 15) {
      const now = fit(own + turn);
      if (now > bestFit) { best = own + turn; bestFit = now; }
    }
    return best;
  }

  /**
   * Draws the route, the stop markers and the labels. Pass null to take the route off the map.
   * With `upright` a phone may turn the map so the route stands larger; the caller sets places, spots and dots again after this.
   */
  function setRoute(model, { upright = false } = {}) {
    if (project && mapData) {
      const bearing = model && upright && host.clientWidth < NARROW ? uprightBearing(model) : Number(mapData.bearing_deg) || 0;
      if (bearing !== bearingNow) { marks = []; spotMarks = []; placeMarks = []; routeMarks = []; setData(mapData, bearing); }
    }
    clear(routeLayer);
    clear(routeLabels);
    closeLook();
    routeMarks = [];
    marks = [...spotMarks, ...placeMarks];
    legBoxes = new Map();
    routeBounds = null;
    routeM = [];
    if (!project || !model) { if (project) { keepNear(); apply(true); } return; }
    const addMark = (mark) => routeMarks.push(newMark(routeLabels, mark));
    // What pressing a mark on the route shows: the real photos taken near it, and the facts the route has. Nothing made up.
    const stopLook = (stop) => {
      const facts = [];
      const access = stopHazards(model, stop).some((hazard) => hazard.kind === "unknown_access") ? t("Access unknown") : stop.access === "yes" ? t("Step-free entrance mapped") : null;
      if (access) facts.push(access);
      return { title: [stop.name ?? t("Name unknown"), stop.category ? t(stop.category) : null].filter(Boolean).join(" · "), facts, photos: stop.photos };
    };
    const legLook = (leg) => {
      if (!leg) return null;
      const to = stops.find((item) => item.id === leg.to);
      const facts = [];
      if (leg.stairs) facts.push(leg.stairs === "none_mapped" ? t("No stairs mapped") : leg.stairs === "unknown" ? t("Stairs unknown") : `${t("Stairs")}: ${leg.stairs}`);
      facts.push(`${legBenches(model, leg).length} ${t("benches on the walk")}`);
      const title = `${t("Walk to")} ${to?.name ?? t("Name unknown")}` + (Number.isFinite(Number(leg.distance_m)) && leg.distance_m !== null ? ` · ${metres(leg.distance_m)}` : "");
      return { title, facts, photos: leg.photos };
    };

    const stops = orderedStops(model);
    const place = (lon, lat) => {
      if (!Number.isFinite(Number(lon)) || !Number.isFinite(Number(lat))) return null;
      const [east, north] = toMetres(Number(lon), Number(lat));
      return project(east, north);
    };
    routeBounds = emptyBounds();

    const halos = svg("g");
    const lines = svg("g");
    routeLayer.append(halos, lines);
    for (const stop of stops) {
      const at = place(stop.lon, stop.lat);
      const legBox = emptyBounds();
      if (at) { grow(legBox, at); grow(routeBounds, at); }
      const leg = legFrom(model, stop.id);
      if (leg) {
        const points = legLine(model, leg).map((p) => place(p[0], p[1])).filter(Boolean);
        routeM.push(legLine(model, leg).filter((p) => Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1]))).map((p) => toMetres(Number(p[0]), Number(p[1]))));
        points.forEach((p) => { grow(legBox, p); grow(routeBounds, p); });
        if (points.length >= 2) {
          // A leg that is not routed is a straight line between two places, not a path anyone mapped:
          // it is drawn as grey dots and says so in words half-way along.
          // The same goes for a leg that came without its line: the segment between its stops is no path.
          const straight = leg.kind !== "routed" || !(Array.isArray(leg.line) && leg.line.length >= 2);
          halos.append(svg("polyline", { class: "map-route-halo", points: pointList(points), "data-from": stop.id, "data-straight": straight ? "true" : null }));
          lines.append(svg("polyline", { class: "map-route-line", points: pointList(points), "data-from": stop.id, "data-straight": straight ? "true" : null }));
          if (straight) {
            const first = points[0];
            const last = points[points.length - 1];
            addMark({ look: legLook(leg), at: [(first[0] + last[0]) / 2, (first[1] + last[1]) / 2], stopId: stop.id, rank: 2, kind: "straight", dot: false, reach: 0, text: t("Not routed") });
          } else if (Number.isFinite(Number(leg.distance_m)) && leg.distance_m !== null
            && !(model.hazards ?? []).some((hazard) => hazard.leg_id === leg.id && hazard.kind === "long_walk")) {
            // The leg's own distance, as the route tool returned it, written half-way along the line.
            // A long walk's warning already carries that distance, so it is not written twice.
            addMark({ look: legLook(leg), at: halfWay(points), stopId: stop.id, rank: 2, kind: "leg", dot: false, reach: 0, text: metres(leg.distance_m) });
          }
        }
      }
      legBoxes.set(stop.id, legBox);
    }

    stops.forEach((stop, index) => {
      const at = place(stop.lon, stop.lat);
      if (!at) return;
      addMark({ look: stopLook(stop), at, stopId: stop.id, rank: 1, kind: "stop", reach: 16, marker: el("span", { class: "map-stop" }, String(index + 1)), text: stop.name ?? "Name unknown" });
    });
    for (const hazard of model.hazards ?? []) {
      const leg = (model.legs ?? []).find((item) => item.id === hazard.leg_id);
      // The warning that a leg has no mapped path is already written on that leg's line.
      if (hazard.kind === "unknown_access" && leg && leg.kind !== "routed") continue;
      const stop = stops.find((item) => item.id === hazard.stop_id);
      const at = place(hazard.lon, hazard.lat) ?? (stop ? place(stop.lon, stop.lat) : null);
      if (!at) continue;
      // Only numbers a tool returned are written on the map: the leg's own distance, nothing worked out here.
      let text = hazardWord(hazard);
      if (hazard.kind === "long_walk" && leg) text += ` · ${metres(leg.distance_m)}`;
      const kind = hazard.kind === "steps" ? "steps" : hazard.kind === "long_walk" ? "long" : "unknown";
      // A warning about a stop sits at the stop: it needs no dot of its own, its words go beside the stop's.
      if (stop) addMark({ look: stopLook(stop), at, stopId: stop.id, rank: 2, kind, dot: false, reach: 16, text });
      else addMark({ look: legLook(leg), at, stopId: leg?.from ?? null, rank: 2, kind, text });
    }
    // The same bench can be listed for two legs; it is one bench on the map.
    const seen = new Set();
    for (const bench of model.benches ?? []) {
      const at = place(bench.lon, bench.lat);
      if (!at) continue;
      const key = `${Number(bench.lon).toFixed(6)},${Number(bench.lat).toFixed(6)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const leg = (model.legs ?? []).find((item) => item.id === bench.leg_id);
      const off = Number.isFinite(Number(bench.off_route_m)) && bench.off_route_m !== null ? [`${metres(bench.off_route_m)} ${t("from the route")}`] : [];
      addMark({ look: { title: t("Bench"), facts: off, photos: bench.photos }, at, stopId: leg?.from ?? null, rank: 3, kind: "bench", text: t("Bench") });
    }
    marks = [...spotMarks, ...placeMarks, ...routeMarks];
    keepNear();
    apply(true);
  }

  function newMark(layer, { at, stopId = null, rank, kind, marker, dot = true, reach = 12, text, pill = null, look = null }) {
    const point = marker ?? (dot ? el("span", { class: "map-dot", "data-kind": kind }) : null);
    const words = pill ?? el("span", { class: "map-pill", "data-kind": kind }, kind === "stop" ? null : el("i", { class: "map-pill-dot", "data-kind": kind }), text);
    if (look) {
      for (const node of [point, words]) {
        if (!node) continue;
        node.dataset.look = "true";
        node.addEventListener("click", (event) => { event.stopPropagation(); showLook(look); });
      }
    }
    if (point) layer.append(point);
    layer.append(words);
    return { at, stopId, rank, kind, dot: point, pill: words, reach, width: 0 };
  }

  /**
   * The places to choose from, as buttons. Each: { id, name, category, lat, lon, state: "yes"|"no"|null, current, label }.
   * `label` is the button's name for a screen reader (the place, what it is and her answer, in words).
   * An empty list takes them off the map.
   */
  function setPlaces(list, onPress, { quiet = false } = {}) {
    clear(placeLabels);
    placeLabels.toggleAttribute("data-quiet", quiet);
    placeMarks = [];
    placePoints = new Map();
    placeBounds = null;
    placesM = [];
    if (project && Array.isArray(list) && list.length) {
      placeBounds = emptyBounds();
      for (const place of list) {
        if (!Number.isFinite(Number(place.lon)) || !Number.isFinite(Number(place.lat))) continue;
        const [east, north] = toMetres(Number(place.lon), Number(place.lat));
        const at = project(east, north);
        placesM.push([east, north]);
        placePoints.set(place.id, at);
        grow(placeBounds, at);
        const glyph = place.state === "yes" ? "check" : place.state === "no" ? "cross" : (place.category in { see: 1, shop: 1, eat: 1 } ? place.category : "see");
        const press = () => onPress(place.id);
        const marker = el("button", { type: "button", class: "map-place", "data-state": place.state ?? "open", "data-current": place.current ? true : null, "aria-label": place.label, on: { click: press } },
          el("span", { class: "map-place-dot" }, icon(glyph)));
        // The name beside it is pressable too, for a finger that misses the dot. A screen reader has the button above.
        const pill = el("button", { type: "button", class: "map-pill", "data-kind": "place", "data-state": place.state ?? "open", tabindex: "-1", "aria-hidden": "true", on: { click: press } }, place.name);
        placeMarks.push(newMark(placeLabels, { at, rank: place.current ? 0 : place.state === "no" ? 4 : 1, kind: "place", marker, reach: 24, pill }));
      }
      if (!Number.isFinite(placeBounds.minX)) placeBounds = null;
    }
    marks = [...spotMarks, ...placeMarks, ...routeMarks];
    if (project) { keepNear(); apply(true); }
  }

  // Shows only the blocks with a corner near the route (before it: near a place) and the streets that lie
  // wholly a little further out; the rest of the neighbourhood is left as empty ground. With neither on the
  // map the island stays as it last was; before anything was shown, the whole neighbourhood is drawn.
  function keepNear() {
    const onRoute = routeM.some((line) => line.length >= 2);
    if (onRoute) nearLines = { lines: routeM, reach: NEAR_M };
    else if (placesM.length) nearLines = { lines: placesM.map((p) => [p, p]), reach: NEAR_PLACES_M };
    const lines = nearLines?.lines ?? [];
    const reach = nearLines?.reach ?? 0;
    const close = (p, within) => lines.some((line) => {
      for (let i = 1; i < line.length; i += 1) if (segDist(p, line[i - 1], line[i]) <= within) return true;
      return false;
    });
    let shown = 0;
    for (const block of blockList) {
      const show = !lines.length || block.pts.some((p) => close(p, reach));
      if (show) shown += 1;
      for (const item of block.els) item.style.display = show ? "" : "none";
    }
    for (const way of wayList) way.el.style.display = !lines.length || way.pts.every((p) => close(p, reach * 1.6)) ? "" : "none";
    host.dataset.blocks = String(shown);
  }

  /** The places to sit the map knows, as small quiet marks: [{ lat, lon }]. */
  function setSpots(list) {
    clear(spotLabels);
    spotMarks = [];
    if (project && Array.isArray(list)) {
      for (const spot of list) {
        if (!Number.isFinite(Number(spot?.lon)) || !Number.isFinite(Number(spot?.lat))) continue;
        const [east, north] = toMetres(Number(spot.lon), Number(spot.lat));
        const marker = el("span", { class: "map-spot" });
        spotLabels.append(marker);
        spotMarks.push({ at: project(east, north), stopId: null, rank: 9, kind: "spot", dot: marker, pill: null, reach: 0, width: 0 });
      }
    }
    marks = [...spotMarks, ...placeMarks, ...routeMarks];
    if (project) apply(true);
  }

  /** Where street photos were taken, as small grey dots: [{ lat, lon }]. */
  function setDots(list) {
    clear(dotsLayer);
    if (!project || !Array.isArray(list)) return;
    for (const item of list) {
      if (!Number.isFinite(Number(item?.lon)) || !Number.isFinite(Number(item?.lat))) continue;
      const [east, north] = toMetres(Number(item.lon), Number(item.lat));
      const [x, y] = project(east, north);
      dotsLayer.append(svg("circle", { class: "map-photo-dot", cx: x.toFixed(1), cy: y.toFixed(1), r: "1.1" }));
    }
  }

  // One small card in the left column: the real photo taken nearest to the pressed mark, what it is, and its facts.
  let lookCard = null;
  let lookShown = null;
  function closeLook() { lookCard?.remove(); lookCard = null; lookShown = null; }
  function showLook(look) {
    if (lookShown === look) { closeLook(); return; }
    closeLook();
    lookShown = look;
    const photos = (Array.isArray(look.photos) ? [...look.photos] : []).filter((photo) => photo?.thumb_url)
      .sort((a, b) => (Number(a.distance_m) || 0) - (Number(b.distance_m) || 0));
    let index = 0;
    const img = el("img", { class: "map-look-photo", alt: "" });
    const count = el("span", { class: "map-look-count" });
    const credit = el("p", { class: "map-look-facts" });
    const facts = el("p", { class: "map-look-facts" });
    const draw = () => {
      const photo = photos[index];
      img.src = photo.thumb_url;
      img.alt = look.title;
      count.textContent = photos.length > 1 ? `${index + 1} / ${photos.length}` : "";
      const near = Number.isFinite(Number(photo.distance_m)) ? `${t("Photo")} ${metres(photo.distance_m)} ${t("from here")}` : null;
      facts.textContent = [...look.facts, near].filter(Boolean).join(" · ");
      credit.textContent = [photo.credit, photo.source].filter(Boolean).join(" · ");
    };
    const step = (by) => (event) => { event.stopPropagation(); index = (index + by + photos.length) % photos.length; draw(); };
    lookCard = el("aside", { class: "map-look", "aria-live": "polite", on: { click: (event) => event.stopPropagation(), pointerdown: (event) => event.stopPropagation() } },
      photos.length ? img : el("p", { class: "map-look-none" }, t("No photo found")),
      photos.length > 1 ? el("div", { class: "map-look-nav" },
        el("button", { type: "button", class: "map-look-step", "aria-label": t("Previous photo"), on: { click: step(-1) } }, "‹"),
        count,
        el("button", { type: "button", class: "map-look-step", "aria-label": t("Next photo"), on: { click: step(1) } }, "›")) : null,
      el("p", { class: "map-look-title" }, look.title),
      facts,
      photos.length ? credit : null);
    if (photos.length) draw(); else facts.textContent = look.facts.join(" · ");
    host.append(lookCard);
  }
  host.addEventListener("click", () => { if (lookCard) closeLook(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && lookCard) closeLook(); });

  // Dragging moves the map. A press that does not move stays a press, so the place buttons keep working.
  function drag() {
    let from = null;
    host.addEventListener("pointerdown", (event) => {
      if (!project || event.button > 0) return;
      from = { x: event.clientX, y: event.clientY, dx: user.dx, dy: user.dy, moved: false };
    });
    host.addEventListener("pointermove", (event) => {
      if (!from) return;
      const dx = event.clientX - from.x;
      const dy = event.clientY - from.y;
      if (!from.moved && Math.hypot(dx, dy) < 6) return;
      if (!from.moved) { from.moved = true; host.setPointerCapture?.(event.pointerId); labels.dataset.moving = "true"; }
      const scale = (host.clientWidth || 1) / box.w;
      user.dx = from.dx - dx / scale;
      user.dy = from.dy - dy / scale;
      cancelAnimationFrame(frame);
      box = targetBox();
      apply(false);
    });
    const end = () => { if (from?.moved) apply(true); from = null; };
    host.addEventListener("pointerup", end);
    host.addEventListener("pointercancel", end);
    // After a drag the browser still sends a click to what lay under the finger: that click is not a press.
    host.addEventListener("click", (event) => { if (host.dataset.dragged) { event.stopPropagation(); event.preventDefault(); } }, true);
    host.addEventListener("pointerdown", () => { delete host.dataset.dragged; }, true);
    host.addEventListener("pointermove", () => { if (from?.moved) host.dataset.dragged = "true"; });
    host.addEventListener("wheel", (event) => {
      if (!project) return;
      event.preventDefault();
      user.k = Math.min(6, Math.max(0.5, user.k * Math.exp(-event.deltaY * 0.0015)));
      moveTo(targetBox(), false);
    }, { passive: false });
  }

  /**
   * Moves the view. stopId null shows the whole route (or the whole map when there is no route).
   * insets are the screen edges covered by panels, in px, so the subject lands in the free part.
   */
  function focus(target, insets) {
    const placeId = target && typeof target === "object" ? target.place : null;
    const stopId = typeof target === "string" ? target : null;
    const next = { stopId, placeId, insets: { top: 0, right: 0, bottom: 0, left: 0, ...insets } };
    // A new subject puts the view back; the same subject (a redraw, a resize) keeps her own zoom and drag.
    if (next.stopId !== lastFocus.stopId || next.placeId !== lastFocus.placeId) user = { k: 1, dx: 0, dy: 0 };
    lastFocus = next;
    for (const line of routeLayer.querySelectorAll("polyline")) {
      line.toggleAttribute("data-current", stopId !== null && line.getAttribute("data-from") === stopId);
    }
    for (const mark of marks) {
      if (mark.kind === "stop") mark.dot.toggleAttribute("data-current", mark.stopId === stopId);
    }
    if (project) moveTo(targetBox(), true);
  }

  function targetBox() {
    const width = host.clientWidth || 1;
    const height = host.clientHeight || 1;
    const { stopId, placeId, insets } = lastFocus;
    const free = { w: Math.max(80, width - insets.left - insets.right), h: Math.max(80, height - insets.top - insets.bottom) };
    const point = placeId !== null && placePoints.has(placeId) ? placePoints.get(placeId) : null;
    let subject = point ? { minX: point[0], maxX: point[0], minY: point[1], maxY: point[1] }
      : stopId !== null && legBoxes.has(stopId) ? legBoxes.get(stopId) : routeBounds ?? placeBounds;
    let scale;
    if (subject && Number.isFinite(subject.minX)) {
      const pad = point ? 110 : width < NARROW ? PAD_NARROW : PAD;   // metres of street kept around the subject
      const w = subject.maxX - subject.minX + pad * 2;
      const h = subject.maxY - subject.minY + pad * 2 * SQUASH;
      scale = Math.min(free.w / w, free.h / h, MAX_SCALE);
    } else {
      // No route yet: fill the screen with the neighbourhood.
      subject = bounds;
      scale = Math.max(width / (bounds.maxX - bounds.minX), height / (bounds.maxY - bounds.minY), 1.5);
    }
    scale *= user.k;
    const cx = (subject.minX + subject.maxX) / 2 + user.dx;
    const cy = (subject.minY + subject.maxY) / 2 + user.dy;
    return {
      x: cx - (insets.left + free.w / 2) / scale,
      y: cy - (insets.top + free.h / 2) / scale,
      w: width / scale,
      h: height / scale,
    };
  }

  function moveTo(target, animate) {
    cancelAnimationFrame(frame);
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!animate || !box || still) {
      box = target;
      apply(true);
      return;
    }
    const from = { ...box };
    const start = performance.now();
    labels.dataset.moving = "true";
    const step = (now) => {
      const t = Math.min(1, (now - start) / MOVE_MS);
      const k = 1 - (1 - t) ** 3;
      box = {
        x: from.x + (target.x - from.x) * k,
        y: from.y + (target.y - from.y) * k,
        w: from.w + (target.w - from.w) * k,
        h: from.h + (target.h - from.h) * k,
      };
      apply(t === 1);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
  }

  // Writes the view box and puts every marker at its place. When the view has come to rest,
  // the labels are laid out so that none covers another; a label with no free place is left out.
  function apply(settled) {
    picture.setAttribute("viewBox", `${box.x.toFixed(2)} ${box.y.toFixed(2)} ${box.w.toFixed(2)} ${box.h.toFixed(2)}`);
    const width = host.clientWidth || 1;
    const height = host.clientHeight || 1;
    const scale = width / box.w;
    for (const mark of marks) {
      mark.sx = (mark.at[0] - box.x) * scale;
      mark.sy = (mark.at[1] - box.y) * scale;
      if (mark.dot) mark.dot.style.transform = `translate(${mark.sx.toFixed(1)}px, ${mark.sy.toFixed(1)}px)`;
      // A label that is shown keeps its place beside its marker on every frame of a move.
      if (!settled && mark.pill?.dataset.shown && mark.ox !== undefined) mark.pill.style.transform = `translate(${(mark.sx + mark.ox).toFixed(1)}px, ${(mark.sy + mark.oy).toFixed(1)}px)`;
    }
    if (!settled) return;
    delete labels.dataset.moving;

    // Every marker keeps its place free, so no label is written over a stop, a warning or a bench.
    const taken = marks.filter((mark) => mark.dot).map((mark) => (mark.kind === "place" ? rect(mark.sx - 18, mark.sy - 18, 36, 36)
      : mark.kind === "stop" ? rect(mark.sx - 14, mark.sy - 14, 28, 28) : rect(mark.sx - 5, mark.sy - 5, 10, 10)));
    const current = lastFocus.stopId;
    const order = [...marks].sort((a, b) => weight(a, current) - weight(b, current));
    const { insets } = lastFocus;
    for (const mark of order) {
      if (!mark.pill) continue;
      if (!mark.width) mark.width = mark.pill.offsetWidth;
      if (!mark.width) continue;                       // a label that is not shown at all takes no room
      const w = mark.width;
      const h = 24;
      const reach = mark.reach;
      // Above or below its marker a label may slide sideways to stay on the screen, so a stop near the edge keeps its name.
      const across = (x) => Math.max(insets.left + 4, Math.min(x, width - insets.right - 4 - w));
      const tries = [
        ...(reach === 0 ? [[mark.sx - w / 2, mark.sy - h / 2]] : []),   // words on a line sit on the line
        [mark.sx + reach, mark.sy - h / 2],
        [mark.sx - reach - w, mark.sy - h / 2],
        [across(mark.sx - w / 2), mark.sy - reach - h - 2],
        [across(mark.sx - w / 2), mark.sy + reach + 2],
      ];
      let spot = null;
      for (const [x, y] of tries) {
        const r = rect(x, y, w, h);
        const inside = x >= insets.left + 4 && y >= insets.top + 4 && x + w <= width - insets.right - 4 && y + h <= height - insets.bottom - 4;
        if (inside && !taken.some((other) => overlap(r, other))) { spot = r; break; }
      }
      if (spot) {
        taken.push(spot);
        mark.ox = spot.x - mark.sx;
        mark.oy = spot.y - mark.sy;
        mark.pill.style.transform = `translate(${spot.x.toFixed(1)}px, ${spot.y.toFixed(1)}px)`;
        mark.pill.dataset.shown = "true";
      } else {
        delete mark.pill.dataset.shown;
      }
    }
  }

  return { setData, setRoute, setPlaces, setSpots, setDots, focus, get drawn() { return Boolean(project); } };
}

// Stop names come first, the stop she is at before the others; then what lies on the leg ahead, then the rest.
function weight(mark, current) {
  if (mark.kind === "place") return mark.rank;
  const here = current !== null && mark.stopId === current;
  if (mark.kind === "stop") return here ? 0 : 1;
  return (here ? 0 : 10) + mark.rank;
}

// How far a point is from a piece of a line, in the units of both.
function segDist(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const q = dx * dx + dy * dy;
  const u = q ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / q)) : 0;
  return Math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy);
}

// The point half-way along a line, measured along the line.
function halfWay(points) {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) total += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
  let left = total / 2;
  for (let i = 1; i < points.length; i += 1) {
    const length = Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    if (length >= left && length > 0) {
      const k = left / length;
      return [points[i - 1][0] + (points[i][0] - points[i - 1][0]) * k, points[i - 1][1] + (points[i][1] - points[i - 1][1]) * k];
    }
    left -= length;
  }
  return points[Math.floor(points.length / 2)];
}

function rect(x, y, w, h) { return { x, y, w, h }; }
function overlap(a, b) {
  const gap = 4;
  return a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;
}
function emptyBounds() { return { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity }; }
function grow(b, p) {
  if (p[0] < b.minX) b.minX = p[0];
  if (p[0] > b.maxX) b.maxX = p[0];
  if (p[1] < b.minY) b.minY = p[1];
  if (p[1] > b.maxY) b.maxY = p[1];
}
function pointList(points) {
  return points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
}
