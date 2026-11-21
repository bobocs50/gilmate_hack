"""The progress steps the page shows while a turn runs, made from the audit rows of that turn.

    steps(rows, start=0) -> [ {id, label: {en, ko}, agent, tool, status: "done"|"blocked"|"withheld",
                               detail: {en, ko}, t} ]

One audit row (CONTRACT.md section 1: {t, agent, tool, decision, rule, detail}) gives one step, in the same
order. No row, no step: nothing is added in between, at the start or at the end, and "Done" is a step only
when a row says so. Every number in a step is a number of its row. A row that is not a row (no known
decision) gives no step.

What a step can say depends on what its row holds. A row's `rule` names what happened and its `detail` may
carry fields written as "key=value; key=value":

    rule                 fields read from detail                         step
    area_supported       area                                            Request read
    area_not_supported   area                                            Request read, no map data (blocked row)
    screened             category, passed, withheld                      Search results screened
    candidates           places_on_map, places_shown                     Places chosen from the map
    photos               places, photos, street_photos, without          Photos fetched
    grounding            kept, dropped                                   Grounding check
    done                 places, photos                                  Done
    (an allowed row with no rule, by tool)  category, name               Searched the web, Looked up on the map, ...

A row without those fields still gives its step, without the numbers. Text in a row that came from the web
or from a model is not repeated here, except a place name of at most 80 characters; a withheld search
result is shown by its site and its rule, not by its words.
Plain Python: no ADK, no network, no model.  python3 -m gilmate.progress <run.json> prints the steps of a saved run.
"""
import json
import re
import sys
from urllib.parse import urlsplit

STATUS = {"allowed": "done", "blocked": "blocked", "withheld": "withheld"}
CATEGORY = {"see": ("sights", "볼거리"), "shop": ("shops", "쇼핑"), "eat": ("places to eat", "식당")}

