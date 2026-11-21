"""Guards for Gilmate: screening of search results, tool policy, grounding, audit log.

Pure standard library. No network, no model, no ADK import.
Everything here fails closed: text that looks like an instruction is withheld,
a tool that is not listed is denied, a missing access tag is "unknown".
"""

import hashlib
import json
import os
import re
import time
import unicodedata

# --------------------------------------------------------------------------
# 1. Screening search results
# --------------------------------------------------------------------------

_INJECTION_PARTS = [
    # English
    r"(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+|my\s+)?"
    r"(?:previous|prior|above|earlier|preceding|former)\s+(?:instructions?|prompts?|rules|directions|guidelines)",
    r"(?:note|message|attention|instructions?)\s+(?:to|for)\s+(?:all\s+|any\s+|the\s+)?"
    r"(?:ai|llm|language\s+model)s?(?:\s+(?:assistants?|agents?|models?|systems?))?",
    r"you\s+are\s+now\s+(?:an?\s+|the\s+|my\s+)?(?:[\w-]+\s+)?(?:assistant|ai|agent|chatbot|bot|model)\b",
    r"you\s+are\s+now\s+(?:acting|operating|in\s+[\w-]+\s+mode)",
    r"from\s+now\s+on,?\s+you\s+(?:are|will|must|should)",
    r"system\s+prompt",
    r"(?:reveal|show|print|repeat|output)\s+(?:me\s+)?(?:your|the)\s+(?:hidden\s+|secret\s+|system\s+|original\s+)?"
    r"(?:instructions|prompt)",
    r"new\s+instructions\s*:",
    # Korean
    r"(?:이전|앞|위|기존)(?:의|에\s*받은)?\s*(?:모든\s*)?(?:지시|지침|명령|프롬프트)(?:\s*사항)?(?:을|를|은|는)?\s*(?:모두\s*|전부\s*)?"
    r"(?:무시|잊)",
    r"AI\s*(?:어시스턴트|비서|에이전트|모델)\s*(?:에게|께|는|은|를\s*위한)",
    r"시스템\s*프롬프트",
    r"(?:너는|당신은)\s*이제(?:부터)?",
    r"(?:지시|지침)(?:\s*사항)?(?:을|를)\s*(?:공개|알려|보여|출력)",
    # Japanese
    r"(?:以前|前|これまで|今まで|上記|従来)の(?:すべての|全ての)?(?:指示|命令|プロンプト|ルール)(?:を|は)?(?:すべて|全て)?"
    r"(?:無視|忘れ)",
    r"AI\s*(?:アシスタント|エージェント|モデル)\s*(?:へ|に告ぐ|への|の皆|に対する)",
    r"システム\s*プロンプト",
    r"あなたは(?:今から|これから|今後)",
    r"(?:指示|命令)(?:内容)?を(?:開示|表示|教え|出力|公開)",
]

INJECTION = re.compile("|".join("(?:%s)" % p for p in _INJECTION_PARTS), re.IGNORECASE)

# A request for money or identity numbers ...
_MONEY_OR_ID = re.compile(
    r"bank\s+transfer|wire\s+transfer|money\s+transfer|transfer\s+(?:the\s+)?money|send\s+money|western\s+union"
    r"|gift\s+cards?|passport\s+(?:number|no\.?|details)|(?:credit\s+|debit\s+)?card\s+(?:number|no\.?|details)|\bcvv\b"
    r"|송금|계좌\s*이체|여권\s*번호|카드\s*번호"
    r"|振込|振り込|送金|パスポート番号|旅券番号|カード番号",
    re.IGNORECASE,
)
# ... phrased as an order to the assistant or to the traveller.
_ADDRESSED = re.compile(
    r"\b(?:ai|assistant|agent|chatbot)s?\b"
    r"|(?:tell|inform|instruct|ask|advise)\s+(?:the\s+|your\s+)?(?:travell?er|user|customer|visitor|tourist|guest|her|him|them)"
    r"|(?:you|she|he|they|travell?ers?|visitors?|tourists?|customers?|guests?)\s+(?:must|have\s+to|need\s+to|should)\s+"
    r"(?:now\s+|immediately\s+|first\s+)?(?:pay|send|transfer|provide|give|enter|share)"
    r"|어시스턴트|여행자에게|고객에게|(?:보내|송금해|이체해|알려)\s*(?:야\s*합니다|주세요|주십시오)"
    r"|アシスタント|旅行者に|お客様に|(?:送って|振り込んで|伝えて|教えて)ください",
    re.IGNORECASE,
)

