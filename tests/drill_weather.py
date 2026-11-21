"""Drill: today's conditions become a fixed verdict and a list of dangers, and change a route only by rule.

With saved forecasts (dry, rain likely, very hot) and variants made from them (thunderstorm, gusts, cold, snow,
ice, heavy rain, bad air, after sunset) the verdict and the route flags are as the rules in gilmate/weather.py say.
With the source not answering (offline, switched off, an unusable answer) the route is exactly the one built
without weather, and one audit row says so. Uses the map extract in data/. No network, no key, no model.

Run from the repo folder: python3 tests/drill_weather.py
"""
import copy
import json
import os
import sys
import tempfile
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="gilmate-drill-weather-")
os.environ["AUDIT_LOG"] = os.path.join(TMP, "audit.jsonl")
os.environ["GILMATE_OFFLINE"] = "1"
os.environ["GILMATE_WEATHER_CACHE"] = os.path.join(TMP, "weather")
os.environ["GILMATE_ELEVATION_CACHE"] = os.path.join(TMP, "heights.json")       # no heights saved: climbs are unknown
os.environ.pop("GILMATE_WEATHER", None)
os.environ.pop("GILMATE_CLIMB", None)                 # the climb is off by default; section 5 calls it directly

from gilmate import climb, note, osm, progress, weather  # noqa: E402

FAILED = []


def check(name, ok, got=None):
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  (got %r)" % (got,)))
    if not ok:
        FAILED.append(name)


def fixture(name):
    return json.load(open(os.path.join(REPO, "tests", "fixtures", "weather_%s.json" % name), encoding="utf-8"))


def changed(saved, **columns):
    """A copy of a forecast with some hourly columns replaced: a number for every hour, or {hour: number}."""
    out = copy.deepcopy(saved)
    for column, value in columns.items():
        old = out["forecast"]["hourly"][column]
        out["forecast"]["hourly"][column] = [value.get(h, old[h]) if isinstance(value, dict) else value for h in range(24)]
    return out


def kinds(verdict):
    return [(d["kind"], d["level"]) for d in verdict["dangers"]]


DRY, RAIN, HOT = fixture("dry"), fixture("rain_likely"), fixture("very_hot")
DAY, MORNING = "2026-11-21", "2026-11-21T09:00"

# ---- 1. the verdict --------------------------------------------------------------------------------------------
v = weather.judge(DRY, at=MORNING)
check("dry: no rain, no heat, not cold, nothing shortened", (v["rain"], v["heat"], v["cold"], v["shorter_walks"]) == ("none", "ok", False, False), v)
check("dry: the list of dangers is empty and the words are 'no warning found', never 'safe'",
      v["dangers"] == [] and v["summary"]["en"] == "No warning found in today's forecast" and "safe" not in v["summary"]["en"].lower(), v["summary"])
check("dry: the verdict names its source and holds only the hours still to come",
      v["source_url"] == DRY["source_url"] and v["hours"][0]["time"] == MORNING and len(v["hours"]) == 15, len(v["hours"]))

v = weather.judge(RAIN, at=MORNING)
check("rain likely: the verdict says so and walks are shortened", (v["rain"], v["shorter_walks"]) == ("likely", True), v)
check("rain likely: one danger, a watch, from the first rainy hour, with its source",
      kinds(v) == [("rain", "watch")] and v["dangers"][0]["valid_from"] == DAY + "T13:00"
      and v["dangers"][0]["valid_to"] == DAY + "T23:00" and v["dangers"][0]["source_url"] == RAIN["source_url"], v["dangers"])
check("rain likely: the line for the page", v["summary"] == {"en": "Rain likely this afternoon: shorter walks",
                                                           "ko": "오늘 오후 비가 올 가능성이 높습니다: 걷는 구간을 짧게 잡습니다"}, v["summary"])
check("every danger has kind, level, text, effect, source and the hours it is true for",
      all(sorted(d) == ["effect", "kind", "level", "shortens", "source_url", "text", "valid_from", "valid_to"]
          and d["level"] in ("watch", "warning") and d["text"]["en"] and d["text"]["ko"] and d["effect"]["en"]
          for d in v["dangers"]), v["dangers"])