# What happened, by the row's rule.
BY_RULE = {
    "area_supported": ("Request read", "요청을 읽었습니다"),
    "area_not_supported": ("Request read: no map data for this area", "요청을 읽었습니다: 이 지역은 지도 자료가 없습니다"),
    "screened": ("Search results screened", "검색 결과를 걸러냈습니다"),
    "candidates": ("Places chosen from the map", "지도에서 장소를 골랐습니다"),
    "photos": ("Photos fetched", "사진을 가져왔습니다"),
    "grounding": ("Grounding check", "근거 확인"),
    "done": ("Done", "완료"),
    "published:verified": ("Route published: confirmed by the checker", "경로 공개: 검토 담당이 확인했습니다"),
    "published:partly_unverified": ("Route published: not every point confirmed", "경로 공개: 모든 내용이 확인되지는 않았습니다"),
    "sent_back_to_router": ("Draft sent back to the router", "초안을 경로 담당에게 돌려보냈습니다"),
    "weather": ("Today's weather read from Open-Meteo", "Open-Meteo에서 오늘 날씨를 읽었습니다"),
    "weather_not_available": ("Weather not available: the route is built without it", "날씨를 읽지 못했습니다: 날씨 없이 경로를 만듭니다"),
    "elevation": ("Climb of each walk read from Open-Meteo's ground heights", "Open-Meteo의 지면 높이로 구간별 오르막을 읽었습니다"),
    "elevation_not_available": ("Ground heights not available: climbs left out", "지면 높이를 읽지 못했습니다: 오르막은 빼고 진행합니다"),
    "air_quality": ("Today's air quality read from Open-Meteo", "Open-Meteo에서 오늘 공기 질을 읽었습니다"),
    "air_quality_not_available": ("Air quality not available: left out", "공기 질을 읽지 못했습니다: 빼고 진행합니다"),
}
# Her own decisions: rows with rule "human_decision".
HER_DECISION = {
    "record_picks": ("Your choices recorded", "고르신 곳을 기록했습니다"),
    "record_feedback": ("Your answer about a walk recorded", "걸은 길에 대한 답을 기록했습니다"),
    "forget_fact": ("A remembered fact deleted", "기억한 내용 하나를 지웠습니다"),
    "record_said": ("Your typed answer read", "직접 쓰신 답을 읽었습니다"),
    "record_context": ("What you wrote about yourself read", "자신에 대해 쓰신 글을 읽었습니다"),
}
HER_DECISION_OTHER = ("Your decision recorded", "결정을 기록했습니다")
# An allowed row without a rule: the call was let through. By tool.
BY_TOOL = {
    "scout": ("Scout started: finding places", "탐색 담당 시작: 장소 찾기"),
    "router": ("Router started: building the route", "경로 담당 시작: 경로 만들기"),
    "critic": ("Checker started: reviewing the route", "검토 담당 시작: 경로 검토"),
    "companion": ("Companion started: answering your question", "동행 담당 시작: 질문에 답하기"),
    "search_options": ("Searched the web", "웹을 검색했습니다"),
    "search_places": ("Searched the web", "웹을 검색했습니다"),
    "option_scout": ("Scout started: finding options", "탐색 담당 시작: 선택지 찾기"),
    "read_request": ("Request passed on", "요청을 전달했습니다"),
    "find_candidates": ("Choosing places from the map", "지도에서 장소를 고르는 중"),
    "describe_candidates": ("Descriptions and ratings handed in", "설명과 평점을 냈습니다"),
    "descriptions_checked": ("Descriptions checked against their sources", "설명을 출처와 대조했습니다"),
    "find_place": ("Looked up on the map", "지도에서 찾아봤습니다"),
    "save_options": ("Grounding check started", "근거 확인 시작"),
    "walking_route": ("Walk measured on the map", "지도에서 걷는 길을 쟀습니다"),
    "rest_spots": ("Benches looked up on the map", "지도에서 벤치를 찾아봤습니다"),
    "propose_route": ("Route drafted", "경로 초안을 만들었습니다"),
    "read_draft": ("Draft read by the checker", "검토 담당이 초안을 읽었습니다"),
    "submit_review": ("Review handed in", "검토 결과를 냈습니다"),
    "route_facts": ("Route facts read", "경로 정보를 읽었습니다"),
    "record_picks": ("Your choices passed on", "고르신 곳을 전달했습니다"),
    "record_feedback": ("Your answer about a walk passed on", "걸은 길에 대한 답을 전달했습니다"),
    "forget_fact": ("Your request to forget passed on", "잊어 달라는 요청을 전달했습니다"),
    "record_said": ("Your typed answer passed on", "직접 쓰신 답을 전달했습니다"),
    "record_context": ("What you wrote about yourself passed on", "자신에 대해 쓰신 글을 전달했습니다"),
    "weather_today": ("Router asked for today's weather", "경로 담당이 오늘 날씨를 물었습니다"),
}
OTHER_TOOL = ("Step: {tool}", "단계: {tool}")
WITHHELD = ("Search result withheld", "검색 결과 하나를 보류했습니다")
WITHHELD_RULE = {
    "injection:instruction_to_assistant": ("text that gives orders to the assistant", "도우미에게 지시하는 글"),
    "payment_or_identity_request": ("a request for money or identity numbers", "돈이나 신분 번호를 요구하는 글"),
    "malformed_result": ("not a readable result", "읽을 수 없는 결과"),
}
# A blocked row: refused by the grounding check, by the policy table, or by another rule.
REFUSED = ("Refused by the grounding check", "근거 확인에서 거부되었습니다")
REFUSED_RULE = {
    "quote_not_found": ("the quote is not in its source", "인용문이 출처에 없습니다"),
    "source_not_seen": ("its source was not among the search results", "출처가 검색 결과에 없습니다"),
    "value_not_in_quote": ("a number is not in its quote", "숫자가 인용문에 없습니다"),
    "place_not_on_map": ("the place is not on the map", "지도에 없는 장소입니다"),
    "category_mismatch": ("the map lists it as another kind of place", "지도에는 다른 종류의 장소로 되어 있습니다"),
    "no_facts": ("no fact with a source was given", "출처가 있는 사실이 없습니다"),
}
POLICY = ("Blocked by the policy table", "정책 표에 따라 막았습니다")
BLOCKED = ("Step refused", "단계가 거부되었습니다")
# Numbers a detail sentence is built from, in this order, each only when the row holds it.
COUNTS = {
    "screened": [("passed", "{n} passed", "{n}건 통과"), ("withheld", "{n} withheld", "{n}건 보류")],
    "candidates": [("places_shown", "{n} places shown", "{n}곳 표시"), ("places_on_map", "{n} places on the map", "지도에 {n}곳")],
    "photos": [("photos", "{n} photos", "사진 {n}장"), ("places", "{n} places", "장소 {n}곳"),
               ("street_photos", "{n} street photos", "거리 사진 {n}장"),
               ("without", "{n} places without a photo", "사진 없는 장소 {n}곳")],
    "grounding": [("kept", "{n} kept", "{n}건 유지"), ("dropped", "{n} dropped", "{n}건 제외")],
    "done": [("places", "{n} places", "장소 {n}곳"), ("photos", "{n} photos", "사진 {n}장")],
}
_FIELD = re.compile(r"\s*([a-z_]+)\s*=\s*(.*?)\s*\Z", re.S)
_ROUND = re.compile(r"round (\d+)\Z")


def _fields(detail):
    """The "key=value; key=value" fields of a row's detail. A detail written any other way has none."""
    out = {}
    for part in detail.split(";"):
        found = _FIELD.match(part)
        if not found:
            return {}
        out[found.group(1)] = found.group(2)
    return out


