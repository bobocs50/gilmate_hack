"""What Gilmate remembers about one traveller between sessions (CONTRACT.md section 6). Pure Python: no ADK.

Everything lives in one per-user key, "user:memory". ADK keeps keys that start with "user:" per user instead of
per session. Only the functions in this file write it, and only from her own answers, picks and taps: never from
web text or model text. A tap reaches record_feedback as a leg id and one of two verdicts, both checked here;
the distance and the place name are read from the route that Python built.
"""
import copy
import time

from . import osm

KEY = "user:memory"                # { facts: [...], feedback: [...] }, shapes in CONTRACT.md 6.1
ANSWERS = ("walk", "stairs", "rest", "wish")    # her answers in the session's "profile"; a food answer is no longer kept
LIMIT = "walk_limit_m"             # the fact key of the walking limit learned from "too far" taps
VERDICTS = ("fine", "too_far")
MARGIN_M = 10                      # "just below": a walk she called too far sets the limit this far under it
FEEDBACK_KEPT = 50                 # only the newest taps are kept

FOOD_SEARCH = {"sushi": "sushi omakase", "ramen": "ramen"}      # what her food answer puts into the web search
FOOD_SEARCH_OTHERWISE = "Japanese food"
ASKED_ABOUT = {"walk": ("how far you like to walk", "걷는 거리"), "stairs": ("stairs", "계단"),
               "rest": ("how often you like to rest", "쉬는 횟수"), "food": ("what you like to eat", "음식")}
ANSWER_KO = {"short": "짧게", "medium": "보통", "long": "문제없음", "avoid": "피하고 싶음", "few": "조금은 괜찮음",
             "ok": "문제없음", "often": "자주", "sometimes": "가끔", "rarely": "거의 필요 없음",
             "sushi": "초밥", "ramen": "라멘", "surprise": "아무거나"}
PICKED_KO = {"see": "볼 곳", "shop": "쇼핑할 곳", "eat": "먹을 곳"}


def _both(en, ko):
    """Every text in memory exists in English and Korean, built here from fixed sentences, never by the model."""
    return {"en": en, "ko": ko}


def read(state):
    """A copy of her memory, always with both lists."""
    stored = state.get(KEY)
    stored = stored if isinstance(stored, dict) else {}
    return {"facts": [copy.deepcopy(f) for f in stored.get("facts") or [] if isinstance(f, dict)],
            "feedback": [copy.deepcopy(r) for r in stored.get("feedback") or [] if isinstance(r, dict)]}


def _fact(mem, key):
    return next((f for f in mem["facts"] if f.get("key") == key), None)


def _put(mem, now, key, value, group, source, evidence, effect, status="kept", changed_legs=()):
    """One fact per key: a new one gets the next free id, a changed one keeps its id and its place."""
    old = _fact(mem, key)
    numbers = [int(f["id"][1:]) for f in mem["facts"] if str(f.get("id", ""))[1:].isdigit()]
    fact = {"id": old["id"] if old else "f%d" % (max(numbers, default=0) + 1), "key": key, "value": value,
            "group": group, "source": source, "evidence": evidence, "at": time.strftime("%H:%M", now),
            "effect": effect, "status": status, "changed_legs": list(changed_legs)}
    if old:
        mem["facts"][mem["facts"].index(old)] = fact
    else:
        mem["facts"].append(fact)
    return fact