v = weather.judge(changed(DRY, precipitation_probability={6: 90, 7: 90}, precipitation={6: 3.0}), at=MORNING)
check("rain that has passed is not reported", v["rain"] == "none" and v["dangers"] == [], v["dangers"])
v = weather.judge(changed(DRY, precipitation_probability={14: 40}), at=MORNING)
check("rain possible is said but is no danger and shortens nothing",
      v["rain"] == "possible" and v["dangers"] == [] and not v["shorter_walks"] and "rain possible this afternoon" in v["summary"]["en"], v["summary"])
v = weather.judge(changed(RAIN, precipitation={15: 14.0}, weather_code={15: 95}), at=MORNING)
check("thunderstorm and heavy rain are warnings, the thunderstorm named first",
      kinds(v) == [("thunderstorm", "warning"), ("rain", "warning")] and v["summary"]["en"].startswith("Thunderstorm forecast this afternoon")
      and "14 mm" in v["dangers"][1]["text"]["en"], v["dangers"])

v = weather.judge(HOT, at="2026-08-01T09:00")
check("very hot: heat and UV are warnings, walks are shortened",
      v["heat"] == "very_hot" and kinds(v) == [("heat", "warning"), ("uv", "warning")] and v["shorter_walks"], kinds(v))
check("very hot: the line for the page", v["summary"]["en"] == "Very hot this morning, feels like 37 °C: shorter walks", v["summary"])
check("UV alone changes no route", [d["shortens"] for d in v["dangers"]] == [True, False], v["dangers"])
v = weather.judge(changed(DRY, apparent_temperature={13: 31}), at=MORNING)
check("hot but not very hot: a watch, nothing shortened", v["heat"] == "hot" and kinds(v) == [("heat", "watch")] and not v["shorter_walks"], kinds(v))

v = weather.judge(changed(DRY, wind_gusts_10m={12: 55}), at=MORNING)
check("strong gusts: a watch, nothing shortened", kinds(v) == [("wind", "watch")] and not v["shorter_walks"] and "55 km/h" in v["dangers"][0]["text"]["en"], v["dangers"])
v = weather.judge(changed(DRY, wind_gusts_10m={12: 82}), at=MORNING)
check("storm gusts: a warning, walks shortened", kinds(v) == [("wind", "warning")] and v["shorter_walks"], v["dangers"])
v = weather.judge(changed(DRY, apparent_temperature={20: 3, 21: 2}), at=MORNING)
check("cold: a watch from the coldest hours, nothing shortened",
      v["cold"] is True and kinds(v) == [("cold", "watch")] and "2 °C" in v["dangers"][0]["text"]["en"] and not v["shorter_walks"], v["dangers"])
v = weather.judge(changed(DRY, apparent_temperature=-8, weather_code={12: 73, 13: 66}, snowfall={12: 1.2}), at=MORNING)
check("very cold, snow and freezing rain: ice and cold are warnings, snow a watch, walks shortened",
      kinds(v) == [("ice", "warning"), ("cold", "warning"), ("snow", "watch")] and v["shorter_walks"], kinds(v))

v = weather.judge(DRY, at=DAY + "T15:00")
check("sunset within two hours is a watch that names the time",
      kinds(v) == [("darkness", "watch")] and v["dangers"][0]["text"]["en"] == "Sunset is at 16:31, in 91 minutes" and not v["shorter_walks"], v["dangers"])
v = weather.judge(DRY, at=DAY + "T17:10")
check("after sunset it says that it is dark now", kinds(v) == [("darkness", "watch")]
      and v["dangers"][0]["text"]["en"] == "It is dark now: sunset was at 16:31" and v["sunset"] == DAY + "T16:31", v["dangers"])
check("in the morning darkness is not on the list", kinds(weather.judge(DRY, at=MORNING)) == [])

AIR = {"source_url": "https://air-quality-api.open-meteo.com/v1/air-quality?fixture=air",
       "forecast": {"hourly": {"time": [DAY + "T%02d:00" % h for h in range(24)], "us_aqi": [40] * 24}}}
