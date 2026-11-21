"""Her typed answers (CONTRACT.md section 7.3, the "say" turn).

She may type instead of pressing. What she typed never goes into the session: only one of the fixed choices of
the step she is at does, and only through accept().

    allowed(step)            the fixed choices of a step, in the order the page numbers them
    accept(step, choice)     a choice the model proposed -> that choice, or "not_understood"
    match(step, text)        obvious answers in English and Korean, decided here -> a choice, or None
    said(step, choice)       the value for state["said"]: {about, choice, at}
    context(text, proposed)  one free text about yourself (the "context" turn) -> the answers it tells, and which
                             of walk, stairs, rest it does not tell
    quoted(text, words)      words that stand in the text -> those words; anything else -> None

A step is what the page sends as `about`: a candidate id ("c3"), a question key ("walk", "stairs", "rest"),
or None when no card and no question is open. match() answers None for everything that is not obvious; then
the model reads her words and proposes a choice, which goes through accept() like any other.
Plain Python: no ADK, no network, no model.
"""
import re
import time
import unicodedata

from . import osm

NOT_UNDERSTOOD = "not_understood"
PLACE = ("yes", "no", "more")
NOTHING_OPEN = ("yes", "no")
QUESTIONS = {
    "walk": ("short", "medium", "long"),
    "stairs": ("avoid", "few", "ok"),
    "rest": ("often", "sometimes", "rarely"),
}
CANDIDATE_ID = re.compile(r"c[1-9][0-9]{0,2}\Z")
MAX_TYPED = 60          # an obvious answer is short; anything longer is for the model to read

# Obvious answers, as she might type them. Compared after folding (lower case, punctuation dropped).
_YES = ("yes", "y", "yes please", "yeah", "yep", "ok", "okay", "sure",
        "네", "예", "응", "좋아요", "좋아", "좋습니다", "네 좋아요", "그래요", "갈래요", "가고 싶어요", "가 볼래요")
_NO = ("no", "n", "nope", "no thanks", "no thank you",
       "아니요", "아니오", "아니", "아뇨", "싫어요", "안 가요", "안 갈래요", "됐어요")
_MORE = ("more", "more please", "tell me more", "more info", "details",
         "더", "더 알려주세요", "더 알려 주세요", "더 보여주세요", "더 보여 주세요", "자세히", "자세히 알려주세요")
PHRASES = {
    "place": {"yes": _YES, "no": _NO, "more": _MORE},
    "nothing_open": {"yes": _YES, "no": _NO},
    "walk": {
        "short": ("short", "a short walk", "짧게", "조금만", "조금"),
        "medium": ("medium", "보통", "중간"),
        "long": ("long", "a long walk", "far", "오래", "멀리", "많이"),
    },
    "stairs": {
        # "yes" and "no" alone are not here: what they mean depends on how the question was put
        "avoid": ("avoid", "avoid stairs", "avoid steps", "no stairs", "no steps", "no stairs please", "without stairs",
                  "i cant climb stairs", "i cannot climb stairs",
                  "계단 안 돼요", "계단 안돼요", "계단은 안 돼요", "계단 없이", "계단 없는 길", "계단 싫어요",
                  "계단 못 올라가요", "계단은 못 올라가요", "계단 못 가요", "계단 피하고 싶어요"),
        "few": ("few", "a few", "few stairs", "a few stairs", "a few steps", "some stairs",
                "계단 조금", "계단 조금은 괜찮아요", "조금은 괜찮아요", "몇 계단은 괜찮아요"),
        "ok": ("ok", "okay", "fine", "stairs ok", "stairs okay", "stairs are ok", "stairs are fine", "no problem",
               "괜찮아요", "계단 괜찮아요", "계단은 괜찮아요", "문제없어요", "문제 없어요"),
    },
    "rest": {
        "often": ("often", "very often", "자주", "자주 쉬어야 해요"),
        "sometimes": ("sometimes", "가끔", "가끔씩"),
        "rarely": ("rarely", "seldom", "hardly ever", "드물게", "거의 안 쉬어요"),
    },
}
# Words around a distance that change nothing: "about 300 m", "I can walk 400 metres", "500미터 정도".
_AROUND_A_DISTANCE = {"about", "around", "roughly", "maybe", "up", "to", "i", "can", "walk", "at", "most", "or", "so",
                      "she", "he", "we", "only",
                      "약", "한", "정도", "정도는", "쯤", "까지", "걸을", "수", "있어요", "걸어요"}
