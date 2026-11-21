"""Write the four development samples the page loads with ?dev=1 to ?dev=4.

Free: no network, no key, no model. Run from the repo folder: python3 frontend/dev/make_samples.py

The names, texts, facts, quotes and audit rows are invented and say so ("Sample ...").
The geometry is not: stop coordinates, lines, distances, steps and benches come from the map
tools in gilmate/osm.py, for map places that are not named here, so that the sample route lies
on the streets the map draws and the hazard sentences have the wording the backend really writes.
The samples are for layout work only and are shown on the page as "Development sample".

Each sample has nine places to choose from (CONTRACT.md section 7.2): its six options and three more map places.
Their pictures are drawings this script writes into dev/photos/, labelled "Sample drawing, not a photo" and credited
to this script. Three places have no picture, one has no description, one has a rating with its sample source.
Sample 2 also has a drawing for the landing card (area.photo). No sample has street photos.

Each sample also carries a "user:memory" (CONTRACT.md section 6.1). It is not typed in here: the functions
in gilmate/memory.py write it from the sample's answers, picks and taps, at fixed times, so the page is shown
the shapes and the sentences the backend really writes. "_today" is the day the sample pretends it is; the page
uses it, in the samples only, to decide whether a limit that is still being learned counts today.
  ?dev=1  answers, picks and a kept walking limit that changed two walks of the route
  ?dev=2  answers, picks and a limit learned today from one tap (still learning, in use today);
          here "evidence" and "effect" are {en, ko} pairs, in the other samples they are plain English strings
  ?dev=3  answers, picks and a limit from one tap on an earlier day (still learning, not in use today)
  ?dev=4  an empty memory, so the five questions are asked
"""
import copy
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from gilmate import memory, osm  # noqa: E402  (pure Python, reads data/shibuya_osm.json)

NOTE = ("Development sample for layout work, written by frontend/dev/make_samples.py. Names, texts, facts, "
        "quotes, ratings and audit rows are invented, and the pictures are drawings, not photos. Coordinates, lines, distances, steps and benches come from the "
        "map tools for places not named here. The memory is written by gilmate/memory.py from the sample's "
        "answers, picks and taps. Loaded only with ?dev=1 to ?dev=4.")
TODAY = "2026-11-21"


def option(number, category, name, osm_id, access, facts):
    place = osm.load()["places"][osm_id]
    return {"id": f"o{number}", "category": category, "name": name,
            "summary": {"en": f"Sample text: this stands in for what the guide would say about {name.lower()}.",
                        "ko": f"샘플 문장: 가이드가 이곳({name})에 대해 들려줄 이야기 자리입니다."},
            "facts": [{"label": label, "value": value, "source_url": f"https://example.org/sample-{number}",
                       "quote": f"Sample quote: {quote}"} for label, value, quote in facts],
            "place": {"lat": place["lat"], "lon": place["lon"], "osm_id": osm_id, "access": access}}


def build(profile, options, picks, straight=(), learned_limit_m=None):
    """The model the backend would build. Pairs in `straight` are treated as having no mapped path."""
    real = osm.walking_route

    def route(from_id, to_id, stairs="ok"):
        found = real(from_id, to_id, stairs)
        if (from_id, to_id) not in straight:
            return found
        a, b = found["line"][0], found["line"][-1]
        return {"status": "ok", "kind": "straight_line", "from": from_id, "to": to_id,
                "distance_m": round(osm._dist((a[1], a[0]), (b[1], b[0]))), "line": [a, b],
                "stairs": "unknown", "steps": [], "stairs_avoided": False}

    osm.walking_route = route
    try:
        model, problems = osm.build_model(profile, options, picks, picks, None, learned_limit_m)
    finally:
        osm.walking_route = real
    assert model and not problems, problems
    return model


def at(stamp):
    return time.strptime(stamp, "%Y-%m-%d %H:%M")


def remember(profile, options, picks, model, answered, picked, taps=()):
    """The session state after she answered, picked and tapped: only gilmate/memory.py writes the memory in it."""
    state = {"profile": dict(profile), "options": options, "picks": picks, "spatial_model": model}
    memory.profile(state, at(answered))
    memory.remember_picks(state, at(picked))
    for stamp, leg_id, verdict in taps:
        result = memory.record_feedback(state, leg_id, verdict, at(stamp))
        assert result["status"] == "recorded", result
    return state


