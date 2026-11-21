"""Conditions today that could be dangerous on a walk, and what they change on a route. Plain Python: no ADK, no model.

Two free sources without a key, both Open-Meteo (https://open-meteo.com): the forecast (rain, thunderstorm, heat,
UV, wind, cold, snow, ice, sunset) and the air-quality forecast. Python turns them into a small fixed verdict and a
list of dangers; no model judges the weather or writes a sentence here. Nothing is called dangerous that a source
did not report, and an empty list means "no warning found", never "safe".

Optional at run time: switched off, offline, timed out, an odd answer or any error gives no verdict, the route is
then built exactly as without this file, and one audit row says that the source was not available.

    fetch(lat, lon), fetch_air(lat, lon) -> (saved | None, "fresh" | "saved" | the reason there is none)
    judge(saved, air=None, at=None)      -> verdict | None
    ensure(state, agent, log)            -> verdict | None    # writes state["weather"] and state["dangers"]
    limit(state, limit_m, log)           -> the walking limit that applies today, in metres, or None
    facts(state)                         -> {} or {"weather": {...}}: what the router and the critic are told
    apply(state, model, profile, limit_m, log) -> the drafted route with the effects written into it

verdict: { summary: {en, ko}, verdict: "dry"|"rain"|"heat",    # one word for ordering places; no weather = unknown
           rain: "none"|"possible"|"likely", heat: "ok"|"hot"|"very_hot", cold: bool,
           shorter_walks: bool, dangers: [danger], local_time, sunrise, sunset, rain_chance_pct,
           feels_like_c: {min, max}, source_url, fetched_at, sources: [url],
           hours: [ {time, temperature_c, feels_like_c, rain_chance_pct, rain_mm, weather_code, wind_kmh, gust_kmh,
                     uv_index, snow_cm, us_aqi} ] }
danger:  { kind: "thunderstorm"|"ice"|"snow"|"rain"|"heat"|"wind"|"cold"|"air_quality"|"uv"|"darkness",
           level: "watch"|"warning", text: {en, ko}, effect: {en, ko}, source_url, valid_from, valid_to,
           shortens: bool }                # valid_from / valid_to: the first and the last forecast hour it is true for
"""
import copy
import json
import math
import os
import time
import urllib.request

from . import climb, osm

HERE = os.path.dirname(os.path.abspath(__file__))
URL = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
       "&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,"
       "wind_speed_10m,wind_gusts_10m,uv_index,snowfall&daily=sunrise,sunset&timezone=auto&forecast_days=1")
AIR_URL = ("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=%s&longitude=%s"
           "&hourly=us_aqi,pm2_5&timezone=auto&forecast_days=1")
TIMEOUT_S = 4
RECHECK_S = 300              # a verdict in the session is read again after five minutes; the file is kept for the hour
ROUTER = "router"

# Product choices, not measurements. All are about the hours of today that are still to come.
RAIN_LIKELY_PCT, RAIN_POSSIBLE_PCT = 60, 30      # the chance of rain in an hour
RAIN_LIKELY_MM, HEAVY_RAIN_MM = 1.0, 10.0        # or this much rain forecast in one hour
THUNDER_CODES = {95, 96, 99}                     # WMO weather codes as Open-Meteo gives them
ICE_CODES = {56, 57, 66, 67}                     # freezing drizzle and freezing rain
SNOW_CODES = {71, 73, 75, 77, 85, 86}
VERY_HOT_C, HOT_C = 35, 30                       # how it feels (apparent temperature)
COLD_C, VERY_COLD_C = 5, -5
UV_HIGH, UV_VERY_HIGH = 6, 8
GUST_STRONG_KMH, GUST_STORM_KMH = 50, 75
AQI_POOR, AQI_UNHEALTHY = 101, 151               # US AQI: unhealthy for sensitive groups, unhealthy
SUNSET_SOON_MIN = 120
PACE_M_PER_MIN = 50                              # a slow walk, to say which walks would end after sunset
SHORTER = 0.75                                   # a danger that shortens walks lowers the walking limit by a quarter
WORST_FIRST = ("thunderstorm", "ice", "snow", "rain", "heat", "wind", "cold", "air_quality", "uv", "darkness")