def _answer_texts(key, value):
    """Where an answer came from and what it changes, in the words of what the code does with it. Both {en, ko}."""
    if key == "wish":
        if not value:
            return (_both("You left the wish empty.", "바라는 점은 비워 두셨습니다."),
                    _both("Nothing changes.", "달라지는 것은 없습니다."))
        return (_both("You wrote this wish yourself.", "이 바람은 직접 적어 주셨습니다."),
                _both("The guide reads it when it chooses the places to offer.",
                      "안내자가 추천할 장소를 고를 때 이 내용을 읽습니다."))
    evidence = _both('You answered "%s" when asked about %s.' % (value, ASKED_ABOUT[key][0]),
                     '%s 질문에 이렇게 답하셨습니다: "%s".' % (ASKED_ABOUT[key][1], ANSWER_KO.get(value, value)))
    if key == "walk":
        limit = osm.walk_limit({"walk": value})
        if limit is None:
            return evidence, _both(
                "No walk is flagged as too long, unless a lower limit learned from your taps applies.",
                "너무 길다고 표시되는 구간은 없습니다. 다만 누르신 평가로 배운 기준이 있으면 그 기준이 적용됩니다.")
        return evidence, _both(
            "Walks longer than %d m are flagged, unless a lower limit learned from your taps applies." % limit,
            "%dm보다 긴 구간은 표시됩니다. 다만 누르신 평가로 배운 더 낮은 기준이 있으면 그 기준이 적용됩니다." % limit)
    if key == "stairs":
        return evidence, {
            "avoid": _both("Routes look for a way without mapped stairs first; a walk with stairs is flagged.",
                           "먼저 지도에 계단이 없는 길을 찾고, 계단이 있는 구간은 표시됩니다."),
            "few": _both("Routes prefer ways with fewer mapped stairs.", "지도에 계단이 적은 길을 우선합니다."),
        }.get(value, _both("Stairs are not avoided.", "계단을 피하지 않습니다."))
    if key == "rest":
        shown = osm.benches_shown({"rest": value})
        return evidence, _both("Up to %d benches from the map are shown for each walk." % shown,
                               "구간마다 지도에 있는 벤치를 최대 %d개까지 보여 드립니다." % shown)
    words = FOOD_SEARCH.get(value, FOOD_SEARCH_OTHERWISE)
    return evidence, _both("Places to eat are searched as: %s." % words, "식당은 다음 검색어로 찾습니다: %s." % words)


def profile(state, now=None):
    """Her answers for this session, kept as facts. A session without answers gets the remembered ones."""
    answers = state.get("profile")
    mem = read(state)
    if not answers:
        return {f["key"]: f["value"] for f in mem["facts"] if f.get("group") == "answers" and f.get("key") in ANSWERS}
    changed = False
    for key in ANSWERS:
        old = _fact(mem, key)
        if key in answers and (old is None or old.get("value") != answers[key]):
            _put(mem, now or time.localtime(), key, answers[key], "answers", "answer", *_answer_texts(key, answers[key]))
            changed = True
    if changed:
        state[KEY] = mem
    return answers


def remember_picks(state, now=None):
    """Her picks become facts, and picks she no longer has are dropped. Names are the map's names.

    The first pick of a category has the category as its key ("see"); a further one of the same category is
    numbered ("see2", "see3"), so every pick has its own fact.
    """
    mem = read(state)
    now = now or time.localtime()
    by_id = {o["id"]: o for o in list(state.get("candidates") or []) + list(state.get("options") or [])}
    on_map = {c["id"] for c in state.get("candidates") or []}
    used, count = set(), {}
    for pick in state.get("picks", []):
        place = by_id.get(pick)
        if not place:
            continue
        category = place["category"]
        count[category] = count.get(category, 0) + 1
        key = category if count[category] == 1 else "%s%d" % (category, count[category])
        used.add(key)
        if pick in on_map:
            evidence = _both("You said Yes to this place on the map.", "지도에서 이 장소에 '예'라고 하셨습니다.")
        else:
            evidence = _both("You picked this from the two places to %s." % category,
                             "%s 두 곳 중에서 직접 고르셨습니다." % PICKED_KO.get(category, "장소"))
        _put(mem, now, key, place["name"], "picks", "pick", evidence,
             _both("It is a stop on your route.", "경로에 들르는 곳입니다."))
    mem["facts"] = [f for f in mem["facts"] if f.get("group") != "picks" or f.get("key") in used]
    state[KEY] = mem


def learned_limit(state, today=None):
    """Her learned walking limit in metres, or None. A kept one always counts; a candidate only on its day."""
    mem = read(state)
    fact = _fact(mem, LIMIT)
    value = fact.get("value") if fact else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    if fact.get("status") == "kept":
        return value
    days = [str(r.get("at", ""))[:10] for r in mem["feedback"] if r.get("verdict") == "too_far"]
    return value if days and days[-1] == (today or time.strftime("%Y-%m-%d")) else None


