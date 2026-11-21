"""The climb on each walk: metres up and down, from ground heights along the walk's line. Plain Python, no ADK.

The heights come from Open-Meteo's elevation endpoint (https://api.open-meteo.com/v1/elevation, free, no key), a
90 m grid, so every number is "about". The map has stairs but no hills; this adds the hills. A walk that climbs
more than a fixed number of metres for the person's answer about stairs is flagged, and for "avoid" it no longer
fits, like stairs.

SWITCHED OFF BY DEFAULT (GILMATE_CLIMB=on switches it on). Measured on 2026-11-21: the heights are a surface model
that includes buildings and raised tracks. Along the flat walk from Shibuya Hikarie to the Scramble Crossing the
samples read 34, 34, 32, 43, 35, 41, 41 m, which this file would report as "climbs about 17 m". In Hongdae the
samples looked like ground (16 to 22 m, 23 to 31 m). Until the numbers are checked against a ground model, a climb
shown as a fact would be wrong in the centre of Shibuya, so no route carries it.

Optional at run time: a height that is neither saved nor answered is unknown, the walk then has
no climb_m and nothing is flagged for it.

    heights(points)                    -> ([metres | None], "saved" | "fresh" | the reason some are missing)
    of_line(line)                      -> ({climb_m, descent_m} | None, how)       # line: [[lon, lat], ...]
    apply(state, model, profile, log)  -> the drafted route with climb_m / descent_m on each walk and its warnings
"""
import json
import math
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://api.open-meteo.com/v1/elevation?latitude=%s&longitude=%s"
SOURCE = "https://api.open-meteo.com/v1/elevation"
TIMEOUT_S = 4
STEP_M = 90                                       # one height about every 90 m of a walk: the grid is no finer
MOST = 12                                         # heights per walk at most
# Product choices, not measurements: from how many metres up a walk is called steep, by the answer about stairs.
STEEP_M = {"avoid": 8, "few": 12, "ok": 20}

T = {
    "steep": ("This walk climbs about {up} m (ground heights from Open-Meteo on a 90 m grid).",
              "이 구간은 약 {up}m 올라갑니다(Open-Meteo의 90m 격자 지면 높이 기준)."),
}


def _cache_path():
    return os.environ.get("GILMATE_ELEVATION_CACHE") or os.path.join(HERE, "..", "data", "cache", "elevation", "heights.json")


def _key(lat, lon):
    return "%.4f,%.4f" % (lat, lon)


def _saved():
    try:
        with open(_cache_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def heights(points):
    """Ground heights in metres for (lat, lon) points; None where neither the saved file nor the source has one."""
    saved = _saved()
    missing = sorted({_key(*p) for p in points} - set(saved))
    how = "saved"
    if missing:
        if os.environ.get("GILMATE_WEATHER", "").strip().lower() in ("off", "0", "no", "false"):
            how = "switched_off"
        elif os.environ.get("GILMATE_OFFLINE"):
            how = "offline"
        else:
            try:
                url = URL % (",".join(k.split(",")[0] for k in missing), ",".join(k.split(",")[1] for k in missing))
                with urllib.request.urlopen(url, timeout=TIMEOUT_S) as answer:
                    found = json.loads(answer.read().decode("utf-8")).get("elevation")
                if not isinstance(found, list) or len(found) != len(missing):
                    raise ValueError("unexpected answer")
                for key, metres in zip(missing, found):
                    if isinstance(metres, (int, float)) and not isinstance(metres, bool) and math.isfinite(metres):
                        saved[key] = metres
                how = "fresh"
                os.makedirs(os.path.dirname(_cache_path()), exist_ok=True)
                with open(_cache_path(), "w", encoding="utf-8") as handle:
                    json.dump(saved, handle, indent=0, sort_keys=True)
            except Exception as error:                   # no network, a timeout, an odd answer: unknown, never a crash
                how = type(error).__name__
    return [saved.get(_key(*p)) for p in points], how


def _samples(line):
    """Points about every STEP_M along a walk's line, its two ends included: [(lat, lon)]."""
    pts = [(lat, lon) for lon, lat in line]
    if len(pts) < 2:
        return pts
    scale = math.cos(math.radians(pts[0][0]))
    lengths = [math.hypot((b[0] - a[0]) * 111320.0, (b[1] - a[1]) * 111320.0 * scale) for a, b in zip(pts, pts[1:])]
    total = sum(lengths)
    count = max(2, min(MOST, int(total // STEP_M) + 2))
    out, done, i = [], 0.0, 0
    for n in range(count):
        target = total * n / (count - 1)
        while i < len(lengths) - 1 and done + lengths[i] < target:
            done += lengths[i]
            i += 1
        part = (target - done) / lengths[i] if lengths[i] else 0.0
        a, b = pts[i], pts[i + 1]
        out.append((round(a[0] + (b[0] - a[0]) * part, 4), round(a[1] + (b[1] - a[1]) * part, 4)))
    return out


def of_line(line):
    """({climb_m, descent_m}, how) for one walk, or (None, why) when a height along it is unknown."""
    found, how = heights(_samples(line))
    if len(found) < 2 or any(h is None for h in found):
        return None, how
    steps = [b - a for a, b in zip(found, found[1:])]
    return {"climb_m": int(round(sum(s for s in steps if s > 0))), "descent_m": int(round(-sum(s for s in steps if s < 0)))}, how


def apply(state, model, profile, log):
    """Writes climb_m and descent_m on every walk of a drafted route and flags the steep ones. Changes the model in place.

    Only for a session with an area (the map-first flow), like the weather. A walk whose heights are unknown is
    left as it was: no climb_m, no warning. A steep walk gets a warning of kind "climb" with its source; with the answer
    "avoid" about stairs it no longer fits, as with stairs. One audit row per draft, tool "climb".
    """
    try:
        if not (state.get("area") or {}).get("bbox"):
            return model
        limit = STEEP_M.get((profile or {}).get("stairs"), STEEP_M["ok"])
        known, steep, hows, hazards, changes = 0, [], set(), [], []
        for leg in model["legs"]:
            found, how = of_line(leg["line"])
            hows.add(how)
            changes.append((leg, found))
            if not found:
                continue
            known += 1
            if found["climb_m"] >= limit:
                steep.append(leg["id"])
                mid = leg["line"][len(leg["line"]) // 2]
                hazards.append({"leg_id": leg["id"], "stop_id": None, "kind": "climb", "cause": "elevation",
                                "lat": mid[1], "lon": mid[0], "source": SOURCE,
                                "detail": {"en": T["steep"][0].format(up=found["climb_m"]), "ko": T["steep"][1].format(up=found["climb_m"])}})
        for leg, found in changes:                       # written only after every walk was read without an error
            if found:                                    # an unknown climb leaves the walk exactly as it was
                leg["climb_m"], leg["descent_m"], leg["climb_source"] = found["climb_m"], found["descent_m"], SOURCE
            if leg["id"] in steep and (profile or {}).get("stairs") == "avoid":
                leg["fits_profile"] = False
        for hazard in hazards:
            model["hazards"].append({"id": "h%d" % (len(model["hazards"]) + 1), **hazard})
        how = "fresh" if "fresh" in hows else "saved" if hows == {"saved"} else sorted(hows - {"saved", "fresh"})[0] if hows else "no_walks"
        log(state, ROUTER, "climb", "allowed", "elevation" if known else "elevation_not_available",
            "walks=%d; known=%d; steep=%d; source=open-meteo.com; %s=%s" % (
                len(model["legs"]), known, len(steep), "from" if known == len(model["legs"]) else "reason", how))
    except Exception:
        pass
    return model


ROUTER = "router"