T = {
    "rain_watch": ("Rain likely this {part}", "오늘 {part} 비가 올 가능성이 높습니다"),
    "rain_warning": ("Heavy rain forecast this {part}, up to {n} mm in an hour", "오늘 {part} 큰비 예보: 한 시간에 최대 {n}mm"),
    "thunderstorm_warning": ("Thunderstorm forecast this {part}", "오늘 {part} 뇌우 예보가 있습니다"),
    "ice_warning": ("Freezing rain forecast this {part}", "오늘 {part} 어는 비 예보가 있습니다"),
    "snow_watch": ("Snow forecast this {part}", "오늘 {part} 눈 예보가 있습니다"),
    "heat_watch": ("Hot this {part}, feels like {n} °C", "오늘 {part} 덥습니다(체감 {n}°C)"),
    "heat_warning": ("Very hot this {part}, feels like {n} °C", "오늘 {part} 매우 덥습니다(체감 {n}°C)"),
    "uv_watch": ("High UV index this {part} ({n})", "오늘 {part} 자외선 지수가 높습니다({n})"),
    "uv_warning": ("Very high UV index this {part} ({n})", "오늘 {part} 자외선 지수가 매우 높습니다({n})"),
    "wind_watch": ("Strong gusts this {part}, up to {n} km/h", "오늘 {part} 강한 돌풍: 최대 시속 {n}km"),
    "wind_warning": ("Storm gusts this {part}, up to {n} km/h", "오늘 {part} 폭풍 수준의 돌풍: 최대 시속 {n}km"),
    "cold_watch": ("Cold this {part}, feels like {n} °C", "오늘 {part} 춥습니다(체감 {n}°C)"),
    "cold_warning": ("Very cold this {part}, feels like {n} °C", "오늘 {part} 매우 춥습니다(체감 {n}°C)"),
    "air_quality_watch": ("Poor air quality this {part} (US AQI {n})", "오늘 {part} 공기 질이 나쁩니다(미국 AQI {n})"),
    "air_quality_warning": ("Unhealthy air quality this {part} (US AQI {n})", "오늘 {part} 공기 질이 매우 나쁩니다(미국 AQI {n})"),
    "dark_now": ("It is dark now: sunset was at {t}", "지금은 어둡습니다: 해는 {t}에 졌습니다"),
    "dark_before_sunrise": ("It is dark now: sunrise is at {t}", "지금은 어둡습니다: 해는 {t}에 뜹니다"),
    "sunset_soon": ("Sunset is at {t}, in {n} minutes", "해는 {t}에 집니다({n}분 뒤)"),
    "effect_shorter": ("Walks are kept shorter today: the walking limit is lowered by a quarter.",
                       "오늘은 걷는 구간을 짧게 잡습니다: 걷는 거리 기준을 4분의 1 낮춥니다."),
    "effect_shown": ("Shown as a warning; the route itself is not changed.", "경고로 보여 드립니다. 경로는 바뀌지 않습니다."),
    "effect_dark": ("Walks that would end after sunset are flagged.", "해가 진 뒤에 끝나는 구간에 표시를 합니다."),
    "none_found": ("No warning found in today's forecast", "오늘 예보에서 경고를 찾지 못했습니다"),
    "rain_possible": ("rain possible this {part}", "{part}에 비가 올 수 있습니다"),
    "shorter": ("shorter walks", "걷는 구간을 짧게 잡습니다"),
    "morning": ("morning", "오전"), "afternoon": ("afternoon", "오후"), "evening": ("evening", "저녁"),
    "note_limit": ("Because of it, walks longer than {lowered} m are flagged today instead of {limit} m.",
                   "그래서 오늘은 {limit}m가 아니라 {lowered}m보다 긴 구간에 표시를 합니다."),
    "note_no_limit": ("You set no walking limit, so no walk is flagged for it.",
                      "걷는 거리 기준이 없어서 이 때문에 표시한 구간은 없습니다."),
    "note_more": ("{n} more warning(s) for today are listed with the route.", "오늘의 다른 경고 {n}건은 경로와 함께 보여 드립니다."),
    "note_benches": ("Benches the map marks as indoors or under cover are listed first.",
                     "지도에 실내이거나 지붕 아래로 표시된 벤치를 먼저 보여 드립니다."),
    "note_source": ("Source: Open-Meteo, read at {at}.", "출처: Open-Meteo, {at}에 읽음."),
    "long_walk": ("This walk is {m} m, longer than the {lowered} m that applies today ({why}; your limit is {limit} m).",
                  "이 구간은 {m}m로, 오늘 적용하는 {lowered}m보다 깁니다({why}. 원래 기준은 {limit}m)."),
    "walk_dark": ("This walk is in the dark: sunset was at {t}.", "이 구간은 어두울 때 걷게 됩니다: 해는 {t}에 졌습니다."),
    "walk_dark_morning": ("This walk is in the dark: sunrise is at {t}.", "이 구간은 어두울 때 걷게 됩니다: 해는 {t}에 뜹니다."),
    "walk_after_sunset": ("This walk would end after sunset ({t}) if you set out now; time at the stops is not counted.",
                          "지금 출발하면 이 구간은 해가 진 뒤({t})에 끝납니다. 들르는 곳에서 보내는 시간은 넣지 않았습니다."),
}


