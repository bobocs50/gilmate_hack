"""Free check of scripts/demo.sh: no network beyond this machine, no key, no model, no search.

    python3 scripts/demo_check.py

What it checks:
- `--saved` under bash and zsh: the printed address serves the page, Ctrl-C ends the script
  and the port is closed afterwards.
- the live mode with keys missing: it stops before starting anything, names what is missing,
  offers `--saved`, and never prints the value of a key.
It does not start the agent server.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "demo.sh")
SECRET = "sk-value-that-must-never-be-printed"
failures = []


def check(ok, what):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        failures.append(what)


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "MAPILLARY_TOKEN", "GILMATE_DEMO_ENV")}
    env.update(extra)
    return env


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status, r.read()
    except Exception:
        return None, b""


def saved(shell):
    out = tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False)
    # its own process group, as a terminal gives it, so Ctrl-C can be sent the way a terminal sends it
    p = subprocess.Popen([shell, DEMO, "--saved"], stdout=out, stderr=subprocess.STDOUT,
                         env=clean_env(), start_new_session=True)
    url = None
    try:
        for _ in range(100):
            text = open(out.name).read()
            if "Press Ctrl-C" in text:
                found = re.search(r"http://127\.0\.0\.1:\d+/\S*", text)
                url = found.group(0) if found else None
                break
            if p.poll() is not None:
                break
            time.sleep(0.2)
        check(url is not None, "%s --saved prints the address to open" % shell)
        if url:
            status, body = get(url)
            check(status == 200 and b"<html" in body.lower(), "%s --saved: %s serves the page" % (shell, url))
            check(get(url + "js/main.js")[0] == 200, "%s --saved: the page's script is served" % shell)
    finally:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGINT)
        try:
            code = p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            code = None
    check(code == 130, "%s --saved: Ctrl-C ends the script (exit %s)" % (shell, code))
    if url:
        check(get(url)[0] is None, "%s --saved: nothing answers on the port afterwards" % shell)
    os.unlink(out.name)


def live(shell, env_text, missing, present, label):
    folder = tempfile.mkdtemp(prefix="gilmate-demo-check-")
    path = os.path.join(folder, "env")
    if env_text is not None:
        with open(path, "w") as f:
            f.write(env_text)
    r = subprocess.run([shell, DEMO], capture_output=True, text=True, timeout=30,
                       env=clean_env(GILMATE_DEMO_ENV=path))
    text = r.stdout + r.stderr
    check(r.returncode == 1, "%s live, %s: does not start (exit %s)" % (shell, label, r.returncode))
    for name in missing:
        check("Missing: %s" % name in text, "%s live, %s: says %s is missing" % (shell, label, name))
    for name in present:
        check("Missing: %s" % name not in text, "%s live, %s: does not call %s missing" % (shell, label, name))
    check("scripts/demo.sh --saved" in text, "%s live, %s: offers --saved" % (shell, label))
    check(SECRET not in text, "%s live, %s: prints no value of a key" % (shell, label))
    check("Open:" not in text, "%s live, %s: prints no address" % (shell, label))
    shutil.rmtree(folder)


shells = [s for s in ("/bin/bash", "/bin/zsh") if os.path.exists(s)]
check(bool(shells), "bash or zsh is there to run the script")
for shell in shells:
    saved(shell)
    live(shell, None, ["ANTHROPIC_API_KEY", "TAVILY_API_KEY"], [], "no .env")
    live(shell, "ANTHROPIC_API_KEY=%s\nTAVILY_API_KEY=\n" % SECRET,
         ["TAVILY_API_KEY"], ["ANTHROPIC_API_KEY"], "one key empty")
    live(shell, "# TAVILY_API_KEY=%s\nexport ANTHROPIC_API_KEY=\"%s\"\nTAVILY_API_KEY=''\n" % (SECRET, SECRET),
         ["TAVILY_API_KEY"], ["ANTHROPIC_API_KEY"], "commented out and empty quotes")

print("\n%d failed" % len(failures) if failures else "\nall passed")
sys.exit(1 if failures else 0)
