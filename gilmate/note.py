"""The route written out in plain sentences, in English and Korean, assembled only from the spatial model.

No model writes here and nothing is computed: every name, distance and warning is read from the model
(CONTRACT.md section 1), every other word is a fixed sentence below. So the note leaves out what a model
wrote (a walk's advice in `note`, a stop's `background`, the critic's open points in `review.removed`) and
gives no total and no count. What the model does not say is written as unknown, never as safe.
Plain Python: no ADK, no network.

    route_note(spatial_model) -> {"en": str, "ko": str}     # one sentence per line
    lines(spatial_model)      -> [ {"about": stop id | leg id | "route" | "review", "en": str, "ko": str} ]
"""

T = {
    "order": ("Your route, in this order: {names}.", "경로는 이 순서입니다: {names}."),
    "no_stops": ("This route has no stops.", "이 경로에는 들를 곳이 없습니다."),
    "access_yes": ("{name}: the map lists wheelchair access at the entrance.",
                   "{name}: 지도에 입구가 휠체어로 들어갈 수 있다고 표시되어 있습니다."),
    "access_limited": ("{name}: the map lists only limited wheelchair access at the entrance.",
                       "{name}: 지도에 입구가 휠체어로는 일부만 들어갈 수 있다고 표시되어 있습니다."),
    "access_no": ("{name}: the map lists no wheelchair access at the entrance.",
                  "{name}: 지도에 입구가 휠체어로 들어갈 수 없다고 표시되어 있습니다."),
    "access_unknown": ("The map has no accessibility information for the entrance of {name}.",
                       "{name} 입구의 접근성 정보가 지도에 없습니다."),
    "walk": ("{a} to {b}: {m} m on foot{stairs}.", "{a}에서 {b}까지: 걸어서 {m}m{stairs}."),
    "walk_no_distance": ("{a} to {b}: the distance is unknown{stairs}.", "{a}에서 {b}까지: 거리는 알 수 없습니다{stairs}."),
    "stairs_none_mapped": (", no stairs mapped", ", 지도에 표시된 계단은 없습니다"),
    "stairs_some": (", with stairs", ", 계단이 있습니다"),
    "stairs_unknown": (", stairs unknown", ", 계단 여부는 알 수 없습니다"),
    "stairs_below": ("", ""),       # the stairs warnings follow as their own sentences
    "not_routed": ("{a} to {b}: not routed, the map has no path between them.",
                   "{a}에서 {b}까지: 지도에 길이 없어 경로를 찾지 못했습니다."),
    "straight": ("The straight-line distance is {m} m and stairs are unknown.",
                 "직선 거리는 {m}m이고 계단 여부는 알 수 없습니다."),
    "straight_no_distance": ("The distance and the stairs are unknown.", "거리와 계단 여부는 알 수 없습니다."),
    "benches": ("Benches mapped near this walk, off the path by: {list}.",
                "이 길 가까이 지도에 표시된 벤치가 있습니다. 길에서 떨어진 거리: {list}."),
    "benches_straight": ("Benches mapped near the two places, away by: {list}.",
                         "두 장소 가까이 지도에 표시된 벤치가 있습니다. 떨어진 거리: {list}."),
    "benches_no_distance": ("A bench is mapped near this walk.", "이 길 가까이 지도에 표시된 벤치가 있습니다."),
    "no_bench": ("No bench is mapped near this walk.", "이 길 가까이에는 지도에 표시된 벤치가 없습니다."),
    "warning_steps": ("There are stairs on this walk.", "이 길에 계단이 있습니다."),
    "warning_long_walk": ("This walk is longer than the limit set for you.", "이 구간은 정해 둔 기준보다 깁니다."),
    "warning_other": ("A warning is recorded here without details.", "이곳에 자세한 내용 없이 경고가 기록되어 있습니다."),
    "verified": ("The checker confirmed this route.", "검토자가 이 경로를 확인했습니다."),
    "partly_unverified": ("The checker did not confirm every point of this route.",
                          "검토자가 이 경로의 모든 내용을 확인하지는 못했습니다."),
    "not_reviewed": ("This route has not been checked.", "이 경로는 아직 검토되지 않았습니다."),
}
UNIT = {"en": " m", "ko": "m"}


def _both(key, **kw):
    """One fixed sentence in both languages. A slot given as {en, ko} is filled per language."""
    en, ko = T[key]
    pick = lambda lang: {k: v[lang] if isinstance(v, dict) else v for k, v in kw.items()}  # noqa: E731
    return {"en": en.format(**pick("en")), "ko": ko.format(**pick("ko"))}


def _metres(value):
    """A distance as the model holds it, or None when it holds no usable number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return int(value) if float(value).is_integer() else value


def _detail(hazard):
    """A warning's own sentence as Python wrote it into the model, or a fixed one for its kind."""
    d = hazard.get("detail")
    if isinstance(d, dict) and d.get("en"):
        return {"en": str(d["en"]), "ko": str(d.get("ko") or d["en"])}
    return _both({"steps": "warning_steps", "long_walk": "warning_long_walk"}.get(hazard.get("kind"), "warning_other"))


