// Reading helpers for the spatial model (CONTRACT.md section 1). No drawing, no fetching.

export function orderedStops(model) {
  const stops = Array.isArray(model?.stops) ? [...model.stops] : [];
  return stops.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

/** The leg that leaves this stop, or null at the last stop. */
export function legFrom(model, stopId) {
  return (model?.legs ?? []).find((leg) => leg.from === stopId) ?? null;
}

export function legHazards(model, leg) {
  if (!leg) return [];
  return (model?.hazards ?? []).filter((hazard) => hazard.leg_id === leg.id);
}

export function stopHazards(model, stop) {
  return (model?.hazards ?? []).filter((hazard) => hazard.stop_id === stop.id);
}

export function legBenches(model, leg) {
  if (!leg) return [];
  return (model?.benches ?? []).filter((bench) => bench.leg_id === leg.id);
}

/** Sum of the leg distances, or null when any of them is unknown. */
export function totalDistance(model) {
  let sum = 0;
  for (const leg of model?.legs ?? []) {
    if (!Number.isFinite(Number(leg.distance_m)) || leg.distance_m === null) return null;
    sum += Number(leg.distance_m);
  }
  return sum;
}

/** The leg's line as [[lon, lat]]; when it has none, the straight segment between its two stops. */
export function legLine(model, leg) {
  if (Array.isArray(leg.line) && leg.line.length >= 2) return leg.line;
  const from = (model.stops ?? []).find((stop) => stop.id === leg.from);
  const to = (model.stops ?? []).find((stop) => stop.id === leg.to);
  if (!from || !to) return [];
  return [[from.lon, from.lat], [to.lon, to.lat]];
}

/**
 * Today's weather as Python judged it (CONTRACT.md section 9): { summary: {en, ko}, worst: danger | null }, or
 * null when the data holds no forecast. `worst` is the first of the dangers, which Python orders worst first.
 * The route on the screen is asked first; a saved run that is being told again is asked for its own route's.
 */
export function dayWeather(app) {
  const found = [app.model?.weather, app.source?.kind !== "live" ? app.run?.spatial_model?.weather : null]
    .find((weather) => weather && typeof weather === "object" && weather.summary && typeof weather.summary === "object");
  if (!found) return null;
  const dangers = Array.isArray(found.dangers) ? found.dangers.filter((danger) => danger && danger.text && typeof danger.text === "object") : [];
  return { summary: found.summary, worst: dangers[0] ?? null };
}