def _both(key, **kw):
    en, ko = T[key]
    pick = lambda i: {k: v[i] if isinstance(v, tuple) else v for k, v in kw.items()}  # noqa: E731
    return {"en": en.format(**pick(0)), "ko": ko.format(**pick(1))}


def _cache_dir():
    return os.environ.get("GILMATE_WEATHER_CACHE") or os.path.join(HERE, "..", "data", "cache", "weather")


def _get(name, template, lat, lon):
    """One Open-Meteo answer for one point: from the file saved this hour, or from the network.

    Returns (saved, how): saved is {source_url, fetched_at, forecast} or None; how is "saved", "fresh", or the
    reason there is nothing ("switched_off", "offline", the error's name).
    """
    if os.environ.get("GILMATE_WEATHER", "").strip().lower() in ("off", "0", "no", "false"):
        return None, "switched_off"
    lat, lon = round(float(lat), 3), round(float(lon), 3)
    url = template % (lat, lon)
    path = os.path.join(_cache_dir(), "%s_%s_%s_%s.json" % (name, lat, lon, time.strftime("%Y-%m-%dT%H", time.gmtime())))
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle), "saved"
        except (OSError, ValueError):
            pass
    if os.environ.get("GILMATE_OFFLINE"):            # the free checks never ask the network
        return None, "offline"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as answer:
            forecast = json.loads(answer.read().decode("utf-8"))
    except Exception as error:                       # no network, a timeout, an odd answer: nothing, never a crash
        return None, type(error).__name__
    if not isinstance(forecast, dict) or not isinstance(forecast.get("hourly"), dict):
        return None, "no_hourly_data"
    saved = {"source_url": url, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "forecast": forecast}
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(saved, handle, ensure_ascii=False)
    except OSError:
        pass
    return saved, "fresh"


def fetch(lat, lon):
    """Today's hourly forecast with sunrise and sunset."""
    return _get("forecast", URL, lat, lon)


def fetch_air(lat, lon):
    """Today's hourly air-quality forecast."""
    return _get("air", AIR_URL, lat, lon)


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _part(stamp):
    hour = int(stamp[11:13])
    return T["morning"] if hour < 12 else T["afternoon"] if hour < 18 else T["evening"]


def _minutes(stamp):
    """Minutes since midnight of "YYYY-MM-DDTHH:MM", or None."""
    try:
        return int(stamp[11:13]) * 60 + int(stamp[14:16])
    except (TypeError, ValueError, IndexError):
        return None


def _column(saved, name, at):
    """{hour stamp: number} for the hours of the day of `at` from its hour on."""
    hourly = ((saved or {}).get("forecast") or {}).get("hourly") or {}
    times, values, start = hourly.get("time") or [], hourly.get(name) or [], at[:13] + ":00"
    return {stamp: _number(values[i]) if i < len(values) else None for i, stamp in enumerate(times)
            if isinstance(stamp, str) and stamp[:10] == at[:10] and stamp >= start}