check("clean air adds nothing", kinds(weather.judge(DRY, AIR, at=MORNING)) == [])
v = weather.judge(DRY, changed(AIR, us_aqi={14: 112}), at=MORNING)
check("poor air is a watch with the air source as its source",
      kinds(v) == [("air_quality", "watch")] and v["dangers"][0]["source_url"] == AIR["source_url"] and not v["shorter_walks"], v["dangers"])
v = weather.judge(DRY, changed(AIR, us_aqi={14: 163}), at=MORNING)
check("unhealthy air is a warning and shortens walks", kinds(v) == [("air_quality", "warning")] and v["shorter_walks"] and "163" in v["dangers"][0]["text"]["en"], v["dangers"])

check("a forecast without rain values gives no verdict: missing data is not fine weather",
      weather.judge(changed(DRY, precipitation_probability=None, precipitation=None), at=MORNING) is None)
check("a forecast without temperatures gives no verdict",
      weather.judge(changed(DRY, temperature_2m=None, apparent_temperature=None), at=MORNING) is None)
check("a forecast for another day gives no verdict", weather.judge(DRY, at="2026-11-22T09:00") is None)
check("an empty answer gives no verdict", weather.judge({"forecast": {}}, at=MORNING) is None and weather.judge(None, at=MORNING) is None)

# ---- 2. the walking limit --------------------------------------------------------------------------------------
wet, fine = weather.judge(RAIN, at=MORNING), weather.judge(DRY, at=MORNING)
check("rain likely lowers a 300 m limit to 225 m and a 600 m limit to 450 m", (weather.lowered(300, wet), weather.lowered(600, wet)) == (225, 450))
check("no limit stays no limit", weather.lowered(None, wet) is None)
check("fine weather and no verdict change no limit", (weather.lowered(300, fine), weather.lowered(300, None)) == (300, 300))

# ---- 3. the route ----------------------------------------------------------------------------------------------
ON_MAP = osm.load()["places"]
PLACES = [("o1", "see", "node/597685675"), ("o2", "shop", "node/11034183301"), ("o3", "eat", "node/4360904389")]
OPTIONS = [{"id": oid, "category": cat, "name": ON_MAP[ref]["name"], "summary": {"en": "", "ko": ""}, "facts": [],
            "place": {k: ON_MAP[ref][k] for k in ("lat", "lon", "osm_id", "access")}} for oid, cat, ref in PLACES]
PROFILE = {"walk": "long", "stairs": "ok", "rest": "often", "wish": None, "language": "en"}
ORDER = ["o2", "o1", "o3"]
plain, _ = osm.build_model(PROFILE, OPTIONS, ORDER, ORDER, None, None)
longest = max(leg["distance_m"] for leg in plain["legs"])
LIMIT = longest + 10                                    # a learned limit just above the longest walk: today every walk fits
BASE, _ = osm.build_model(PROFILE, OPTIONS, ORDER, ORDER, None, LIMIT)
LOW = weather.lowered(LIMIT, wet)
check("the drill's route: every walk fits the usual limit, the longest is over the lowered one",
      all(leg["fits_profile"] for leg in BASE["legs"]) and LOW < longest <= LIMIT, (longest, LIMIT, LOW))


def route(verdict, at=MORNING):
    return weather._apply(copy.deepcopy(BASE), verdict, PROFILE, LIMIT, at)


def same_route(a, b):
    return all(a[k] == b[k] for k in ("stops", "legs", "hazards", "benches", "review"))


m = route(fine)
check("fine weather: stops, walks, warnings and benches are untouched", same_route(m, BASE))
check("fine weather: the route note says one sentence about it, with 'no warning found' and the source",
      m["weather"]["note"]["en"] == "No warning found in today's forecast. Source: Open-Meteo, read at 09:00."
      and note.route_note(m)["en"].split("\n")[1] == m["weather"]["note"]["en"]
      and note.route_note(m)["ko"].split("\n")[1] == m["weather"]["note"]["ko"], m["weather"]["note"])