RULE_INJECTION = "injection:instruction_to_assistant"
RULE_PAYMENT = "payment_or_identity_request"
RULE_MALFORMED = "malformed_result"


def _fold(text):
    """Lower case, full-width forms to plain ones, runs of whitespace to one space."""
    return " ".join(unicodedata.normalize("NFKC", str(text)).lower().split())


def screen_text(text):
    """Return the name of the rule the text breaks, or None."""
    folded = _fold(text)
    if INJECTION.search(folded):
        return RULE_INJECTION
    if _MONEY_OR_ID.search(folded) and _ADDRESSED.search(folded):
        return RULE_PAYMENT
    return None


def screen_results(results):
    """Split search results into passed and withheld. Result text is data, never instructions."""
    passed, withheld = [], []
    for result in results or []:
        if not isinstance(result, dict):
            withheld.append({"url": "", "rule": RULE_MALFORMED, "sample": str(result)[:120]})
            continue
        url = str(result.get("url") or "")
        text = "%s\n%s" % (result.get("title") or "", result.get("content") or "")
        rule = screen_text(text + "\n" + url)
        if rule:
            withheld.append({"url": url, "rule": rule, "sample": str(result.get("content") or "")[:120]})
        else:
            passed.append(result)
    return {"passed": passed, "withheld": withheld}


# --------------------------------------------------------------------------
# 2. Tool policy (deny by default)
# --------------------------------------------------------------------------
# args spec per argument name:
#   a list                         -> the value must be one of the list
#   {"each_in_state": k, "rule": r} -> the value is a list; every item must be in state[k]

POLICY = {
    "search_options": {"max_calls": 3, "args": {"category": ["see", "shop", "eat"]}},
    "find_place": {"max_calls": 12, "args": {}},
    "save_options": {"max_calls": 2, "args": {}},
    "walking_route": {"max_calls": 12, "args": {}},      # five picks have ten pairs
    "rest_spots": {"max_calls": 12, "args": {}},
    "propose_route": {"max_calls": 3, "args": {"stops": {"each_in_state": "picks", "rule": "stop_not_picked"}}},
    "read_draft": {"max_calls": 6, "args": {}},
    "submit_review": {"max_calls": 3, "args": {}},
    "route_facts": {"max_calls": 6, "args": {}},
    "record_feedback": {"max_calls": 1, "args": {"verdict": ["fine", "too_far"]}},
    "forget_fact": {"max_calls": 1, "args": {}},
    "read_request": {"max_calls": 1, "args": {}},
    "search_places": {"max_calls": 3, "args": {"category": ["see", "shop", "eat"]}},
    "find_candidates": {"max_calls": 1, "args": {}},
    "describe_candidates": {"max_calls": 3, "args": {}},
    "record_said": {"max_calls": 1, "args": {}},
    "record_context": {"max_calls": 1, "args": {}},
    "scout": {"max_calls": 2, "args": {}},
    "option_scout": {"max_calls": 2, "args": {}},
    "router": {"max_calls": 3, "args": {}},
    "critic": {"max_calls": 3, "args": {}},
    "companion": {"max_calls": 20, "args": {}},
    # Google Places over MCP (gilmate/places_server.py): the scout has these only when GOOGLE_API_KEY is set
    "places_search": {"max_calls": 15, "args": {"category": ["see", "shop", "eat"]}},    # 3 kinds, then one per place
    "place_details": {"max_calls": 5, "args": {}},
}


def _stop_id(stop):
    if isinstance(stop, dict):
        return stop.get("option_id") or stop.get("id")
    return stop