def judge(saved, air=None, at=None):
    """The verdict for the hours of today that are still to come, or None when the forecast holds no usable hour.

    at: the local time at the place as "YYYY-MM-DDTHH:MM"; by default the clock, moved to the place's time zone.
    A forecast without any rain value or without any temperature gives no verdict: missing data is not fine weather.
    """
    forecast = (saved or {}).get("forecast") or {}
    if at is None:
        at = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + (_number(forecast.get("utc_offset_seconds")) or 0)))
    columns = {key: _column(saved, name, at) for key, name in (
        ("temperature_c", "temperature_2m"), ("feels_like_c", "apparent_temperature"),
        ("rain_chance_pct", "precipitation_probability"), ("rain_mm", "precipitation"), ("weather_code", "weather_code"),
        ("wind_kmh", "wind_speed_10m"), ("gust_kmh", "wind_gusts_10m"), ("uv_index", "uv_index"), ("snow_cm", "snowfall"))}
    columns["us_aqi"] = _column(air, "us_aqi", at) if air else {}
    hours = []
    for stamp in sorted(columns["temperature_c"]):
        row = {"time": stamp, **{key: values.get(stamp) for key, values in columns.items()}}
        if row["feels_like_c"] is None:
            row["feels_like_c"] = row["temperature_c"]
        hours.append(row)
    felt = [h["feels_like_c"] for h in hours if h["feels_like_c"] is not None]
    if not felt or not any(h["rain_chance_pct"] is not None or h["rain_mm"] is not None for h in hours):
        return None
    source, air_source = saved.get("source_url") or "https://open-meteo.com", (air or {}).get("source_url")
    dangers = []

    def when(test):
        return [h for h in hours if test(h)]

    def add(kind, level, found, shortens, n=None, url=source):
        if found:
            dangers.append({"kind": kind, "level": level, "text": _both("%s_%s" % (kind, level), part=_part(found[0]["time"]), n=n),
                            "effect": _both("effect_shorter" if shortens else "effect_shown"), "source_url": url,
                            "valid_from": found[0]["time"], "valid_to": found[-1]["time"], "shortens": shortens})
        return bool(found)

    def top(found, key, low=False):
        values = [h[key] for h in found if h[key] is not None]
        return round(min(values) if low else max(values)) if values else None

    # 1. rain and thunderstorm
    likely = when(lambda h: (h["rain_chance_pct"] or 0) >= RAIN_LIKELY_PCT or (h["rain_mm"] or 0) >= RAIN_LIKELY_MM)
    possible = when(lambda h: (h["rain_chance_pct"] or 0) >= RAIN_POSSIBLE_PCT or (h["rain_mm"] or 0) >= 0.1)
    heavy = when(lambda h: (h["rain_mm"] or 0) >= HEAVY_RAIN_MM)
    add("thunderstorm", "warning", when(lambda h: h["weather_code"] in THUNDER_CODES), True)
    add("rain", "warning", heavy, True, top(heavy, "rain_mm")) or add("rain", "watch", likely, True)
    # 2. heat and UV
    very_hot, hot = when(lambda h: (h["feels_like_c"] or 0) >= VERY_HOT_C), when(lambda h: (h["feels_like_c"] or 0) >= HOT_C)
    add("heat", "warning", very_hot, True, top(very_hot, "feels_like_c")) or add("heat", "watch", hot, False, top(hot, "feels_like_c"))
    uv_top, uv = when(lambda h: (h["uv_index"] or 0) >= UV_VERY_HIGH), when(lambda h: (h["uv_index"] or 0) >= UV_HIGH)
    add("uv", "warning", uv_top, False, top(uv_top, "uv_index")) or add("uv", "watch", uv, False, top(uv, "uv_index"))
    # 3. strong wind and gusts
    for h in hours:
        h["_gust"] = h["gust_kmh"] if h["gust_kmh"] is not None else h["wind_kmh"]
    storm, strong = when(lambda h: (h["_gust"] or 0) >= GUST_STORM_KMH), when(lambda h: (h["_gust"] or 0) >= GUST_STRONG_KMH)
    add("wind", "warning", storm, True, top(storm, "_gust")) or add("wind", "watch", strong, False, top(strong, "_gust"))
    for h in hours:
        del h["_gust"]
    # 4. cold, snow, ice
    very_cold = when(lambda h: h["feels_like_c"] is not None and h["feels_like_c"] <= VERY_COLD_C)
    cold_hours = when(lambda h: h["feels_like_c"] is not None and h["feels_like_c"] <= COLD_C)
    add("cold", "warning", very_cold, True, top(very_cold, "feels_like_c", low=True)) \
        or add("cold", "watch", cold_hours, False, top(cold_hours, "feels_like_c", low=True))
    add("ice", "warning", when(lambda h: h["weather_code"] in ICE_CODES), True)
    add("snow", "watch", when(lambda h: h["weather_code"] in SNOW_CODES or (h["snow_cm"] or 0) > 0), True)
    # 5. darkness, from today's sunrise and sunset
    daily = forecast.get("daily") or {}
    sunrise, sunset = ((daily.get(key) or [None])[0] for key in ("sunrise", "sunset"))
    sunrise = sunrise if isinstance(sunrise, str) and sunrise[:10] == at[:10] else None
    sunset = sunset if isinstance(sunset, str) and sunset[:10] == at[:10] else None
    dark = None
    if sunset and at >= sunset:
        dark = (_both("dark_now", t=sunset[11:16]), sunset, at[:10] + "T23:59")
    elif sunrise and at < sunrise:
        dark = (_both("dark_before_sunrise", t=sunrise[11:16]), at, sunrise)
    elif sunset and _minutes(sunset) - _minutes(at) <= SUNSET_SOON_MIN:
        dark = (_both("sunset_soon", t=sunset[11:16], n=_minutes(sunset) - _minutes(at)), sunset, at[:10] + "T23:59")
    if dark:
        dangers.append({"kind": "darkness", "level": "watch", "text": dark[0], "effect": _both("effect_dark"),
                        "source_url": source, "valid_from": dark[1], "valid_to": dark[2], "shortens": False})
    # 6. air quality, when its own source answered
    unhealthy, poor = when(lambda h: (h["us_aqi"] or 0) >= AQI_UNHEALTHY), when(lambda h: (h["us_aqi"] or 0) >= AQI_POOR)
    add("air_quality", "warning", unhealthy, True, top(unhealthy, "us_aqi"), air_source) \
        or add("air_quality", "watch", poor, False, top(poor, "us_aqi"), air_source)

    dangers.sort(key=lambda d: (d["level"] != "warning", WORST_FIRST.index(d["kind"])))
    shorter = any(d["shortens"] for d in dangers)
    rain = "likely" if likely else "possible" if possible else "none"
    if dangers:
        summary = dict(dangers[0]["text"])
    else:
        summary = _both("none_found")
        if rain == "possible":
            summary = {lang: "%s; %s" % (summary[lang], _both("rain_possible", part=_part(possible[0]["time"]))[lang])
                       for lang in ("en", "ko")}
    if shorter:
        summary = {lang: "%s: %s" % (summary[lang], _both("shorter")[lang]) for lang in ("en", "ko")}
    chances = [h["rain_chance_pct"] for h in hours if h["rain_chance_pct"] is not None]
    wet_or_frozen = likely or any(d["kind"] in ("thunderstorm", "snow", "ice") for d in dangers)
    return {"summary": summary, "verdict": "rain" if wet_or_frozen else "heat" if very_hot else "dry", "rain": rain, "heat": "very_hot" if very_hot else "hot" if hot else "ok",
            "cold": bool(cold_hours), "shorter_walks": shorter, "dangers": dangers,
            "local_time": at, "sunrise": sunrise, "sunset": sunset,
            "rain_chance_pct": round(max(chances)) if chances else None,
            "feels_like_c": {"min": round(min(felt)), "max": round(max(felt))},
            "source_url": source, "fetched_at": saved.get("fetched_at"),
            "sources": [source] + ([air_source] if air_source else []), "hours": hours}