check("without weather the route note is the one of today", "Open-Meteo" not in note.route_note(BASE)["en"]
      and [line for line in note.route_note(m)["en"].split("\n") if "Open-Meteo" not in line] == note.route_note(BASE)["en"].split("\n"))

for name, verdict, at in (("rain likely", wet, MORNING), ("very hot", weather.judge(HOT, at="2026-08-01T09:00"), "2026-08-01T09:00")):
    m = route(verdict, at)
    over = [leg["id"] for leg in BASE["legs"] if LOW < leg["distance_m"] <= LIMIT]
    added = [h for h in m["hazards"] if h.get("cause") == "weather"]
    check("%s: the walks between the lowered and the usual limit no longer fit, the others are untouched" % name,
          m["weather"]["flagged_legs"] == over and [leg["id"] for leg in m["legs"] if not leg["fits_profile"]] == over
          and [leg for leg in m["legs"] if leg["id"] not in over] == [leg for leg in BASE["legs"] if leg["id"] not in over], m["weather"])
    check("%s: each flagged walk has a warning with the numbers and the forecast as its source" % name,
          [h["leg_id"] for h in added] == over and all(
              h["kind"] == "long_walk" and h["source"] == verdict["source_url"] and str(LOW) in h["detail"]["en"]
              and str(LIMIT) in h["detail"]["en"] and h["detail"]["ko"] for h in added)
          and m["hazards"][:len(BASE["hazards"])] == BASE["hazards"], added)
    check("%s: the route note names the danger and both limits" % name,
          verdict["dangers"][0]["text"]["en"] in m["weather"]["note"]["en"] and "%d m" % LOW in m["weather"]["note"]["en"]
          and (m["weather"]["usual_walk_limit_m"], m["weather"]["walk_limit_m"]) == (LIMIT, LOW)
          and added[0]["detail"]["en"] in note.route_note(m)["en"], m["weather"]["note"])
    under_cover = weather.covered_benches()
    ok = True
    for leg in m["legs"]:
        near = [b["id"] for b in osm.rest_spots(leg["line"])]
        mine = [b for b in m["benches"] if b["leg_id"] == leg["id"]]
        if any(b in under_cover for b in near):
            ok = ok and mine[0].get("covered") is True
        else:
            ok = ok and [{k: b[k] for k in b if k != "id"} for b in mine] == [
                {k: b[k] for k in b if k != "id"} for b in BASE["benches"] if b["leg_id"] == leg["id"]]
    check("%s: a bench the map marks as indoors or under cover is listed first where there is one; "
          "other walks keep their benches" % name, ok and [b["id"] for b in m["benches"]] == ["b%d" % (i + 1) for i in range(len(m["benches"]))])
check("the map extract marks benches as indoors (two in Shibuya Hikarie)", len(weather.covered_benches()) >= 1, weather.covered_benches())
m = weather._apply(copy.deepcopy(plain), wet, PROFILE, None, MORNING)
check("with no walking limit nothing is flagged and the note says so",
      same_route({**m, "benches": plain["benches"]}, plain) and "You set no walking limit" in m["weather"]["note"]["en"], m["weather"]["note"])

m = route(weather.judge(DRY, at=DAY + "T17:10"), DAY + "T17:10")
dark = [h for h in m["hazards"] if h["kind"] == "darkness"]
check("after sunset every walk is flagged as dark, with the sunset time and its source; nothing else changes",
      [h["leg_id"] for h in dark] == [leg["id"] for leg in BASE["legs"]] and all("16:31" in h["detail"]["en"] and h["source"] == DRY["source_url"] for h in dark)
      and m["legs"] == BASE["legs"] and m["benches"] == BASE["benches"], dark)
start = DAY + "T16:28"                                    # three minutes of light left: 150 m at the slow pace
m = route(weather.judge(DRY, at=start), start)
walked, expected = 0, []
for leg in BASE["legs"]:
    walked += leg["distance_m"]
    if walked / weather.PACE_M_PER_MIN > 3:
        expected.append(leg["id"])
check("before sunset only the walks that would end after it are flagged", m["weather"]["dark_legs"] == expected and expected, m["weather"]["dark_legs"])
check("in the morning no walk is flagged as dark", route(fine)["weather"]["dark_legs"] == [])