def in_two_languages(mem):
    """The same memory with "evidence" and "effect" as {en, ko}. The Korean sentences are this sample's own."""
    asked = {"walk": "얼마나 걸을 수 있는지", "stairs": "계단에 대해", "rest": "얼마나 자주 쉬는지", "food": "무엇을 드시고 싶은지"}
    places = {"see": "볼 곳", "shop": "쇼핑할 곳", "eat": "먹을 곳"}
    for fact in mem["facts"]:
        key, value = fact["key"], fact["value"]
        if key in asked:
            evidence = f'샘플 문장: {asked[key]} 여쭤봤을 때 "{value}"(이)라고 답하셨습니다.'
            effect = "샘플 문장: 이 답변에 맞춰 경로와 장소를 고릅니다."
        elif key == "wish":
            evidence, effect = "샘플 문장: 이 바람은 직접 쓰셨습니다.", "샘플 문장: 가이드가 제안할 장소를 고를 때 읽습니다."
        elif key in places:
            evidence, effect = f"샘플 문장: {places[key]} 두 곳 중에서 이곳을 고르셨습니다.", "샘플 문장: 경로에 들어 있는 곳입니다."
        else:
            evidence = "샘플 문장: 걸은 뒤에 ‘너무 멀어요’라고 하셨습니다."
            effect = f"샘플 문장: 오늘은 {value} m보다 긴 구간을 표시합니다. ‘너무 멀어요’를 한 번 더 누르시면 계속 기억합니다."
        fact["evidence"] = {"en": fact["evidence"], "ko": evidence}
        fact["effect"] = {"en": fact["effect"], "ko": effect}
    return mem


def hide_ids(run):
    """An invented name must not be tied to a real place id."""
    names = {}
    for o in run["options"]:
        names[o["place"]["osm_id"]] = f"sample/{o['id']}"
        o["place"]["osm_id"] = names[o["place"]["osm_id"]]
    for h in run["spatial_model"]["hazards"]:
        ref = str(h.get("source", "")).removeprefix("osm:")
        if ref in names:
            h["source"] = "osm:" + names[ref]
    return run


# ---- the places to choose from (CONTRACT.md section 7.2) ----------------------------------------------
# The sample's options become its candidates, with three more places, so that the map has nine marks.
# Their pictures are drawings this script writes into dev/photos/: grey shapes with the words
# "Sample drawing, not a photo". They stand in for photos in layout work and are credited as what they are.
EXTRA = [("eat", "Sample noodle bar", "node/2268223524", "unknown"),
         ("shop", "Sample record shop", "node/8828812383", "yes"),
         ("eat", "Sample grill", "node/13754044527", "unknown")]
KINDS = {"see": [{"en": "Viewing deck", "ko": "전망대"}, {"en": "Statue", "ko": "동상"}],
         "shop": [{"en": "Shopping centre", "ko": "쇼핑센터"}, {"en": "Souvenir shop", "ko": "기념품 가게"}, {"en": "Record shop", "ko": "음반 가게"}],
         "eat": [{"en": "Sushi restaurant", "ko": "초밥집"}, {"en": "Ramen shop", "ko": "라멘집"}, {"en": "Noodle bar", "ko": "국숫집"}, {"en": "Grill", "ko": "구이집"}]}
PHOTO_COUNTS = [3, 1, 0, 2, 1, 0, 2, 1, 0]      # the third, sixth and ninth place have no picture: "No photo found"
SHADES = ["#c9cfd4", "#d8d2c6", "#bcc6cf", "#cfd6cc", "#d6cdd2", "#c4ccd6"]