def _name(stop):
    return str(stop.get("name") or stop.get("id") or "?")


def _leg_lines(leg, a, b, hazards, benches):
    out, said = [], set()

    def add(text):
        if text["en"] not in said:          # two warnings with the very same words are said once
            said.add(text["en"])
            out.append({"about": leg.get("id"), **text})

    mine = [h for h in hazards if h.get("leg_id") == leg.get("id")]
    steps = [h for h in mine if h.get("kind") == "steps"]
    m = _metres(leg.get("distance_m"))
    routed = leg.get("kind") == "routed"
    if routed:
        if steps:
            stairs = "stairs_below"
        else:
            stairs = {"none_mapped": "stairs_none_mapped", "some": "stairs_some"}.get(leg.get("stairs"), "stairs_unknown")
        add(_both("walk" if m is not None else "walk_no_distance", a=a, b=b, m=m, stairs=_both(stairs)))
    else:
        # anything that is not a routed walk is a leg with no mapped path: its distance is a straight line
        add(_both("not_routed", a=a, b=b))
        add(_both("straight", m=m) if m is not None else _both("straight_no_distance"))
    for h in mine:
        if not routed and h.get("kind") == "unknown_access":
            continue                        # that warning says "no mapped path" again
        add(_detail(h))
    near = [x for x in benches if x.get("leg_id") == leg.get("id")]
    if near:
        off = [_metres(x.get("off_route_m")) for x in near]
        if None in off:
            add(_both("benches_no_distance"))
        else:
            add(_both("benches" if routed else "benches_straight",
                      list={lang: ", ".join("%s%s" % (n, UNIT[lang]) for n in sorted(off)) for lang in UNIT}))
    else:
        add(_both("no_bench"))
    return out


def lines(spatial_model):
    """The note as a list of sentences, each with the stop or walk it is about."""
    model = spatial_model if isinstance(spatial_model, dict) else {}
    stops = sorted((s for s in model.get("stops") or [] if isinstance(s, dict)), key=lambda s: s.get("order") or 0)
    legs = [leg for leg in model.get("legs") or [] if isinstance(leg, dict)]
    hazards = [h for h in model.get("hazards") or [] if isinstance(h, dict)]
    benches = [b for b in model.get("benches") or [] if isinstance(b, dict)]
    by_id = {s.get("id"): s for s in stops}
    out = []
    if stops:
        out.append({"about": "route", **_both("order", names=", ".join(_name(s) for s in stops))})
    else:
        out.append({"about": "route", **_both("no_stops")})
    said = (model.get("weather") or {}).get("note") if isinstance(model.get("weather"), dict) else None
    if isinstance(said, dict) and said.get("en"):        # one line about today's weather, as gilmate/weather.py wrote it
        out.append({"about": "weather", "en": str(said["en"]), "ko": str(said.get("ko") or said["en"])})

    done_legs, done_hazards = set(), set()

    def walk(leg):
        done_legs.add(id(leg))
        done_hazards.update(id(h) for h in hazards if h.get("leg_id") == leg.get("id"))
        a, b = by_id.get(leg.get("from")), by_id.get(leg.get("to"))
        return _leg_lines(leg, _name(a) if a else str(leg.get("from") or "?"),
                          _name(b) if b else str(leg.get("to") or "?"), hazards, benches)

    for s in stops:
        at_stop = [h for h in hazards if h.get("stop_id") == s.get("id") and not h.get("leg_id")]
        done_hazards.update(id(h) for h in at_stop)
        said_unknown = False
        for h in at_stop:
            said_unknown = said_unknown or h.get("kind") == "unknown_access"
            out.append({"about": s.get("id"), **_detail(h)})
        access = s.get("access") if s.get("access") in ("yes", "limited", "no") else "unknown"
        if not (access == "unknown" and said_unknown):
            out.append({"about": s.get("id"), **_both("access_" + access, name=_name(s))})
        for leg in legs:
            if leg.get("from") == s.get("id") and id(leg) not in done_legs:
                out += walk(leg)
    for leg in legs:                         # a walk that starts at no known stop is still said
        if id(leg) not in done_legs:
            out += walk(leg)
    for h in hazards:                        # and so is a warning tied to nothing
        if id(h) not in done_hazards:
            out.append({"about": h.get("leg_id") or h.get("stop_id") or "route", **_detail(h)})

    review = model.get("review") if isinstance(model.get("review"), dict) else {}
    status = review.get("status") if review.get("status") in ("verified", "partly_unverified") else "not_reviewed"
    out.append({"about": "review", **_both(status)})
    return out


def route_note(spatial_model):
    """The route in sentences, one per line: {"en": ..., "ko": ...}."""
    rows = lines(spatial_model)
    return {lang: "\n".join(r[lang] for r in rows) for lang in ("en", "ko")}