def _centre(state):
    """The middle of the area being visited, or None when the session names no area."""
    bbox = (state.get("area") or {}).get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    south, west, north, east = bbox
    return (south + north) / 2, (west + east) / 2


def ensure(state, agent, log):
    """The verdict for the area of this session, read at most once in five minutes.

    Writes state["weather"] (the verdict or None) and state["dangers"] (its list; None when no source answered,
    which is "unknown", not "nothing found"). log is tools.log. One audit row per source and reading: rule
    "weather" or "air_quality" with what was found, or "weather_not_available" / "air_quality_not_available" with
    the reason. A session without an area (the older questions-first page) has no place to read the weather for:
    nothing is fetched and nothing is logged.
    """
    try:
        checked = state.get("weather_checked_at") or 0
        if checked and 0 <= time.time() - checked < RECHECK_S:
            return state.get("weather") or None
        centre = _centre(state)
        if centre is None:
            return None
        saved, how = fetch(*centre)
        air, air_how = fetch_air(*centre) if saved else (None, "not_asked")
        verdict = judge(saved, air) if saved else None
        if saved and verdict is None:
            how = "no_usable_hours"
        state["weather"] = verdict
        state["dangers"] = verdict["dangers"] if verdict else None
        state["weather_checked_at"] = time.time()
        if not verdict:
            log(state, agent, "weather_today", "allowed", "weather_not_available",
                "source=open-meteo.com; reason=%s; the route is built without it" % how)
            return None
        found = [d for d in verdict["dangers"] if d["kind"] != "air_quality"]
        log(state, agent, "weather_today", "allowed", "weather", "rain=%s; heat=%s; cold=%s; dangers=%s; shorter_walks=%s; source=open-meteo.com; from=%s" % (
            verdict["rain"], verdict["heat"], "yes" if verdict["cold"] else "no",
            ",".join("%s:%s" % (d["kind"], d["level"]) for d in found) or "none_found",
            "yes" if verdict["shorter_walks"] else "no", how))
        if air:
            worst = [d["level"] for d in verdict["dangers"] if d["kind"] == "air_quality"]
            log(state, agent, "weather_today", "allowed", "air_quality",
                "air_quality=%s; source=air-quality-api.open-meteo.com; from=%s" % (worst[0] if worst else "no_warning_found", air_how))
        else:
            log(state, agent, "weather_today", "allowed", "air_quality_not_available",
                "source=air-quality-api.open-meteo.com; reason=%s" % air_how)
        return verdict
    except Exception:                                # whatever happens here, the route is built as without weather
        return None