_DISTANCE = re.compile(r"(\d+(?:\.\d+)?)(m|meters?|metres?|미터|km|kilometers?|kilometres?|킬로|킬로미터)?(?:쯤|정도|까지)?\Z")
_NUMBERED = re.compile(r"([1-9])(?:번)?\Z")


def _ids(candidates):
    """The candidate ids of this session, from a list of ids or of candidates. None: not given."""
    if candidates is None:
        return None
    return {c.get("id") if isinstance(c, dict) else c for c in candidates}


def _kind(step, candidates=None):
    if step is None:
        return "nothing_open"
    if not isinstance(step, str):
        return None
    if step in QUESTIONS:
        return step
    ids = _ids(candidates)
    if CANDIDATE_ID.match(step) and (ids is None or step in ids):
        return "place"
    return None


def allowed(step, candidates=None):
    """The fixed choices of a step, in the order the page numbers them. Nothing for a step that does not exist.

    candidates: the ids (or the candidates) of this session. When given, a candidate id must be one of them.
    """
    kind = _kind(step, candidates)
    if kind is None:
        return ()
    return {"place": PLACE, "nothing_open": NOTHING_OPEN}.get(kind) or QUESTIONS[kind]


def accept(step, choice, candidates=None):
    """A proposed choice for a step: that choice when it is one of the step's fixed choices, else "not_understood".

    The only way an answer gets into the session. Nothing is guessed, cut out of a longer text or repaired.
    """
    if not isinstance(choice, str):
        return NOT_UNDERSTOOD
    choice = choice.strip().lower()
    return choice if choice in allowed(step, candidates) else NOT_UNDERSTOOD


def _plain(text):
    """True for text an obvious answer can be: a short string without control characters or a negative number."""
    if not isinstance(text, str) or len(text) > MAX_TYPED:
        return False
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cs") and ch not in "\t\n\r" for ch in text):
        return False
    return not re.search(r"[-\u2212\u2013\u2014]\s*\d", unicodedata.normalize("NFKC", text))