def check_policy(tool, args, calls_so_far, state):
    """Return the name of the violated rule, or None when the call is allowed.

    calls_so_far counts the earlier calls of this tool, so the first call passes 0.
    """
    entry = POLICY.get(tool)
    if entry is None:
        return "deny_by_default:tool_not_in_policy"
    if calls_so_far >= entry["max_calls"]:
        return "%s.max_calls:%d" % (tool, entry["max_calls"])
    args = args or {}
    state = state or {}
    if find_keys(json.dumps(args, ensure_ascii=False, default=str)):
        return RULE_KEY                          # no tool is ever called with a key in its arguments
    for name, spec in entry.get("args", {}).items():
        value = args.get(name)
        if isinstance(spec, dict):
            allowed = state.get(spec["each_in_state"]) or []
            if not isinstance(value, (list, tuple)) or not value:
                return "%s.args.%s" % (tool, name)
            for item in value:
                if _stop_id(item) not in allowed:
                    return "%s.%s" % (tool, spec["rule"])
        elif not isinstance(value, str) or value not in spec:
            return "%s.args.%s" % (tool, name)
    return None


# --------------------------------------------------------------------------
# 3. Grounding of option facts
# --------------------------------------------------------------------------

def _digit_runs(text):
    """Numbers in the text as digit strings; the comma in 1,200 is dropped so it equals 1200."""
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    return re.findall(r"\d+", text)


def ground_option(option, seen):
    """Return a list of problems; an empty list means every fact is backed by a seen source.

    seen maps the url of each passed search result to its text.
    """
    problems = []
    for fact in (option or {}).get("facts") or []:
        label = str(fact.get("label") or "")
        url = fact.get("source_url") or ""
        quote = str(fact.get("quote") or "")
        if url not in seen:
            problems.append("source_not_seen:%s" % url)
            continue
        if not _fold(quote) or _fold(quote) not in _fold(seen[url]):
            problems.append("quote_not_found:%s" % label)
            continue
        quote_numbers = set(_digit_runs(quote))
        missing = [n for n in _digit_runs(fact.get("value") or "") if n not in quote_numbers]
        if missing:
            problems.append("value_not_in_quote:%s:%s" % (label, ",".join(missing)))
    return problems


def ground_description(candidate, seen):
    """Problems with a candidate's description; an empty list means it is tied to a source that was read.

    candidate: {description: {en, ko}|None, description_source: {url, quote, ko?: {url, quote}}|None}.
    No description is no problem: the card then says "No description found". A description needs its source in
    seen and its quote in that text, and every number it states must stand in the quote. A Korean text copied
    from its own page (description_source.ko) is checked against that page.
    """
    description = (candidate or {}).get("description")
    if not description:
        return []
    source = (candidate or {}).get("description_source") or {}
    problems = []
    for language in ("en", "ko"):
        text = str(description.get(language) or "")
        own = source.get(language) if isinstance(source.get(language), dict) else source
        url, quote = own.get("url") or "", str(own.get("quote") or "")
        if language == "en" and not text.strip():
            problems.append("description_empty")
            continue
        if not text.strip():
            continue                                    # no Korean yet: the page shows the English
        if url not in seen:
            problems.append("description_source_not_seen:%s" % url)
            continue
        if not _fold(quote) or _fold(quote) not in _fold(seen[url]):
            problems.append("description_quote_not_found:%s" % language)
            continue
        missing = [n for n in _digit_runs(text) if n not in set(_digit_runs(quote))]
        if missing:
            problems.append("description_number_not_in_quote:%s:%s" % (language, ",".join(missing)))
        if screen_text(text):
            problems.append("description_withheld:%s" % language)
    return problems


_STOP = set("""about above after again also another around because been before being between both could does doing
during each from have having here into more most much must near only other over same should some such than that
their them then there these they this those through under until very were what when where which while will with
would your place places visitors visitor people offers offer known well many""".split())


def _sentence_list(text):
    return [part.strip() for part in re.split(r"(?<=[.!?。])\s+", " ".join(str(text or "").split())) if part.strip()]