def order_hint(state):
    """One word for whoever orders places: "rain" (indoors first), "heat", "dry", or "unknown" without a verdict."""
    verdict = state.get("weather") or None
    return verdict.get("verdict", "unknown") if isinstance(verdict, dict) else "unknown"


def lowered(limit_m, verdict):
    """The walking limit that applies today: a quarter lower when a danger shortens walks (rain likely, very hot, ...)."""
    if not verdict or not verdict.get("shorter_walks") or limit_m is None:
        return limit_m
    return int(round(limit_m * SHORTER))


def limit(state, limit_m, log):
    """The walking limit that applies today (see lowered). Reads the weather when the session has none yet."""
    try:
        return lowered(limit_m, ensure(state, ROUTER, log))
    except Exception:
        return limit_m


def facts(state):
    """What the router and the critic are told with their route facts: {} without a verdict."""
    verdict = state.get("weather") or None
    if not isinstance(verdict, dict) or not verdict.get("summary"):
        return {}
    told = {k: verdict.get(k) for k in ("rain", "heat", "cold", "shorter_walks", "sunset", "local_time")}
    told["summary"] = verdict["summary"]["en"]
    told["dangers"] = [{"kind": d["kind"], "level": d["level"], "text": d["text"]["en"], "effect": d["effect"]["en"]}
                       for d in verdict.get("dangers") or []] or "no warning found (that is not a promise of safety)"
    told["source"] = "open-meteo.com, fetched %s" % verdict.get("fetched_at")
    told["what_it_changes"] = (
        "The walking limit is lowered by a quarter today; her_limit_m already is the lowered one. Prefer the order "
        "with the shortest single walks and say in a walk's advice when it is over that limit because of the weather."
        if verdict.get("shorter_walks") else "The walking limit is unchanged. Name only dangers listed here.")
    return {"weather": told}


_covered = {}


def covered_benches():
    """Ids of the benches the map marks as indoors or under cover (indoor=yes, covered=yes). Empty when unknown."""
    extract = getattr(osm, "EXTRACT", None)
    if not extract:
        return set()
    if extract not in _covered:
        try:
            with open(extract, encoding="utf-8") as handle:
                elements = json.load(handle)["elements"]
            _covered[extract] = {
                "%s/%s" % (e["type"], e["id"]) for e in elements
                if (e.get("tags") or {}).get("amenity") == "bench"
                and (e["tags"].get("indoor") == "yes" or e["tags"].get("covered") in ("yes", "roof", "building"))}
        except Exception:
            _covered[extract] = set()
    return _covered[extract]