def _short(text, limit=80):
    """One line of at most `limit` characters."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _both(pair, **kw):
    return {"en": pair[0].format(**kw), "ko": pair[1].format(**kw)}


def _same(text):
    return {"en": text, "ko": text}


def _with(label, extra):
    """A label with a name or a category after it: "Searched the web: sights"."""
    return {lang: "%s: %s" % (label[lang], extra[lang]) if extra[lang] else label[lang] for lang in ("en", "ko")}


def _counts(kind, fields):
    parts = [(en.format(n=fields[key]), ko.format(n=fields[key])) for key, en, ko in COUNTS[kind]
             if fields.get(key, "").isdigit()]
    return {"en": ", ".join(p[0] for p in parts), "ko": ", ".join(p[1] for p in parts)}


def _category(fields):
    return _both(CATEGORY[fields["category"]]) if fields.get("category") in CATEGORY else _same("")


def _step(row):
    """(label, detail) for one row."""
    tool, decision, rule, detail = row["tool"], row["decision"], row["rule"], row["detail"]
    fields = _fields(detail)
    none = _same("")

    if decision == "withheld":
        host = (urlsplit(detail.split(" | ")[0].strip()).hostname or "") if detail else ""
        why = _both(WITHHELD_RULE[rule]) if rule in WITHHELD_RULE else _same(_short(rule))
        return _both(WITHHELD), {lang: ": ".join(x for x in (host, why[lang]) if x) for lang in ("en", "ko")}

    if rule in COUNTS:
        label = _both(BY_RULE[rule])
        return (_with(label, _category(fields)) if rule == "screened" else label), _counts(rule, fields)
    if rule in ("area_supported", "area_not_supported"):
        return _both(BY_RULE[rule]), _same(_short(fields.get("area", "")))
    if rule in BY_RULE:                                     # published, sent back: the critic's words are not repeated
        found = _ROUND.match(detail)
        return _both(BY_RULE[rule]), (_both(("Review round {n}", "검토 {n}회차"), n=found.group(1)) if found else none)
    if rule == "human_decision":
        return _both(HER_DECISION.get(tool, HER_DECISION_OTHER)), _same(_short(detail))

    if decision == "blocked":
        name = rule.split(":")[0]
        if name in REFUSED_RULE:
            why = _both(REFUSED_RULE[name])
            who = _short(detail)
            return _both(REFUSED), {lang: ": ".join(x for x in (who, why[lang]) if x) for lang in ("en", "ko")}
        if name.startswith(("description", "rating_", "fact_", "photo_", "name_", "place_")):
            return _both(REFUSED), _same(": ".join(x for x in (_short(detail), name.replace("_", " ")) if x))
        if name == "deny_by_default" or re.match(r"[a-z_]+\.(max_calls|args\.|[a-z_]+\Z)", rule):
            return _with(_both(POLICY), _same(_short(tool))), _same(_short(rule))
        return _with(_both(BLOCKED), _same(_short(tool))), _same(_short(rule))

    # an allowed row that names no rule: the call itself
    label = _both(BY_TOOL[tool]) if tool in BY_TOOL else _both(OTHER_TOOL, tool=_short(tool, 40))
    if tool in ("search_options", "search_places"):
        return _with(label, _category(fields)), none
    if tool == "describe_candidates" and fields.get("name"):
        return _with(_both(("Added, with its source", "출처와 함께 추가")), _same(_short(fields["name"]))), none
    if tool == "find_place":
        return _with(label, _same(_short(fields.get("name", "")))), none
    return label, none


def _row(row):
    """A row with its six keys as strings, or None when it is no audit row."""
    if not isinstance(row, dict) or row.get("decision") not in STATUS:
        return None
    return {k: "" if row.get(k) is None else str(row.get(k)) for k in ("t", "agent", "tool", "decision", "rule", "detail")}


def steps(rows, start=0):
    """The progress steps for audit rows, one per row, in their order.

    start: how many rows came before these in the session's audit list, so that a step keeps its id
    ("p" and the row's place in the whole list) when only the rows of the newest turn are passed.
    """
    out = []
    for i, raw in enumerate(rows if isinstance(rows, (list, tuple)) else []):
        row = _row(raw)
        if row is None:
            continue
        label, detail = _step(row)
        out.append({"id": "p%d" % (start + i + 1), "label": label, "agent": row["agent"], "tool": row["tool"],
                    "status": STATUS[row["decision"]], "detail": detail, "t": row["t"]})
    return out


if __name__ == "__main__":
    saved = json.load(open(sys.argv[1], encoding="utf-8"))
    json.dump(steps(saved.get("audit", [])), sys.stdout, ensure_ascii=False, indent=1)
    print()