# ---- 4. the source does not answer -----------------------------------------------------------------------------
ROWS = []


def log(state, agent, tool, decision, rule="", detail=""):
    row = {"agent": agent, "tool": tool, "decision": decision, "rule": rule, "detail": detail}
    ROWS.append(row)
    return row


AREA = {"name": osm.AREA["name"], "bbox": osm.AREA["bbox"], "supported": True}
state = {"area": AREA}
got = weather.ensure(state, "router", log)
check("offline with nothing saved: no verdict, and state says unknown (weather and dangers are None)",
      got is None and state["weather"] is None and state["dangers"] is None, state)
check("one audit row says the source was not available, and why",
      [(r["tool"], r["rule"]) for r in ROWS] == [("weather_today", "weather_not_available")] and "reason=offline" in ROWS[0]["detail"], ROWS)
m = copy.deepcopy(BASE)
check("then the limit is today's and the route is exactly today's route",
      weather.limit(state, 300, log) == 300 and weather.apply(state, m, PROFILE, LIMIT, log) == BASE and weather.facts(state) == {}, m.get("weather"))
check("asking again in the same turn writes no second row", [r["tool"] for r in ROWS].count("weather_today") == 1, ROWS)
step = progress.steps([{"t": "12:00:00", **ROWS[0]}])[0]
check("the page's step for it", step["label"]["en"] == "Weather not available: the route is built without it" and step["status"] == "done", step)

ROWS.clear()
os.environ["GILMATE_WEATHER"] = "off"
state = {"area": AREA}
check("switched off: the same, with that reason", weather.ensure(state, "router", log) is None and "reason=switched_off" in ROWS[0]["detail"], ROWS)
os.environ.pop("GILMATE_WEATHER")
ROWS.clear()
state = {"picks": ORDER}
m = copy.deepcopy(BASE)
check("a session without an area has no place to read the weather for: nothing asked, nothing logged, nothing changed",
      weather.ensure(state, "router", log) is None and weather.apply(state, m, PROFILE, LIMIT, log) == BASE and not ROWS and state == {"picks": ORDER}, (state, ROWS))


def save_for_now(saved, name="forecast"):
    """Puts a forecast where fetch() looks for the answer of this hour, dated today at the place."""
    lat, lon = (round(x, 3) for x in weather._centre({"area": AREA}))
    today = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 32400))
    text = json.dumps(saved).replace(saved["forecast"]["hourly"]["time"][0][:10], today)
    os.makedirs(os.environ["GILMATE_WEATHER_CACHE"], exist_ok=True)
    path = os.path.join(os.environ["GILMATE_WEATHER_CACHE"], "%s_%s_%s_%s.json" % (name, lat, lon, time.strftime("%Y-%m-%dT%H", time.gmtime())))
    open(path, "w", encoding="utf-8").write(text)
    return path


ROWS.clear()
saved_path = save_for_now({"forecast": {"hourly": {"time": [DAY + "T00:00"]}}})
state = {"area": AREA}
check("an answer with no usable hour: no verdict, one row with that reason",
      weather.ensure(state, "router", log) is None and len(ROWS) == 1 and "reason=no_usable_hours" in ROWS[0]["detail"], ROWS)

ROWS.clear()
ALL_DAY = changed(RAIN, precipitation_probability=85, precipitation=2.0)       # raining whatever hour the drill runs at
save_for_now(ALL_DAY)
state = {"area": AREA}
got = weather.ensure(state, "router", log)
check("a forecast saved this hour is used: state gets weather and the list dangers",
      got is not None and state["weather"]["rain"] == "likely" and ("rain", "watch") in kinds(state["weather"])
      and state["dangers"] == state["weather"]["dangers"], state.get("weather") and kinds(state["weather"]))
check("its audit rows: the forecast read, the air quality not available",
      [r["rule"] for r in ROWS if r["tool"] == "weather_today"] == ["weather", "air_quality_not_available"] and "rain=likely" in ROWS[0]["detail"]
      and "from=saved" in ROWS[0]["detail"] and all(r["decision"] == "allowed" for r in ROWS), ROWS)
