// The small map strip of one walk: the walk's own line, its two stops and its benches, north up.
// It is drawn from the route alone. When the street map (data/map.json) could be read, its streets lie under it.

import { svg } from "../dom.js";

const WIDTH = 358;      // the strip's size on the phone, in px; the drawing keeps this shape
const HEIGHT = 132;
const MARGIN_M = 45;

/** Returns an <svg>, or null when the walk has no place on the map. `label` is said to a screen reader. */
export function drawStrip(route, leg, map, label) {
  const from = route.stops.find((stop) => stop.id === leg.from);
  const to = route.stops.find((stop) => stop.id === leg.to);
  const ends = [from, to].filter((stop) => stop && stop.lat !== null && stop.lon !== null);
  const line = leg.line.length >= 2 ? leg.line : ends.map((stop) => [stop.lon, stop.lat]);
  if (line.length < 2) return null;

  // Metres east and south of one fixed point: the street map's own when there is one.
  const origin = map?.origin ?? { lat: line[0][1], lon: line[0][0], m_per_deg_lat: 111320, m_per_deg_lon: 111320 * Math.cos((line[0][1] * Math.PI) / 180) };
  const place = ([lon, lat]) => [(lon - origin.lon) * origin.m_per_deg_lon, -(lat - origin.lat) * origin.m_per_deg_lat];
  const points = line.map(place);
  const benches = route.benches.filter((bench) => bench.leg_id === leg.id && bench.lat !== null && bench.lon !== null).map((bench) => place([bench.lon, bench.lat]));

  // The frame: the walk with a margin, widened or heightened to the strip's shape.
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  let left = Math.min(...xs) - MARGIN_M;
  let right = Math.max(...xs) + MARGIN_M;
  let top = Math.min(...ys) - MARGIN_M;
  let bottom = Math.max(...ys) + MARGIN_M;
  const shape = WIDTH / HEIGHT;
  if ((right - left) / (bottom - top) < shape) {
    const grow = ((bottom - top) * shape - (right - left)) / 2;
    left -= grow;
    right += grow;
  } else {
    const grow = ((right - left) / shape - (bottom - top)) / 2;
    top -= grow;
    bottom += grow;
  }
  const px = (right - left) / WIDTH;      // metres per px
  const path = (list) => list.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const inFrame = (list) => list.some(([x, y]) => x >= left && x <= right && y >= top && y <= bottom);

  const ground = [];
  if (map) {
    for (const building of map.buildings ?? []) {
      const shapeOf = (building.pts ?? []).map(([east, north]) => [east, -north]);
      if (shapeOf.length > 2 && inFrame(shapeOf)) ground.push(svg("path", { class: "walk-strip-building", d: `${path(shapeOf)}Z` }));
    }
    for (const way of map.ways ?? []) {
      const wayLine = (way.pts ?? []).map(([east, north]) => [east, -north]);
      if (wayLine.length > 1 && inFrame(wayLine)) {
        ground.push(svg("path", { class: "walk-strip-way", "data-kind": way.kind, d: path(wayLine), "stroke-width": (way.kind === "street" ? 5 : 2.5) * px }));
      }
    }
  }

  const others = route.legs.filter((other) => other.id !== leg.id && other.line.length >= 2)
    .map((other) => svg("path", { class: "walk-strip-other", d: path(other.line.map(place)), "stroke-width": 2.5 * px }));

  const dot = (stop, kind) => {
    if (!stop || stop.lat === null || stop.lon === null) return null;
    const [x, y] = place([stop.lon, stop.lat]);
    const number = route.stops.indexOf(stop) + 1;
    return svg("g", { class: "walk-strip-stop", "data-kind": kind },
      svg("circle", { cx: x, cy: y, r: 9 * px, "stroke-width": 1.5 * px }),
      svg("text", { x, y: y + 3.8 * px, "font-size": 11 * px, "text-anchor": "middle" }, number));
  };

  return svg("svg", { class: "walk-strip", viewBox: `${left.toFixed(1)} ${top.toFixed(1)} ${(right - left).toFixed(1)} ${(bottom - top).toFixed(1)}`, role: "img", "aria-label": label },
    ground,
    others,
    svg("path", { class: "walk-strip-line", "data-kind": leg.kind === "routed" ? "routed" : "straight", d: path(points), "stroke-width": 4 * px,
      "stroke-dasharray": leg.kind === "routed" ? null : `${6 * px} ${6 * px}` }),
    benches.map(([x, y]) => svg("circle", { class: "walk-strip-bench", cx: x, cy: y, r: 3.5 * px, "stroke-width": 1.5 * px })),
    dot(from, "from"),
    dot(to, "to"),
    // The walk's line and the streets are OpenStreetMap's.
    svg("text", { class: "walk-strip-osm", x: right - 6 * px, y: bottom - 6 * px, "font-size": 9 * px, "text-anchor": "end" }, "© OpenStreetMap"));
}