def unsupported_sentences(text, source):
    """The sentences of an English text that the source page does not support. Checked sentence by sentence.

    A sentence is supported when every number and every name in it (a capitalised word that does not open the
    sentence) stands in the source, and at least two thirds of its other content words do (compared by their
    first five letters, so "views" finds "view"). A sentence with no checkable word is not supported.
    """
    page = _fold(source)
    page_numbers = set(_digit_runs(source))
    failed = []
    for sentence in _sentence_list(text):
        words = re.findall(r"[^\W\d_]{2,}", unicodedata.normalize("NFKC", sentence))
        names = [w for w in words[1:] if w[0].isupper()]
        content = [w.lower() for w in words if len(w) >= 4 and w.lower() not in _STOP]
        found = [w for w in content if w[:5] in page]
        ok = bool(content) and len(found) * 3 >= len(content) * 2
        ok = ok and all(n.lower() in page for n in names) and all(n in page_numbers for n in _digit_runs(sentence))
        if not ok:
            failed.append(sentence)
    return failed


def ground_written_description(description, source_text):
    """A description a model wrote, kept only as far as the source supports it. Returns ({en, ko}|None, dropped).

    English sentences the source does not support are dropped. The Korean is the model's translation and cannot be
    compared word by word: it is kept only when no English sentence was dropped, and then only when every number
    and every word in Latin letters in it stands in the source; otherwise it is left empty.
    """
    sentences = _sentence_list((description or {}).get("en"))
    failed = unsupported_sentences((description or {}).get("en"), source_text)
    kept = [s for s in sentences if s not in failed]
    if not kept:
        return None, failed
    korean = str((description or {}).get("ko") or "").strip()
    page, numbers = _fold(source_text), set(_digit_runs(source_text))
    latin = re.findall(r"[A-Za-z]{3,}", korean)
    if failed or any(w.lower() not in page for w in latin) or any(n not in numbers for n in _digit_runs(korean)):
        korean = ""
    return {"en": " ".join(kept), "ko": korean}, failed


_RATING_WORDS = re.compile(r"rat(?:ed|ing)|stars?|score|review|/\s*5|out of|★|평점|별점|評価|点", re.IGNORECASE)


def ground_rating(candidate, seen, names):
    """Problems with a candidate's rating; an empty list means a source that was read states it for this place.

    candidate: {rating: {value, source_url, quote}|None}. names: the names the map has for the place.
    "Top rated" is never said without this: the source must have been read, the quote must stand in it and speak of
    a rating, the value's numbers must stand in the quote, and the quote or its page must name the place.
    """
    rating = (candidate or {}).get("rating")
    if not rating:
        return []
    url, quote, value = rating.get("source_url") or "", str(rating.get("quote") or ""), str(rating.get("value") or "")
    if url not in seen:
        return ["rating_source_not_seen:%s" % url]
    if not _fold(quote) or _fold(quote) not in _fold(seen[url]):
        return ["rating_quote_not_found"]
    numbers = _digit_runs(value)
    if not numbers or any(n not in set(_digit_runs(quote)) for n in numbers):
        return ["rating_value_not_in_quote"]
    if not _RATING_WORDS.search(quote):
        return ["rating_quote_is_not_a_rating"]
    page = " %s " % re.sub(r"[^\w]+", " ", _fold(seen[url]))
    if not any(n and len(_fold(n)) >= 3 and " %s " % re.sub(r"[^\w]+", " ", _fold(n)).strip() in page for n in names):
        return ["rating_source_does_not_name_the_place"]
    return []


def access_label(tags):
    """OpenStreetMap wheelchair tag as yes|limited|no|unknown. Anything missing or odd is unknown."""
    value = str((tags or {}).get("wheelchair") or "").strip().lower()
    return value if value in ("yes", "limited", "no") else "unknown"