check("the limit is lowered and the router's facts carry the verdict",
      weather.limit(state, 300, log) == 225 and weather.facts(state)["weather"]["rain"] == "likely"
      and weather.facts(state)["weather"]["dangers"][0]["kind"] in weather.WORST_FIRST, weather.facts(state))
m = weather.apply(state, copy.deepcopy(BASE), PROFILE, LIMIT, log)
check("and the drafted route carries the effects", m["weather"]["shorter_walks"] and m["weather"]["flagged_legs"], m.get("weather"))
check("the steps for the page", [s["label"]["en"] for s in progress.steps([{"t": "12:00:00", **r} for r in ROWS if r["tool"] == "weather_today"])]
      == ["Today's weather read from Open-Meteo", "Air quality not available: left out"])

# ---- 5. the climb on each walk ---------------------------------------------------------------------------------
# tests/fixtures/elevation_heights.json: what Open-Meteo's elevation endpoint answered on 2026-11-21 for the points
# along the drill's two walks (Loft to the Hachiko statue, the statue to Uobei).
os.environ["GILMATE_ELEVATION_CACHE"] = os.path.join(REPO, "tests", "fixtures", "elevation_heights.json")
m = copy.deepcopy(BASE)
check("the climb is switched off by default: a route gets no climb even when the heights are saved",
      weather.apply({"area": AREA, "weather_checked_at": time.time()}, m, dict(PROFILE, stairs="avoid"), LIMIT, log) == BASE
      and not any("climb_m" in leg for leg in m["legs"]), m["legs"][0].keys())
os.environ["GILMATE_ELEVATION_CACHE"] = os.path.join(TMP, "heights.json")
ROWS.clear()
m = copy.deepcopy(BASE)
check("no heights saved and offline: the climb is unknown, the route untouched, one row says so",
      climb.of_line(BASE["legs"][0]["line"]) == (None, "offline") and climb.apply({"area": AREA}, m, PROFILE, log) == BASE
      and [(r["tool"], r["rule"]) for r in ROWS] == [("climb", "elevation_not_available")] and "reason=offline" in ROWS[0]["detail"], ROWS)
os.environ["GILMATE_ELEVATION_CACHE"] = os.path.join(REPO, "tests", "fixtures", "elevation_heights.json")
ROWS.clear()
m = climb.apply({"area": AREA}, copy.deepcopy(BASE), PROFILE, log)
check("with heights every walk says its metres up and down, with the source",
      [(leg["climb_m"], leg["descent_m"], leg["climb_source"]) for leg in m["legs"]] == [(9, 14, climb.SOURCE), (11, 9, climb.SOURCE)],
      [(leg.get("climb_m"), leg.get("descent_m")) for leg in m["legs"]])
check("stairs 'ok': 9 m and 11 m up are not steep, nothing is flagged",
      m["hazards"] == BASE["hazards"] and [leg["fits_profile"] for leg in m["legs"]] == [leg["fits_profile"] for leg in BASE["legs"]]
      and ROWS[-1]["rule"] == "elevation" and "walks=2; known=2; steep=0" in ROWS[-1]["detail"] and "from=saved" in ROWS[-1]["detail"], ROWS)
m = climb.apply({"area": AREA}, copy.deepcopy(BASE), dict(PROFILE, stairs="few"), log)
check("stairs 'few': steep starts at 12 m, nothing is flagged", m["hazards"] == BASE["hazards"])
m = climb.apply({"area": AREA}, copy.deepcopy(BASE), dict(PROFILE, stairs="avoid"), log)
steep = [h for h in m["hazards"] if h["kind"] == "climb"]
check("stairs 'avoid': from 8 m up a walk is steep, gets a warning with its source and no longer fits",
      [h["leg_id"] for h in steep] == [leg["id"] for leg in m["legs"]] and all(h["source"] == climb.SOURCE and h["cause"] == "elevation" for h in steep)
      and steep[0]["detail"]["en"] == "This walk climbs about 9 m (ground heights from Open-Meteo on a 90 m grid)." and steep[0]["detail"]["ko"]
      and not any(leg["fits_profile"] for leg in m["legs"]) and steep[1]["detail"]["en"] in note.route_note(m)["en"], steep)