def _hazard(model, leg, kind, detail, source):
    mid = leg["line"][len(leg["line"]) // 2]
    model["hazards"].append({"id": "h%d" % (len(model["hazards"]) + 1), "leg_id": leg["id"], "stop_id": None, "kind": kind,
                             "cause": "weather", "lat": mid[1], "lon": mid[0], "detail": detail, "source": source})


def _apply(model, verdict, profile, limit_m, at=None):
    low = lowered(limit_m, verdict)
    dangers = verdict.get("dangers") or []
    flagged, dark_legs, covered_shown = [], [], 0
    if verdict.get("shorter_walks"):
        why = next(d for d in dangers if d["shortens"])
        for leg in model["legs"]:
            if low is not None and limit_m is not None and low < leg["distance_m"] <= limit_m:
                leg["fits_profile"] = False
                flagged.append(leg["id"])
                detail = _both("long_walk", m=leg["distance_m"], lowered=low, limit=limit_m,
                               why=(why["text"]["en"][0].lower() + why["text"]["en"][1:], why["text"]["ko"]))
                _hazard(model, leg, "long_walk", detail, why["source_url"])
        under_cover = covered_benches()
        if under_cover:
            benches = []
            for leg in model["legs"]:
                near = osm.rest_spots(leg["line"])
                if not any(b["id"] in under_cover for b in near):
                    benches += [b for b in model["benches"] if b["leg_id"] == leg["id"]]
                    continue
                near.sort(key=lambda b: b["id"] not in under_cover)          # stable: the nearest of each kind first
                for bench in near[:osm.benches_shown(profile)]:
                    entry = {"id": "", "leg_id": leg["id"], "lat": bench["lat"], "lon": bench["lon"],
                             "off_route_m": bench["off_route_m"], "source": bench["source"]}
                    if bench["id"] in under_cover:
                        entry["covered"] = True
                        covered_shown += 1
                    benches.append(entry)
            for i, bench in enumerate(benches):
                bench["id"] = "b%d" % (i + 1)
            model["benches"] = benches
    # darkness: which walks would end after sunset when setting out now, walking slowly, with no time at the stops
    sunrise, sunset = verdict.get("sunrise"), verdict.get("sunset")
    at = at or verdict.get("local_time")             # the local time of the reading, at most five minutes old
    if sunset and at and at[:10] == sunset[:10]:
        clock = _minutes(at)
        for leg in model["legs"]:
            clock += leg["distance_m"] / PACE_M_PER_MIN
            if at >= sunset:
                detail = _both("walk_dark", t=sunset[11:16])
            elif sunrise and at < sunrise:
                detail = _both("walk_dark_morning", t=sunrise[11:16])
            elif clock > _minutes(sunset):
                detail = _both("walk_after_sunset", t=sunset[11:16])
            else:
                continue
            dark_legs.append(leg["id"])
            _hazard(model, leg, "darkness", detail, verdict["source_url"])
    said = [{lang: verdict["summary"][lang] + "." for lang in ("en", "ko")}]
    if verdict.get("shorter_walks"):
        said.append(_both("note_limit", lowered=low, limit=limit_m) if low is not None else _both("note_no_limit"))
    if len(dangers) > 1:
        said.append(_both("note_more", n=len(dangers) - 1))
    if covered_shown:
        said.append(_both("note_benches"))
    said.append(_both("note_source", at=str(verdict.get("fetched_at") or "")[11:16] or "?"))
    model["weather"] = {
        "summary": verdict["summary"], "rain": verdict["rain"], "heat": verdict["heat"], "cold": verdict["cold"],
        "shorter_walks": bool(verdict.get("shorter_walks")), "dangers": dangers,
        "usual_walk_limit_m": limit_m, "walk_limit_m": low, "flagged_legs": flagged, "dark_legs": dark_legs,
        "covered_benches": covered_shown, "note": {lang: " ".join(s[lang] for s in said) for lang in ("en", "ko")},
        "source_url": verdict["source_url"], "fetched_at": verdict.get("fetched_at")}
    return model


def apply(state, model, profile, limit_m, log):
    """Writes the effects of today's conditions into a drafted route, by rule. Returns the model (changed in place).

    Without a verdict nothing is touched. With no danger only the key "weather" is added, for the route note.
    A danger that shortens walks: a walk between the lowered limit and the usual one no longer fits and gets a
    long_walk warning with cause "weather" and the forecast as its source; benches the map marks as indoors or
    under cover are listed first on the walks that have one. Darkness: a walk that would end after sunset gets a
    warning of kind "darkness". The climb of each walk (gilmate/climb.py) is written first, only when
    GILMATE_CLIMB=on: it is off by default because the heights proved too rough in Shibuya (see climb.py).
    """
    if os.environ.get("GILMATE_CLIMB", "").strip().lower() == "on":
        climb.apply(state, model, profile, log)
    try:
        verdict = ensure(state, ROUTER, log)
        if not verdict:
            return model
        changed = _apply(copy.deepcopy(model), verdict, profile or {}, limit_m, verdict.get("local_time"))
        model.clear()
        model.update(changed)
    except Exception:
        pass
    return model
