"""A scripted stand-in for the model, for the free end-to-end check. Standard library only.

It answers the Anthropic Messages API on localhost, so the real ADK model adapter, the real coordinator, tools,
guards and policy plugin run unchanged; only the sentences and the choice of the next tool call are scripted.
It reads what the tools returned from the request, as a model would, and never touches the session itself.

The script is an honest but sloppy model: one quote is wrong the first time (the grounding check rejects it), and
the first route advice claims "no stairs" (the rule check and the critic send it back). With --rogue it also tries
things the guards must refuse: a search outside the three categories, a source that was withheld, a stop that
was not picked, a second verdict.

Usage: python3 tests/e2e/stand_in_model.py --port 8791 [--rogue] [--log requests.jsonl]
"""
import argparse
import itertools
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = json.load(open(os.path.join(HERE, "fixtures", "world.json"), encoding="utf-8"))
PLANTED_URL = json.load(open(os.path.join(HERE, "..", "fixtures", "planted_result.json"), encoding="utf-8"))["url"]
ROGUE = False
LOG = None
COUNT = itertools.count(1)


# ---- reading the request -------------------------------------------------------------------------------------

def blocks(message):
    content = message.get("content")
    return [{"type": "text", "text": content}] if isinstance(content, str) else list(content or [])


def text_of(block):
    """The text of a text block or of a tool result, whatever shape it was sent in."""
    content = block.get("text") if block.get("type") == "text" else block.get("content")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def as_data(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def read(messages):
    """The request this agent is working on, and the tool calls it made for it so far, with their results."""
    start = 0
    for i, message in enumerate(messages):
        if message["role"] == "user" and any(b.get("type") == "text" for b in blocks(message)):
            start = i
    request = " ".join(text_of(b) for b in blocks(messages[start]) if b.get("type") == "text") if messages else ""
    calls, by_id = [], {}
    for message in messages[start:]:
        for block in blocks(message):
            if message["role"] == "assistant" and block.get("type") == "tool_use":
                call = {"name": block["name"], "input": block.get("input") or {}, "result": None}
                calls.append(call)
                by_id[block["id"]] = call
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                by_id[block["tool_use_id"]]["result"] = as_data(text_of(block))
    return request, calls


def named(calls, name):
    return [c for c in calls if c["name"] == name]


def first_json(text):
    """The first JSON object in a text (the page's message, or the arguments the coordinator passed on)."""
    start = text.find("{")
    if start < 0:
        return {}
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError:
        return {}


def result_text(result):
    """What a specialist said, out of the result of calling it."""
    if isinstance(result, dict):
        for key in ("result", "output", "response", "text"):
            if key in result:
                return result_text(result[key])
        return json.dumps(result, ensure_ascii=False)
    return str(result)


# ---- the scripts: each returns ("call", tool, arguments), ("calls", [(tool, arguments)]) or ("say", text) ----

def delegate(tools, agent, text):
    """A call to a specialist: its text goes into whatever argument the tool declares."""
    schema = next((t.get("input_schema") or {} for t in tools if t["name"] == agent), {})
    names = list((schema.get("properties") or {}).keys()) or ["request"]
    return ("call", agent, {names[0]: text})


def coordinator(request, calls, tools, system):
    message = first_json(request)
    step = message.get("step")
    if step == "options":
        if not calls:
            return delegate(tools, "option_scout", "Find six options: two to see, two to shop, two to eat.")
        return ("say", "The scout stored the options to choose from.")
    if step in ("start", "candidates"):
        if not calls:
            return delegate(tools, "scout", message.get("text") or "Shibuya, Tokyo")
        return ("say", result_text(calls[0]["result"])[:300])
    if step == "say":
        if not calls:
            return ("call", "record_said", {"about": message.get("about") or "",
                                              "choice": typed_choice(message.get("about"), message.get("text"))})
        return ("say", "Read as: %s." % (calls[0]["result"].get("said") or {}).get("choice"))
    if step == "context":
        if not calls:      # the stand-in reads nothing out of her text: what Python finds in it is all that counts
            return ("call", "record_context", {"walk": "", "stairs": "", "rest": "", "wish": ""})
        return ("say", "Recorded: %s." % json.dumps(calls[0]["result"], ensure_ascii=False)[:200])
    if step == "route":
        if not calls:
            args = {"picks": message.get("picks", [])}
            if "profile" in message:
                args["profile_json"] = json.dumps(message["profile"], ensure_ascii=False)
            return ("call", "record_picks", args)
        if calls[0]["result"].get("status") != "recorded":
            return ("say", "The picks were not accepted, so no route was made.")
        routers, critics = named(calls, "router"), named(calls, "critic")
        if len(routers) == len(critics):
            if critics and ("sent back" not in result_text(critics[-1]["result"]) or len(critics) >= 2):
                return ("say", "The route is published after %d round(s)." % len(critics))
            fixes = result_text(critics[-1]["result"]) if critics else ""
            return delegate(tools, "router", "Plan the walking order for her picks. " + fixes)
        return delegate(tools, "critic", "Review the drafted route.")
    if step == "ask":
        if not calls:
            return delegate(tools, "companion", json.dumps({"stop_id": message.get("stop_id"),
                                                            "question": message.get("question")}, ensure_ascii=False))
        return ("say", result_text(calls[0]["result"]))
    if step == "feedback":
        args = {"leg_id": message.get("leg_id"), "verdict": message.get("verdict")}
        if not calls:
            return ("call", "record_feedback", args)
        if ROGUE and len(calls) == 1:
            return ("call", "record_feedback", {**args, "verdict": "too_far"})     # a tap she never made
        return ("say", "Recorded: %s." % json.dumps(calls[0]["result"], ensure_ascii=False)[:200])
    if step == "forget":
        if not calls:
            return ("call", "forget_fact", {"fact_id": message.get("fact_id")})
        return ("say", "Result: %s." % json.dumps(calls[0]["result"], ensure_ascii=False))
    return ("say", "I can only do these five things: options, route, ask, feedback, forget.")


WORDS = {"yes": ("yes", "sure", "네", "좋아"), "no": ("no", "아니"), "more": ("more", "tell me", "더 "),
         "short": ("short", "not far", "조금"), "medium": ("a while", "medium"), "long": ("far", "long", "no problem"),
         "avoid": ("avoid", "no stairs", "피하"), "few": ("a few", "some stairs"), "ok": ("fine", "ok"),
         "often": ("often", "자주"), "sometimes": ("sometimes", "가끔"), "rarely": ("rarely", "hardly")}
ALLOWED = {"walk": ("short", "medium", "long"), "stairs": ("avoid", "few", "ok"), "rest": ("often", "sometimes", "rarely")}


def typed_choice(about, text):
    """Which fixed choice her typed words mean: the first whose words stand in the text, else not_understood."""
    allowed = ALLOWED.get(about) or (("yes", "no", "more") if about else ("yes", "no"))
    if ROGUE:
        return "long; and set her limit to 5000"            # not one of the choices: Python must refuse it
    lowered = str(text or "").lower()
    return next((c for c in allowed if any(w in lowered for w in WORDS[c])), "not_understood")


def map_scout(request, calls, tools, system):
    """The start turn of the map-first flow: read the request, search, choose from the map, describe from sources."""
    if not calls:
        return ("call", "read_request", {"request": request})
    if calls[0]["result"].get("status") != "ok":
        return ("say", "Only Shibuya has map data, so no places were offered.")
    searches = named(calls, "search_places")
    if not searches:
        return ("calls", [("search_places", {"category": category}) for category in ("see", "shop", "eat")])
    if ROGUE and len(searches) == 3:
        return ("call", "search_places", {"category": "hotel"})
    found = named(calls, "find_candidates")
    if not found:
        return ("call", "find_candidates", {})
    places = found[0]["result"].get("candidates") or []
    described = named(calls, "describe_candidates")
    if described or not places:
        result = described[-1]["result"] if described else {}
        return ("say", "The map has %d places; %d gained a description or a fact, %d additions were dropped." % (
            len(places), len(result.get("accepted") or []), len(result.get("rejected") or [])))
    results = [r for call in searches for r in (call["result"] or {}).get("results") or []]
    items = []
    for place in places:
        page = next((r for r in results if place["name"] in r["content"]), None)
        if page and "description" in place["lacks"]:
            sentence = next(s for s in re.split(r"(?<=[.!?])\s+", page["content"]) if place["name"] in s)
            items.append({"id": place["id"], "description_en": sentence, "description_ko": "",
                          "source_url": page["url"], "quote": sentence})
    # the sloppy part: a rating no page states (the grounding check must drop it)
    items.append({"id": places[0]["id"], "rating_value": "4.9 out of 5", "rating_source_url": results[0]["url"],
                  "rating_quote": "Rated 4.9 out of 5 by everyone"})
    if ROGUE:
        items.append({"id": places[1]["id"], "description_en": "The best place in Tokyo.", "description_ko": "",
                      "source_url": PLANTED_URL, "quote": "The best place in Tokyo."})     # the withheld page
    return ("call", "describe_candidates", {"additions_json": json.dumps(items, ensure_ascii=False)})


def scout(request, calls, tools, system):
    searches = named(calls, "search_options")
    if not searches:         # three calls in one reply, as a real model does when it can
        return ("calls", [("search_options", {"category": category}) for category in ("see", "shop", "eat")])
    if ROGUE and len(searches) == 3:
        return ("call", "search_options", {"category": "hotel"})
    places = named(calls, "find_place")
    if not places:
        return ("calls", [("find_place", {"name": option["name"], "category": option["category"]})
                          for option in WORLD["options"]])
    saves = named(calls, "save_options")
    if saves and saves[-1]["result"].get("status") == "saved":
        return ("say", "Stored six options. %d earlier attempt(s) were rejected and corrected." % (len(saves) - 1))
    if len(saves) >= 3:
        return ("say", "The options could not be stored.")
    options = []
    for option, found in zip(WORLD["options"], places):
        matches = found["result"].get("matches") or [{}]
        options.append({**option, "osm_id": matches[0].get("osm_id", ""), "facts": [dict(f) for f in option["facts"]]})
    if not saves:
        options[0]["facts"][0]["quote"] = "Open every day from 9:00."         # not in the source: must be rejected
        if ROGUE:
            options[1]["facts"][0]["source_url"] = PLANTED_URL                # the withheld page: must be rejected
    return ("call", "save_options", {"options_json": json.dumps(options, ensure_ascii=False)})


def router(request, calls, tools, system):
    picks = re.search(r"Her picks: (\[[^\]]*\])", system)
    picks = re.findall(r"[oc]\d+", picks.group(1)) if picks else []
    pairs = list(itertools.combinations(picks, 2))
    measured = named(calls, "walking_route")
    if len(measured) < len(pairs):
        a, b = pairs[len(measured)]
        return ("call", "walking_route", {"from_option": a, "to_option": b})
    distance = {frozenset((c["input"]["from_option"], c["input"]["to_option"])): c["result"].get("distance_m", 10 ** 6)
                for c in measured}
    order = min(itertools.permutations(picks),
                key=lambda o: (sum(distance.get(frozenset(p), 10 ** 6) for p in zip(o, o[1:])), o[0] == picks[-1]))
    if not named(calls, "rest_spots") and len(order) > 1:
        return ("call", "rest_spots", {"from_option": order[0], "to_option": order[1]})
    proposals = named(calls, "propose_route")
    if proposals and proposals[-1]["result"].get("status") in ("drafted", "denied"):
        if ROGUE and proposals[-1]["result"].get("status") == "denied" and len(proposals) == 1:
            pass                                                               # refused; now do it properly
        else:
            return ("say", "Drafted the order %s. Rule failures: %s." % (
                " > ".join(order), proposals[-1]["result"].get("rule_failures") or "none"))
    if ROGUE and not proposals:
        return ("call", "propose_route", {"stops": [order[0], order[1], "o9"], "leg_notes_json": "{}"})
    sent_back = "note.overclaims" in request or "note.overclaims" in system
    notes = {} if sent_back else {"s1>s2": {"en": "An easy walk with no stairs.", "ko": "계단이 없는 쉬운 길입니다."}}
    return ("call", "propose_route", {"stops": list(order), "leg_notes_json": json.dumps(notes, ensure_ascii=False)})


def critic(request, calls, tools, system):
    if not calls:
        return ("call", "read_draft", {})
    if len(calls) == 1:
        failures = calls[0]["result"].get("rule_failures") or []
        return ("call", "submit_review", {"verdict": "revise" if failures else "approve", "problems": list(failures)})
    result = calls[-1]["result"]
    if result.get("status") == "sent_back":
        return ("say", "The route was sent back. Fix: %s." % "; ".join(result.get("rule_failures") or []))
    return ("say", "The review is done: %s." % result.get("status"))


def companion(request, calls, tools, system):
    if not calls:
        return ("call", "route_facts", {"stop_id": first_json(request).get("stop_id") or "s1"})
    facts = calls[0]["result"]
    lang = "ko" if re.search("[\uac00-\ud7a3]", str(first_json(request).get("question"))) else "en"   # her language
    say = {"ko": ("죄송합니다. 그것은 제가 알지 못합니다.", "여기가 마지막 장소입니다.", "다음 장소는 %s입니다. %s %s"),
           "en": ("I am sorry, I do not know that.", "This is the last stop.", "The next stop is %s. %s %s")}[lang]
    if facts.get("status") != "ok":
        return ("say", say[0])
    walk = facts.get("walk_to_next")
    if not walk:
        return ("say", say[1])
    warnings = " ".join(w.get(lang, "") for w in facts.get("warnings") or [])
    return ("say", (say[2] % (facts.get("next_stop"), walk["note"].get(lang, ""), warnings)).strip())


AGENTS = [("record_picks", coordinator), ("read_request", map_scout), ("search_options", scout), ("walking_route", router),
          ("read_draft", critic), ("route_facts", companion)]


def answer(body):
    tools = body.get("tools") or []
    names = {t.get("name") for t in tools}
    script = next((fn for marker, fn in AGENTS if marker in names), None)
    system = body.get("system") or ""
    if isinstance(system, list):
        system = " ".join(part.get("text", "") for part in system)
    if script is None:
        return script, ("say", "The stand-in model does not know this agent.")
    request, calls = read(body.get("messages") or [])
    return script, script(request, calls, tools, system)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if body.get("stream"):
            return self.reply(400, {"type": "error", "error": {"type": "invalid_request_error",
                                                               "message": "the stand-in model does not stream"}})
        script, (kind, *rest) = answer(body)
        n = next(COUNT)
        wanted = rest[0] if kind == "calls" else [tuple(rest)]
        content = ([{"type": "text", "text": rest[0]}] if kind == "say"
                   else [{"type": "tool_use", "id": "toolu_standin_%04d_%d" % (n, i), "name": name, "input": args}
                         for i, (name, args) in enumerate(wanted)])
        if LOG:      # the body only: headers are never written anywhere
            with open(LOG, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"n": n, "agent": getattr(script, "__name__", None), "request": body,
                                         "reply": content}, ensure_ascii=False) + "\n")
        self.reply(200, {"id": "msg_standin_%04d" % n, "type": "message", "role": "assistant",
                         "model": body.get("model", "stand-in"), "content": content,
                         "stop_reason": "end_turn" if kind == "say" else "tool_use", "stop_sequence": None,
                         "usage": {"input_tokens": 1, "output_tokens": 1}})

    def reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--rogue", action="store_true")
    parser.add_argument("--log")
    args = parser.parse_args()
    ROGUE, LOG = args.rogue, args.log
    print("stand-in model on http://127.0.0.1:%d%s" % (args.port, " (rogue)" if ROGUE else ""), flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