def record_feedback(state, leg_id, verdict, now=None):
    """Store one tap about one walk of the published route. Returns {status, fact|null}. A refused tap changes nothing."""
    if not isinstance(verdict, str) or verdict not in VERDICTS:
        return {"status": "rejected", "fact": None, "reason": 'verdict must be "fine" or "too_far"'}
    model = state.get("spatial_model") or {}
    leg = next((leg for leg in model.get("legs", []) if leg["id"] == leg_id), None)
    if leg is None:
        return {"status": "rejected", "fact": None, "reason": "leg_id must be the id of a walk in the current route"}
    now = now or time.localtime()
    mem = read(state)
    mem["feedback"] = (mem["feedback"] + [{"leg_id": leg["id"], "distance_m": leg["distance_m"], "verdict": verdict,
                                           "at": time.strftime("%Y-%m-%dT%H:%M:%S", now)}])[-FEEDBACK_KEPT:]
    fact = None
    if verdict == "too_far":
        below = max(0, leg["distance_m"] - MARGIN_M)
        old = _fact(mem, LIMIT)
        if old is None:          # the first "too far": a candidate, used for the rest of the day
            status, value, evidence, legs = "candidate", below, None, ()
        elif isinstance(old.get("value"), (int, float)) and old["value"] <= below:
            status, value, evidence, legs = "kept", old["value"], old["evidence"], old.get("changed_legs", ())
        else:
            status, value, evidence, legs = "kept", below, None, ()
        if evidence is None:
            start = next((s["name"] for s in model.get("stops", []) if s["id"] == leg["from"]), None)
            evidence = _both(
                "You said: too far, after the %d m walk%s." % (leg["distance_m"], " from %s" % start if start else ""),
                "%s%dm 구간을 걸은 뒤 '너무 멀다'고 하셨습니다." % ("%s에서 출발한 " % start if start else "", leg["distance_m"]))
        if status == "kept":
            effect = _both("Walks longer than %d m are flagged." % value, "%dm보다 긴 구간은 표시됩니다." % value)
        else:
            effect = _both(
                'Walks longer than %d m are flagged for the rest of that day. A second "too far" keeps it.' % value,
                "그날 남은 시간 동안 %dm보다 긴 구간은 표시됩니다. '너무 멀다'를 한 번 더 누르시면 계속 유지됩니다." % value)
        walk = _fact(mem, "walk")
        asked = osm.walk_limit({"walk": walk["value"]}) if walk else None
        if asked is not None and asked < value:      # the lower limit applies, and that is her answer's
            effect = _both(effect["en"] + " Your answer about walking sets a lower limit, %d m, and that one applies." % asked,
                           effect["ko"] + " 걷는 거리 답변에 따른 기준 %dm가 더 낮아서 그 기준이 적용됩니다." % asked)
        fact = copy.deepcopy(_put(mem, now, LIMIT, value, "day", "feedback", evidence, effect, status, legs))
    state[KEY] = mem
    return {"status": "recorded", "fact": fact}


def note_route(state, model, today=None):
    """After a route is published: which of its walks the learned limit judged differently than her answer would."""
    answers = profile(state)
    mem = read(state)
    fact = _fact(mem, LIMIT)
    if fact is None:
        return
    limit = learned_limit(state, today)
    changed = osm.legs_changed_by_limit(model, answers, limit) if limit is not None else []
    if fact.get("changed_legs") != changed:
        fact["changed_legs"] = changed
        state[KEY] = mem


def forget_fact(state, fact_id):
    """Delete one fact she no longer wants kept. Returns {status}: "forgotten" or "not_found"."""
    mem = read(state)
    fact = next((f for f in mem["facts"] if f.get("id") == fact_id), None)
    if fact is None:
        return {"status": "not_found"}
    mem["facts"].remove(fact)
    if fact["key"] == LIMIT:     # the taps it was learned from go with it
        mem["feedback"] = [r for r in mem["feedback"] if r.get("verdict") != "too_far"]
    state[KEY] = mem
    answers = state.get("profile")
    if fact.get("group") == "answers" and answers and fact["key"] in answers:
        # otherwise the next tool call would learn the answer again from this session
        state["profile"] = {k: v for k, v in answers.items() if k != fact["key"]}
    return {"status": "forgotten"}