def _fold(text):
    """Lower case, full-width forms to plain ones, punctuation to spaces; a point or comma inside a number stays."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"['’`]", "", text)                              # can't -> cant
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)            # 1,000 -> 1000
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)                    # 0,5 -> 0.5
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return " ".join(re.sub(r"[^\w\s.]|_", " ", text).split())


def _phrase(kind, folded, more=None):
    """The one choice the whole text says, word for word from the lists above. Two different choices: none.

    more: further phrases {choice: (phrase, ...)} that count as well (the "context" turn's).
    """
    table = {}
    for value, phrases in PHRASES[kind].items():
        for p in phrases + tuple((more or {}).get(value, ())):
            table[_fold(p)] = value
    if folded.replace(" ", "") in {p.replace(" ", ""): v for p, v in table.items()}:
        return {p.replace(" ", ""): v for p, v in table.items()}[folded.replace(" ", "")]
    words, found, i = folded.split(), set(), 0
    while i < len(words):
        for n in range(min(5, len(words) - i), 0, -1):         # the longest phrase first: "no stairs" before "no"
            value = table.get(" ".join(words[i:i + n]))
            if value:
                found.add(value)
                i += n
                break
        else:
            return None                                         # a word that is in no list: not obvious
    return found.pop() if len(found) == 1 else None


def metres(text):
    """A distance she typed, in metres, when the text is nothing but that distance. Otherwise None."""
    if not _plain(text):
        return None
    words = [w for w in _fold(text).split() if w not in _AROUND_A_DISTANCE]
    if sum(any(ch.isdigit() for ch in w) for w in words) != 1:
        return None                                             # "3 or 4 km" is two numbers, not one distance
    found = _DISTANCE.match("".join(words))
    if not found:
        return None
    number, unit = float(found.group(1)), found.group(2) or ""
    if unit.startswith(("k", "킬")):
        number *= 1000
    elif not unit and number < 50:
        return None                                             # "2" is the second choice, not two metres
    return round(number) if 0 < number <= 100000 else None


def walk_for(distance_m):
    """Her answer about walking for a distance in metres: the longest limit that is not longer than she said.

    "long" has no limit (osm.WALK_LIMIT_M), so a distance never gives it. A distance below the shortest limit
    gives the shortest: the profile has no smaller value.
    """
    limits = sorted((limit, value) for value, limit in osm.WALK_LIMIT_M.items() if limit is not None)
    chosen = limits[0][1]
    for limit, value in limits:
        if limit <= distance_m:
            chosen = value
    return chosen


def match(step, text, candidates=None):
    """An obvious typed answer, decided without the model: one of the step's choices, or None.

    Obvious means: the whole text is one of the listed answers (English or Korean, or both saying the same),
    the number of a choice ("2", "2번"), or for `walk` a distance ("300 m", "500미터 정도", "0.5 km").
    Everything else is None, which means "ask the model", never "no".
    """
    kind = _kind(step, candidates)
    if kind is None or not _plain(text):
        return None
    folded = _fold(text)
    if not folded:
        return None
    choices = allowed(step, candidates)
    numbered = _NUMBERED.match(folded)
    if numbered:
        n = int(numbered.group(1))
        return accept(step, choices[n - 1], candidates) if n <= len(choices) else None
    value = _phrase(kind, folded)
    if value is None and kind == "walk":
        distance = metres(text)
        value = walk_for(distance) if distance is not None else None
    if value is None:
        return None
    value = accept(step, value, candidates)
    return None if value == NOT_UNDERSTOOD else value


def said(step, choice, candidates=None, at=None):
    """The value for state["said"] after a "say" turn. A step that does not exist is stored as None, not as typed."""
    known = _kind(step, candidates) is not None
    return {"about": step if known else None,
            "choice": accept(step, choice, candidates) if known else NOT_UNDERSTOOD,
            "at": at or time.strftime("%H:%M:%S")}


# --- the "context" turn: one free text about yourself instead of the answer buttons ---------------------------------
# Sentences a person may write about themselves, besides the answers above. Each is one part of the text.
CONTEXT_PHRASES = {
    "walk": {
        "short": ("short walks", "only short walks", "i like short walks", "i can only walk a little",
                  "i cant walk far", "i cannot walk far", "i cant walk long", "i cannot walk long",
                  "조금만 걸어요", "조금만 걸을 수 있어요", "오래 못 걸어요", "많이 못 걸어요", "멀리 못 걸어요"),
        "medium": ("medium walks", "i can walk a while", "보통으로 걸어요"),
        "long": ("long walks", "i like long walks", "i can walk far", "i can walk a lot", "walking is no problem",
                 "오래 걸을 수 있어요", "많이 걸어도 괜찮아요", "멀리 걸을 수 있어요"),
    },
    "stairs": {
        "avoid": ("i avoid stairs", "i cant do stairs", "i cannot do stairs", "i cant use stairs", "i cannot use stairs",
                  "i cant take stairs", "stairs are hard for me", "stairs are difficult for me", "please avoid stairs",
                  "계단은 힘들어요", "계단이 힘들어요", "계단은 못 가요", "계단은 피해 주세요"),
        "few": ("a few stairs are ok", "a few stairs are fine", "a few steps are ok", "a few steps are fine",
                "계단 조금은 괜찮아요"),
        "ok": ("i can climb stairs", "i can do stairs", "i can take stairs", "stairs are no problem",
               "계단은 문제없어요", "계단은 문제 없어요", "계단도 괜찮아요"),
    },
    "rest": {
        "often": ("i need to rest often", "i need to sit often", "i need to sit down often", "i rest often",
                  "rest often", "i need many breaks", "i need a lot of breaks",
                  "then needs a break", "then needs break", "needs a break", "then she needs a break",
                  "then he needs a break", "then i need a break", "she needs a break", "he needs a break",
                  "자주 쉬어야 해요", "자주 쉬고 싶어요", "자주 앉아야 해요"),
        "sometimes": ("i rest sometimes", "i need to rest sometimes", "i need to sit sometimes", "rest sometimes",
                      "i need a break sometimes", "가끔 쉬어요", "가끔 쉬면 돼요", "가끔 쉬고 싶어요"),
        "rarely": ("i rarely rest", "i rarely need to rest", "i rarely need to sit", "i rarely need a break",
                   "i dont need to rest", "i dont need breaks", "쉬지 않아도 돼요", "거의 안 쉬어요", "안 쉬어도 돼요"),
    },
}
MAX_CONTEXT = 600       # characters of the text that are read
MAX_WISH = 200
# A part of the text counts for a question only when it names what the question is about: "fine" alone says nothing.
_SAYS_WHICH = {"walk": re.compile(r"walk|걷|걸[어을으]"), "stairs": re.compile(r"stair|step|계단"),
               "rest": re.compile(r"rest|sit|break|쉬|앉")}
_WITH_UNIT = re.compile(r"\d\s*(?:m\b|meter|metre|미터|km\b|kilo|킬로)")
_I = {"저는", "나는", "전", "난", "제가", "내가"}      # "I" in Korean, in front of a distance
_PARTS = re.compile(r"[.,;!?]+(?=\s|\Z)|[\n。、，！？]+|\s+(?:and|but|also|그리고|하지만)\s+", re.I)


# Whole sentences about someone ("stairs and steep hills are hard for her, and she can walk about 1 km before she
# needs to sit down"): read on the folded text, each pattern gives one fixed choice or the one distance.
_STAIRS_HARD = re.compile(r"\bstairs?\b(?:\s+\w+){0,4}?\s+(?:is|are)\s+(?:too\s+)?(?:hard|difficult)\b")
_WALK_DISTANCE = re.compile(r"\bwalk\s+(?:only\s+)?(?:about\s+|around\s+|roughly\s+|up\s+to\s+|at\s+most\s+)?"
                            r"(\d+(?:\.\d+)?)\s*(km|kilometers?|kilometres?|m|meters?|metres?)\b")
_THEN_SITS = re.compile(r"\b(?:before|then)\s+(?:(?:she|he|i|we)\s+)?needs?\s+(?:to\s+)?"
                        r"(?:sit(?:\s+down)?|rest|a\s+break|break)\b")
_HILLS = re.compile(r"\bhills?\b")


def _stated_distance(folded):
    """The distances a folded text states after "walk", in metres."""
    return {round(float(n) * (1000 if unit.startswith("k") else 1)) for n, unit in _WALK_DISTANCE.findall(folded)}


def says_hills(text):
    """True when her words name hills. Nothing checks hills yet, so the guide says so instead of pretending."""
    return isinstance(text, str) and bool(_HILLS.search(_fold(text[:MAX_CONTEXT])))


def from_text(text):
    """The answers a free text tells in an obvious way, decided without the model: {walk, stairs, rest}, each only
    when one part of the text says it and no other part says something else."""
    if not isinstance(text, str):
        return {}
    found = {}
    for part in _PARTS.split(text[:MAX_CONTEXT]):
        if not part or not _plain(part):
            continue
        folded = _fold(part)
        if not folded:
            continue
        for step in QUESTIONS:
            names_it = bool(_SAYS_WHICH[step].search(folded))
            value = _phrase(step, folded, CONTEXT_PHRASES[step]) if names_it else None
            if value is None and step == "walk" and (names_it or _WITH_UNIT.search(folded)):
                distance = metres(" ".join(w for w in part.split() if w.casefold() not in _I))
                value = walk_for(distance) if distance is not None else None
            if value is not None:
                found.setdefault(step, set()).add(value)
    whole = _fold(text[:MAX_CONTEXT])
    if _STAIRS_HARD.search(whole):
        found.setdefault("stairs", set()).add("avoid")
    if _THEN_SITS.search(whole):
        found.setdefault("rest", set()).add("often")
    for distance in _stated_distance(whole):
        if 0 < distance <= 100000:
            found.setdefault("walk", set()).add(walk_for(distance))
    return {step: values.pop() for step, values in found.items() if len(values) == 1}


LIMIT_M = (100, 5000)   # a walking limit she states as a distance counts as the limit itself only inside this range


def limit_m(text):
    """The one walking distance a free text states ("she can only walk about 1 km"), in metres, or None.

    Only a part of the text that is nothing but that distance counts (metres), only one such distance in the
    whole text, and only inside LIMIT_M. The number is the only thing of her text that leaves this function."""
    if not isinstance(text, str):
        return None
    found = set()
    for part in _PARTS.split(text[:MAX_CONTEXT]):
        if not part or not _plain(part):
            continue
        folded = _fold(part)
        if folded and (_SAYS_WHICH["walk"].search(folded) or _WITH_UNIT.search(folded)):
            distance = metres(" ".join(w for w in part.split() if w.casefold() not in _I))
            if distance is not None:
                found.add(distance)
    found |= _stated_distance(_fold(text[:MAX_CONTEXT]))
    if len(found) != 1:
        return None
    distance = found.pop()
    return distance if LIMIT_M[0] <= distance <= LIMIT_M[1] else None


def understood(profile, hills=False):
    """What the guide says back about her answers, in fixed words: {"en", "ko"} or None when it knows nothing.
    Hills are named only to say that nothing checks them yet."""
    en, ko = [], []
    if profile.get("stairs") == "avoid":
        en.append("avoid stairs"); ko.append("계단을 피하고")
    limit = profile.get("walk_limit_m") or osm.WALK_LIMIT_M.get(profile.get("walk"))
    if limit:
        shown = ("%g km" % (limit / 1000)) if limit >= 1000 else "%d m" % limit
        en.append("keep walks under %s" % shown); ko.append("한 번에 %s 넘게 걷지 않게 하고" % shown)
    if not en and profile.get("rest") != "often":
        return None
    sit = profile.get("rest") == "often"
    en_text = "I " + " and ".join(en) + (" with places to sit" if sit else "") if en else "I plan places to sit"
    ko_text = " ".join(ko) + (" 앉을 곳을 넣겠습니다" if sit else " 길을 잡겠습니다") if ko else "앉을 곳을 넣겠습니다"
    if hills:
        en_text += "; I cannot check hills yet"; ko_text += ". 언덕은 아직 확인하지 못합니다"
    return {"en": en_text + ".", "ko": ko_text + "."}


def context(text, proposed=None, trust_proposed=True):
    """What one free text tells about walking, stairs and resting: (told, missing).

    told: {step: one of the step's fixed choices}. missing: the steps the text does not tell, in the order asked.
    What the text says in an obvious way is decided here (from_text). For the rest the model's proposal counts,
    {step: choice}, each through accept(); with trust_proposed=False (a text that reads like an instruction) the
    proposals are not looked at. Nothing of the text itself is in the result.
    """
    obvious = from_text(text)
    proposed = proposed if isinstance(proposed, dict) else {}
    told, missing = {}, []
    for step in QUESTIONS:
        value = obvious.get(step)
        if value is None and trust_proposed:
            value = accept(step, proposed.get(step))
        if value is None or value == NOT_UNDERSTOOD:
            missing.append(step)
        else:
            told[step] = value
    return told, missing


def quoted(text, words, most=MAX_WISH):
    """The words when they stand in the text as they are (capitals and spaces aside): the person's own words, cut
    out by the model, never the model's. Otherwise None."""
    if not isinstance(text, str) or not isinstance(words, str):
        return None
    words = " ".join(words.split()).strip(" .,;!?\"'")[:most]
    if len(words) < 3 or any(unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cs") for ch in words):
        return None
    return words if words.casefold() in " ".join(text[:MAX_CONTEXT].split()).casefold() else None