m = copy.deepcopy(BASE)
check("a session without an area is left alone", climb.apply({"picks": ORDER}, m, dict(PROFILE, stairs="avoid"), log) == BASE)
check("the steps for the page say where the heights are from",
      [s["label"]["en"] for s in progress.steps([{"t": "12:00:00", **r} for r in ROWS[:2]])]
      == ["Climb of each walk read from Open-Meteo's ground heights"] * 2, ROWS[:2])
os.environ["GILMATE_ELEVATION_CACHE"] = os.path.join(TMP, "heights.json")

# ---- 6. the tools (need the ADK) -------------------------------------------------------------------------------
try:
    from gilmate import guards, security, tools, weather_tool  # noqa: F401
except ImportError:
    tools = None
    print("note  not checked here: weather_today, propose_route and the policy row (need the ADK)")
if tools:
    check("weather_today is in the policy table: one call per turn",
          guards.check_policy("weather_today", {}, 0, {}) is None
          and guards.check_policy("weather_today", {}, 1, {}) == "weather_today.max_calls:1")

    def session(area):
        s = {"profile": dict(PROFILE, walk="medium"), "options": OPTIONS, "picks": ORDER, "rounds": 0}
        if area:
            s["area"] = AREA
        return s

    def draft_of(s):
        tools.propose_route(ORDER, "{}", types.SimpleNamespace(state=s, agent_name="router"))
        return {k: s["draft"][k] for k in ("stops", "legs", "hazards", "benches")}

    for path in os.listdir(os.environ["GILMATE_WEATHER_CACHE"]):
        os.remove(os.path.join(os.environ["GILMATE_WEATHER_CACHE"], path))
    without, failing = session(False), session(True)
    today = draft_of(without)
    check("propose_route with the fetch failing drafts exactly today's route, and one audit row says why",
          draft_of(failing) == today and "weather" not in failing["draft"]
          and [r["rule"] for r in failing["audit"] if r["tool"] == "weather_today"] == ["weather_not_available"], failing.get("audit"))
    context = types.SimpleNamespace(state=failing, agent_name="router")
    check("weather_today then tells the router to plan as usual", weather_tool.weather_today(context)["status"] == "unavailable")
    check("walking_route gives the usual limit", tools.walking_route("o2", "o1", context)["her_limit_m"] == 600)

    save_for_now(ALL_DAY)
    raining = session(True)
    context = types.SimpleNamespace(state=raining, agent_name="router")
    told = weather_tool.weather_today(context)
    check("with rain likely weather_today returns the verdict, not the hours", told["status"] == "ok" and told["rain"] == "likely" and "hours" not in told, told)
    got = tools.walking_route("o2", "o1", context)
    check("walking_route gives the lowered limit and the weather facts", got["her_limit_m"] == 450 and got["weather"]["shorter_walks"] is True, got)
    tools.propose_route(ORDER, "{}", context)
    check("the draft carries the weather; stops and walk distances are the map's as before",
          raining["draft"]["weather"]["walk_limit_m"] == 450 and raining["draft"]["stops"] == today["stops"]
          and [leg["distance_m"] for leg in raining["draft"]["legs"]] == [leg["distance_m"] for leg in today["legs"]]
          and raining["rule_failures"] == [], raining["draft"].get("weather"))
    seen = tools.read_draft(context)
    check("the critic reads the verdict and the lowered limit with the draft", seen["her_limit_m"] == 450 and seen["weather"]["rain"] == "likely", seen)
    tools.submit_review("approve", [], context)
    check("the published route note says the weather sentence", raining["draft"]["weather"]["note"]["en"] in raining["route_note"]["en"], raining["route_note"]["en"])
    check("the weather was read once in the turn",
          [r["rule"] for r in raining["audit"] if r["tool"] == "weather_today"] == ["weather", "air_quality_not_available"], raining["audit"])

print("drill_weather: %s" % ("FAILED %d check(s)" % len(FAILED) if FAILED else "all checks passed"))
sys.exit(1 if FAILED else 0)
