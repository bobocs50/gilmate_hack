"""One full live run from the terminal, with a trace. PAID: about 25 model calls, and up to 3 searches when
the saved search results in data/cache/tavily are missing. Saves frontend/data/run.json.

The turns are the ones the page sends (CONTRACT.md 3 and 6.2): options, route, ask, feedback, forget.
Usage: python scripts/run_once.py [--attack] [--out <file>]
  --attack   plant the search result of tests/fixtures/planted_result.json; this run is never saved as run.json
  --out      save the run somewhere else than frontend/data/run.json"""
import asyncio, json, logging, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))   # keys live in .env next to this repo's README, never in git
from google.adk.runners import InMemoryRunner
from google.genai import types
from gilmate import tools
from gilmate.agent import app

PROFILE = {"walk": "short", "stairs": "avoid", "rest": "often", "food": "sushi", "wish": None, "language": "ko"}
ATTACK = "--attack" in sys.argv
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "frontend", "data", "run.json")


class ModelCalls(logging.Handler):
    """Counts the requests to the model as the HTTP client logs them."""
    count = 0

    def emit(self, record):
        if "/v1/messages" in record.getMessage():
            ModelCalls.count += 1


for name in ("httpx", "httpx2"):     # whichever HTTP client the model library uses
    logging.getLogger(name).setLevel(logging.INFO)
    logging.getLogger(name).addHandler(ModelCalls())


def saved_searches():
    return set(os.listdir(tools.CACHE)) if os.path.isdir(tools.CACHE) else set()


async def turn(runner, sid, payload):
    print(f"\n=== {json.dumps(payload, ensure_ascii=False)}")
    t0, final, before = time.time(), "", ModelCalls.count
    msg = types.Content(role="user", parts=[types.Part(text=json.dumps(payload, ensure_ascii=False))])
    async for ev in runner.run_async(user_id="u1", session_id=sid, new_message=msg):
        for c in ev.get_function_calls():
            print(f"  [{ev.author}] CALL {c.name} {json.dumps(dict(c.args or {}), ensure_ascii=False)[:150]}")
        for r in ev.get_function_responses():
            print(f"  [{ev.author}] RESULT {r.name} -> {json.dumps(r.response, ensure_ascii=False, default=str)[:170]}")
        if ev.author == "coordinator" and ev.is_final_response() and ev.content and ev.content.parts:
            final = "".join(p.text or "" for p in ev.content.parts)
    print(f"  FINAL ({time.time() - t0:.0f}s, {ModelCalls.count - before} model calls): {final}")
    return final


async def main():
    searches_before = saved_searches()
    runner = InMemoryRunner(app=app)
    state = {"profile": PROFILE, "attack": ATTACK}

    async def read():
        return (await runner.session_service.get_session(app_name=app.name, user_id="u1", session_id=s.id)).state

    s = await runner.session_service.create_session(app_name=app.name, user_id="u1", state=state)
    await turn(runner, s.id, {"step": "options"})
    st = await read()
    opts = st.get("options", [])
    for o in opts:
        print("   ", o["id"], o["category"], o["name"], o["place"]["access"])
    if len(opts) == 6:
        picks = [next(o["id"] for o in opts if o["category"] == c) for c in ("see", "shop", "eat")]
        await turn(runner, s.id, {"step": "route", "picks": picks})
    st = await read()
    if st.get("spatial_model"):
        await turn(runner, s.id, {"step": "ask", "stop_id": "s1", "question": "다음 장소까지 얼마나 걸어야 해요? 계단이 있어요?"})
        leg = st["spatial_model"]["legs"][0]
        await turn(runner, s.id, {"step": "feedback", "leg_id": leg["id"], "verdict": "too_far"})
        st = await read()
        limit = next((f for f in st.get("user:memory", {}).get("facts", []) if f["key"] == "walk_limit_m"), None)
        print("    learned:", json.dumps(limit, ensure_ascii=False))
        if limit:
            await turn(runner, s.id, {"step": "forget", "fact_id": limit["id"]})
            st = await read()
            print("    memory after forget:", [(f["id"], f["key"], f["value"]) for f in st["user:memory"]["facts"]])
    # the shape of CONTRACT.md section 2
    out = {"recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           **{k: st.get(k) for k in ("profile", "options", "picks", "spatial_model", "audit", "user:memory")}}
    print(f"\nmodel calls: {ModelCalls.count}; fresh searches: {len(saved_searches() - searches_before)}; "
          f"audit rows: {len(st.get('audit', []))}")
    if not st.get("spatial_model"):
        print("no spatial model; nothing saved; state keys:", sorted(st.keys()))
    elif ATTACK and "--out" not in sys.argv:
        print("attack run: not saved as run.json; review:", st["spatial_model"]["review"])
    else:
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"saved {os.path.relpath(OUT, ROOT)}; review:", st["spatial_model"]["review"])

asyncio.run(main())