# --------------------------------------------------------------------------
# 3b. Outside text inside a tool result, keys, file names
# --------------------------------------------------------------------------
# Whatever a tool returns is data. Before a model sees it, every string in it is screened on its own: a place
# name from the map, a field of a Google Places record, a warning text, a photo credit. A string that reads like
# an instruction is replaced by a fixed marker; a string that holds something shaped like a key loses the key.

RULE_KEY = "secret:key_shape"
WITHHELD_TEXT = "[withheld: this text read like an instruction]"
KEY_REMOVED = "[key removed]"

# The shapes of the four keys this project uses, and of a key handed over in an address.
KEY_SHAPES = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{20,}"                  # Anthropic
    r"|tvly-[A-Za-z0-9_-]{20,}"                   # Tavily
    r"|AIza[0-9A-Za-z_-]{35}"                     # Google
    r"|MLY\|\d+\|[0-9a-f]{32}"                    # Mapillary
    r"|(?:access_token|api_key|apikey|client_secret)=[A-Za-z0-9|_%-]{16,}",
    re.IGNORECASE,
)


def find_keys(text):
    """Where the text holds something shaped like a key: a list of (position, kind). The key itself is not returned."""
    return [(m.start(), m.group(0)[:4].lower().rstrip("-|=")) for m in KEY_SHAPES.finditer(str(text))]


def redact(text):
    """The text with every key-shaped part replaced."""
    return KEY_SHAPES.sub(KEY_REMOVED, str(text))


def screen_fields(value, _path=""):
    """Screen every string inside a tool result. Returns (clean value, withheld).

    withheld: [ {field, rule, sample} ]; field is the path of the string ("candidates[2].name"). Numbers, booleans
    and the shape of the value stay as they are, so Python's own facts pass; only words are judged.
    """
    withheld = []

    def walk(item, path):
        if isinstance(item, str):
            rule = screen_text(item)
            if rule:
                withheld.append({"field": path, "rule": rule, "sample": redact(item)[:120]})
                return WITHHELD_TEXT
            if KEY_SHAPES.search(item):
                withheld.append({"field": path, "rule": RULE_KEY, "sample": ""})
                return redact(item)
            return item
        if isinstance(item, dict):
            return {key: walk(inner, "%s.%s" % (path, key) if path else str(key)) for key, inner in item.items()}
        if isinstance(item, (list, tuple)):
            return [walk(inner, "%s[%d]" % (path, i)) for i, inner in enumerate(item)]
        return item

    return walk(value, _path), withheld


_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}\Z")


def safe_file_name(name):
    """True when a cache file name is one plain name: no folder, no "..", no odd character. Outside text never
    names a file directly; a name built from it goes through a hash or a fixed alphabet first, and this checks it."""
    return isinstance(name, str) and bool(_SAFE_NAME.match(name)) and ".." not in name


# --------------------------------------------------------------------------
# 4. Hash-chained audit log
# --------------------------------------------------------------------------
# One JSON object per line. "prev" is the sha256 of the line before (64 zeros for the
# first line). Because the last line has no successor, its hash is also kept in a small
# file next to the log (<path>.head); with it, edits to the last line and cut-off ends
# are detected as well.

_GENESIS = "0" * 64


def _sha(line):
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _lines(path):
    with open(path, encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if line.strip()]


def audit(event, path):
    """Append the event as one JSON line and return the record that was written."""
    lines = _lines(path) if os.path.exists(path) else []
    record = {key: redact(value) if isinstance(value, str) else value for key, value in dict(event).items()}
    record["t"] = time.time()
    record["prev"] = _sha(lines[-1]) if lines else _GENESIS
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    with open(path + ".head", "w", encoding="utf-8") as handle:
        handle.write(_sha(line) + "\n")
    return record


def verify_chain(path):
    """True when no line of the log was edited, removed or inserted. A missing log is not verified."""
    if not os.path.exists(path):
        return False
    lines = _lines(path)
    expected = _GENESIS
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            return False
        if not isinstance(record, dict) or record.get("prev") != expected:
            return False
        expected = _sha(line)
    if os.path.exists(path + ".head"):
        with open(path + ".head", encoding="utf-8") as handle:
            return handle.read().strip() == expected
    return True