def drawing(number):
    """One drawn stand-in: a street, two blocks and its label. Returns the path the page loads it from."""
    folder = os.path.join(HERE, "photos")
    os.makedirs(folder, exist_ok=True)
    shade = SHADES[number % len(SHADES)]
    lean = 40 + (number * 37) % 120
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400" width="640" height="400">
<rect width="640" height="400" fill="{shade}"/>
<path d="M0 400 L{180 + lean} 150 L{300 + lean} 150 L640 400 Z" fill="#eef0f1"/>
<rect x="{40 + lean // 3}" y="70" width="150" height="190" fill="#9aa3ab"/>
<rect x="{430 - lean // 4}" y="40" width="170" height="230" fill="#aeb6bd"/>
<text x="320" y="340" text-anchor="middle" font-family="system-ui, sans-serif" font-size="26" fill="#1d2125">Sample drawing {number}, not a photo</text>
</svg>
"""
    with open(os.path.join(folder, f"sample-{number}.svg"), "w", encoding="utf-8") as out:
        out.write(svg)
    return f"dev/photos/sample-{number}.svg"


def sample_photo(number):
    path = drawing(number)
    return {"url": path, "thumb_url": path, "width": 640, "height": 400, "credit": "Drawn by frontend/dev/make_samples.py",
            "licence": "sample drawing, not a photo", "source_url": "frontend/dev/make_samples.py", "taken_at": None}


def candidates_for(options):
    """The options in the shape of section 7.2, and three more places from the map."""
    places = osm.load()["places"]
    found = [dict(option) for option in options]
    for index, (category, name, osm_id, access) in enumerate(EXTRA):
        number = len(options) + index + 1
        place = places[osm_id]
        found.append({"id": f"o{number}", "category": category, "name": name,
                      "summary": {"en": f"Sample text: this stands in for what the guide would say about {name.lower()}.",
                                  "ko": f"샘플 문장: 가이드가 이곳({name})에 대해 들려줄 이야기 자리입니다."},
                      "facts": [], "place": {"lat": place["lat"], "lon": place["lon"], "osm_id": f"sample/o{number}", "access": access}})
    seen = {"see": 0, "shop": 0, "eat": 0}
    drawn = 0
    out = []
    for index, option in enumerate(found):
        kinds = KINDS[option["category"]]
        kind = kinds[seen[option["category"]] % len(kinds)]
        seen[option["category"]] += 1
        summary = option.get("summary") or {}
        photos = []
        for _ in range(PHOTO_COUNTS[index % len(PHOTO_COUNTS)]):
            drawn += 1
            photos.append(sample_photo(drawn))
        out.append({"id": option["id"], "category": option["category"], "name": option["name"], "kind": kind,
                    "description": summary if summary.get("en") or summary.get("ko") else None,
                    "description_source": {"url": f"https://example.org/sample-{index + 1}", "quote": "Sample quote."} if summary.get("en") else None,
                    "rating": {"value": "4.5 of 5", "source_url": "https://example.org/sample-rating", "quote": "Sample quote: rated 4.5 of 5 by visitors."} if index == 4 else None,
                    "facts": option["facts"], "place": dict(option["place"]), "photos": photos})
    return out


def write(name, run, area_photo=False):
    path = os.path.join(HERE, name)
    run = hide_ids(run)
    candidates = candidates_for(run.pop("options"))
    area = {"name": "Shibuya, Tokyo", "bbox": run["spatial_model"]["area"]["bbox"], "supported": True}
    if area_photo:
        area["photo"] = sample_photo(99)
    photos = sum(len(place["photos"]) for place in candidates)
    run = {**{key: run[key] for key in ("_note", "_today", "recorded_at", "profile")}, "area": area, "candidates": candidates,
           "street_photos": [], "counts": {"places_on_map": len(osm.load()["places"]), "places_shown": len(candidates), "photos_found": photos, "street_photos": 0},
           **{key: value for key, value in run.items() if key not in ("_note", "_today", "recorded_at", "profile")}}
    with open(path, "w", encoding="utf-8") as out:
        json.dump(run, out, ensure_ascii=False, indent=1)
        out.write("\n")
    model = run["spatial_model"]
    print(name, [(leg["kind"], leg["distance_m"], leg["stairs"], leg["fits_profile"]) for leg in model["legs"]],
          len(model["hazards"]), "hazards,", len(model["benches"]), "benches;",
          [(f["key"], f["value"], f["status"], f["changed_legs"]) for f in run[memory.KEY]["facts"] if f["group"] == "day"],
          len(run[memory.KEY]["facts"]), "facts")


# ---- sample 1: a careful traveller; one leg routed, one leg with no mapped path, review partly unverified ----
profile = {"walk": "short", "stairs": "avoid", "rest": "often", "food": "sushi", "wish": None, "language": "ko"}
options = [
    option(1, "see", "Sample viewing deck", "node/10289966935", "yes",
           [("Price", "1,000 yen", "tickets are 1,000 yen for adults."), ("Hours", "10:00 to 22:00", "open from 10:00 to 22:00.")]),
    option(2, "see", "Sample crossing", "node/597685675", "limited", [("Price", "Free", "free to visit at any time.")]),
    option(3, "shop", "Sample rooftop mall", "node/1377643958", "unknown", [("Hours", "11:00 to 21:00", "shops open 11:00 to 21:00.")]),
    option(4, "shop", "Sample souvenir store", "node/861115501", "no", []),
    option(5, "eat", "Sample sushi counter", "node/7975620864", "yes", [("Lunch set", "2,000 yen", "lunch sets from 2,000 yen.")]),
    option(6, "eat", "Sample ramen shop", "node/1558819039", "unknown", [("Bowl", "900 yen", "a bowl costs 900 yen.")]),
]
picks = ["o1", "o5", "o3"]
straight = {("node/7975620864", "node/1377643958")}
# The day before she walked this route and said "too far" twice, so the limit is kept. Today's route is built with it.
state = remember(profile, options, picks, build(profile, options, picks, straight), "2026-11-20 10:02", "2026-11-20 10:08",
                 [("2026-11-20 10:41", "s1>s2", "too_far"), ("2026-11-20 11:15", "s2>s3", "too_far")])
memory.remember_picks(state, at("2026-11-21 09:37"))
model = build(profile, options, picks, straight, memory.learned_limit(state, TODAY))
state["spatial_model"] = model
memory.note_route(state, model, TODAY)
model["review"] = {"status": "partly_unverified", "rounds": 2,
                   "removed": [{"what": "Sample claim about a lift at the mall", "why": "not confirmed within two rounds"}]}
model["generated_at"] = "2026-11-21T09:39:00"
sample_1 = {"profile": profile, "options": copy.deepcopy(options), "picks": picks}
write("shape-sample.json", {
    "_note": NOTE, "_today": TODAY, "recorded_at": "2026-11-21T09:40:00", "profile": profile, "options": options, "picks": picks,
    "spatial_model": model, memory.KEY: state[memory.KEY],
    "audit": [
        {"t": "09:36:02", "agent": "scout", "tool": "search_options", "decision": "allowed", "rule": "", "detail": "Sample row: see: 5 results"},
        {"t": "09:36:09", "agent": "scout", "tool": "search_options", "decision": "withheld", "rule": "injection_pattern", "detail": "Sample row: one result held back, https://example.org/bad"},
        {"t": "09:36:40", "agent": "scout", "tool": "save_options", "decision": "blocked", "rule": "quote_not_found", "detail": "Sample row: an option whose quote is not in its source"},
        {"t": "09:37:05", "agent": "traveller", "tool": "record_picks", "decision": "allowed", "rule": "human_decision", "detail": "o1,o5,o3"},
        {"t": "09:37:40", "agent": "router", "tool": "propose_route", "decision": "blocked", "rule": "stop_not_in_picks", "detail": "Sample row: a stop that she did not pick"},
        {"t": "09:38:20", "agent": "critic", "tool": "submit_review", "decision": "blocked", "rule": "sent_back_to_router", "detail": "Sample row: round 1"},
        {"t": "09:39:00", "agent": "critic", "tool": "submit_review", "decision": "allowed", "rule": "published:partly_unverified", "detail": "round 2"},
    ],
})

# ---- sample 2: stairs on the way, a walk that is too long, every place with a different access, review verified ----
profile = {"walk": "short", "stairs": "ok", "rest": "sometimes", "food": "ramen", "wish": "a quiet place", "language": "ko"}
options = [
    option(1, "see", "Sample museum", "node/4579436893", "limited", [("Price", "Free", "entry is free.")]),
    option(2, "see", "Sample statue", "node/597685675", "yes", [("Price", "Free", "free to visit at any time.")]),
    option(3, "shop", "Sample bookshop with a very long name that has to wrap on a small screen", "node/2356791180", "no",
           [("Hours", "10:00 to 20:00", "open 10:00 to 20:00.")]),
    option(4, "shop", "Sample souvenir store", "node/861115501", "unknown", []),
    option(5, "eat", "Sample ramen shop", "node/1558819041", "yes", [("Bowl", "900 yen", "a bowl costs 900 yen.")]),
    option(6, "eat", "Sample sushi counter", "node/1558819039", "unknown", [("Lunch set", "2,000 yen", "lunch sets from 2,000 yen.")]),
]
options[4]["summary"] = {"en": "", "ko": ""}      # the backend can save an empty text; the page must say "unknown"
picks = ["o1", "o3", "o5"]
model = build(profile, options, picks)
model["review"] = {"status": "verified", "rounds": 1, "removed": []}
model["generated_at"] = "2026-11-21T10:12:00"
# One "too far" today, after the route was made: a limit that is still being learned, and no route built with it yet.
state = remember(profile, options, picks, model, "2026-11-21 10:05", "2026-11-21 10:11",
                 [("2026-11-21 10:26", "s2>s3", "fine"), ("2026-11-21 10:48", "s1>s2", "too_far")])
audit = [
    {"t": "10:10:31", "agent": "scout", "tool": "search_options", "decision": "allowed", "rule": "", "detail": "Sample row: eat: 5 results"},
    {"t": "10:11:15", "agent": "traveller", "tool": "record_picks", "decision": "allowed", "rule": "human_decision", "detail": "o1,o3,o5"},
    {"t": "10:12:00", "agent": "critic", "tool": "submit_review", "decision": "allowed", "rule": "published:verified", "detail": "round 1"},
]
sample_2 = {"_note": NOTE, "_today": TODAY, "recorded_at": "2026-11-21T10:13:00", "profile": profile,
            "options": copy.deepcopy(options), "picks": picks, "spatial_model": copy.deepcopy(model), "audit": audit}
write("shape-sample-2.json", area_photo=True, run={
    "_note": NOTE, "_today": TODAY, "recorded_at": "2026-11-21T10:13:00", "profile": profile, "options": options, "picks": picks,
    "spatial_model": model, memory.KEY: in_two_languages(state[memory.KEY]),
    "audit": audit + [
        {"t": "10:26:10", "agent": "traveller", "tool": "record_feedback", "decision": "allowed", "rule": "human_decision", "detail": "s2>s3 fine"},
        {"t": "10:48:30", "agent": "traveller", "tool": "record_feedback", "decision": "allowed", "rule": "human_decision", "detail": "s1>s2 too_far, limit 336 m candidate"},
    ],
})

# ---- sample 3: other answers, typed words in the wish, and a limit from one tap two days ago: not in use today ----
profile = {"walk": "medium", "stairs": "few", "rest": "rarely", "food": "surprise",
           "wish": 'How far can you walk at a time? "ten minutes, then I want to sit" | a quiet place with a view',
           "language": "ko"}
options, picks = copy.deepcopy(sample_1["options"]), sample_1["picks"]
model = build(profile, options, picks, straight)
state = remember(profile, options, picks, model, "2026-11-19 13:20", "2026-11-19 13:27",
                 [("2026-11-19 14:02", "s2>s3", "too_far")])
memory.remember_picks(state, at("2026-11-21 11:02"))
assert memory.learned_limit(state, TODAY) is None
memory.note_route(state, model, TODAY)
model["review"] = {"status": "verified", "rounds": 1, "removed": []}
model["generated_at"] = "2026-11-21T11:04:00"
write("shape-sample-3.json", {
    "_note": NOTE, "_today": TODAY, "recorded_at": "2026-11-21T11:05:00", "profile": profile, "options": options, "picks": picks,
    "spatial_model": model, memory.KEY: state[memory.KEY],
    "audit": [
        {"t": "11:02:10", "agent": "traveller", "tool": "record_picks", "decision": "allowed", "rule": "human_decision", "detail": "o1,o5,o3"},
        {"t": "11:04:00", "agent": "critic", "tool": "submit_review", "decision": "allowed", "rule": "published:verified", "detail": "round 1"},
    ],
})

# ---- sample 4: the run of sample 2 for a traveller Gilmate knows nothing about yet ----
write("shape-sample-4.json", {**copy.deepcopy(sample_2), memory.KEY: {"facts": [], "feedback": []}})
