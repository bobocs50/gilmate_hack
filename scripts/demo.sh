#!/bin/bash
# Start the Gilmate demo with one command.
#
#   scripts/demo.sh            the page on the live agents (needs .env with your keys; using the page costs money)
#   scripts/demo.sh --saved    the page on the saved run (no keys, no model, no search, free)
#   add --phone                so a phone on the same Wi-Fi can open the route (the page is then served to the network)
#
# It picks free ports, waits until the servers answer, prints the one address to open,
# and stops everything it started on Ctrl-C. It never prints or stores the value of a key.
# Written to run the same under macOS bash 3.2, zsh and sh: no arrays, no word splitting.

usage() {
  cat <<'EOF'
Usage: scripts/demo.sh [--saved] [--phone] [--phone-live] [--frontend <folder>]

  (no option)          start the agent server and the page; the page talks to the live agents.
                       Needs .env with ANTHROPIC_API_KEY and TAVILY_API_KEY. Starting is free;
                       every visit on the page then calls the model, which costs money.
  --saved              start only the page, on the saved run in frontend/data/run.json.
                       No keys, no model, no search.
  --phone              also serve the page to this computer's network, so a phone on the same
                       Wi-Fi can open the route from the QR code on the final map. Only the page
                       folder is served (static files, read-only). The agent server stays on this
                       computer, so "Fine" / "Too far" on the phone are kept on the phone, not sent.
  --phone-live         as --phone, and the agent server listens on the network too, so the phone's
                       "Fine" / "Too far" reach the live agents. Anyone on the same network can then
                       send turns to your agents, which costs money. Not for a shared Wi-Fi you do
                       not trust. Has no effect with --saved.
  --frontend <folder>  serve another copy of the page instead of frontend/.
  -h, --help           this text.

Ctrl-C stops everything this script started.
EOF
}

say() { printf '%s\n' "$*"; }
fail() { printf 'demo.sh: %s\n' "$*" >&2; exit 1; }

case "$0" in
  */*) here=${0%/*} ;;
  *) here=. ;;
esac
REPO=$(cd "$here/.." && pwd -P) || fail "cannot find the project folder from $0"

mode=live
phone=no
phone_live=no
FRONTEND=$REPO/frontend
while [ $# -gt 0 ]; do
  case "$1" in
    --saved) mode=saved ;;
    --phone) phone=yes ;;
    --phone-live) phone=yes; phone_live=yes ;;
    --frontend)
      [ $# -ge 2 ] || fail "--frontend needs a folder"
      FRONTEND=$(cd "$2" 2>/dev/null && pwd -P) || fail "no such folder: $2"
      shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; fail "unknown option: $1" ;;
  esac
  shift
done

[ -f "$FRONTEND/index.html" ] || fail "no index.html in $FRONTEND"

# --- Python: the project's virtualenv if there is one ------------------------------------------
VENV=$REPO/.venv
if [ -x "$VENV/bin/python" ]; then
  PY=$VENV/bin/python
  have_venv=yes
else
  PY=$(command -v python3) || PY=
  have_venv=no
fi

venv_help() {
  say "  There is no virtualenv in $VENV. Create it with the two commands from the README:"
  say "    uv venv --python 3.13 && source .venv/bin/activate"
  say "    uv pip install -r requirements.txt"
}

# --- Keys: names only ---------------------------------------------------------------------------
# A name counts as set when it is in the environment, or when .env has a line NAME=<something>.
# grep -q answers yes or no and prints nothing, so no value ever reaches the terminal or a variable.
ENV_FILE=${GILMATE_DEMO_ENV:-$REPO/.env}      # the override exists for scripts/demo_check.py only

name_is_set() {
  eval "[ -n \"\${$1:+x}\" ]" && return 0
  [ -f "$ENV_FILE" ] || return 1
  grep -Eq "^[[:space:]]*(export[[:space:]]+)?$1[[:space:]]*=[[:space:]]*[\"']?[^[:space:]\"'#]" "$ENV_FILE"
}

if [ "$mode" = live ]; then
  problems=0
  if [ ! -f "$ENV_FILE" ]; then
    say "No .env file in $REPO (make one with: cp .env.example .env, then put your two keys in it)."
  fi
  for name in ANTHROPIC_API_KEY TAVILY_API_KEY; do
    if ! name_is_set "$name"; then
      say "Missing: $name is not set in .env."
      problems=1
    fi
  done
  if [ "$have_venv" = no ] || [ ! -x "$VENV/bin/adk" ]; then
    say "Missing: the agent server (adk) is not installed."
    venv_help
    problems=1
  fi
  if [ "$problems" = 1 ]; then
    say ""
    say "The live demo cannot start. The saved run needs no keys:"
    say "    scripts/demo.sh --saved"
    exit 1
  fi
  if ! name_is_set MAPILLARY_TOKEN; then
    say "Note: MAPILLARY_TOKEN is not set (optional). Street photos come from what is already saved."
  fi
else
  if [ -z "$PY" ]; then
    say "Missing: python3 was not found."
    venv_help
    exit 1
  fi
  [ "$have_venv" = yes ] || say "Note: no virtualenv in $VENV; using $PY, which is enough for the saved run."
  [ -f "$FRONTEND/data/run.json" ] || say "Note: $FRONTEND/data/run.json does not exist, so the page will say there is no run."
fi

# --- Start, wait, stop --------------------------------------------------------------------------
LOGS=$(mktemp -d "${TMPDIR:-/tmp}/gilmate-demo.XXXXXX") || fail "cannot make a folder for the logs"
web_pid=
api_pid=
stopped=no

stop_one() {
  # $1 = pid. Ask politely, give it five seconds, then insist.
  [ -n "$1" ] || return 0
  kill "$1" 2>/dev/null || return 0
  n=0
  while kill -0 "$1" 2>/dev/null && [ $n -lt 50 ]; do sleep 0.1; n=$((n + 1)); done
  kill -9 "$1" 2>/dev/null
  wait "$1"
  return 0
} 2>/dev/null      # also keeps the shell's own "Terminated" notice off the screen

cleanup() {
  [ "$stopped" = no ] || return 0
  stopped=yes
  trap - INT TERM HUP EXIT
  if [ -n "$web_pid$api_pid" ]; then
    say ""
    say "Stopping..."
    stop_one "$api_pid"
    stop_one "$web_pid"
    say "Stopped. Logs: $LOGS"
  fi
}
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM HUP
trap 'cleanup' EXIT

free_port() {
  "$PY" -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])'
}

answers() {
  # $1 = address. True when it answers with a success status.
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -o /dev/null --max-time 3 "$1" 2>/dev/null
  else
    "$PY" -c 'import sys, urllib.request
urllib.request.urlopen(sys.argv[1], timeout=3).read(1)' "$1" 2>/dev/null
  fi
}

wait_for() {
  # $1 = address, $2 = pid, $3 = what it is, $4 = its log file
  n=0
  while ! answers "$1"; do
    if ! kill -0 "$2" 2>/dev/null; then
      say "$3 stopped before it answered. The end of its log ($4):"
      tail -n 20 "$4"
      exit 1
    fi
    n=$((n + 1))
    if [ $n -ge 120 ]; then
      say "$3 did not answer at $1 within 60 seconds. The end of its log ($4):"
      tail -n 20 "$4"
      exit 1
    fi
    sleep 0.5
  done
}

# --- The phone: this computer's address on the network --------------------------------------------
# The address the system would use to reach another network. Nothing is sent to find it.
lan_address() {
  "$PY" -c 'import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("192.0.2.1", 9))
    print(s.getsockname()[0])
except OSError:
    pass'
}

WEB_BIND=127.0.0.1
API_HOST=127.0.0.1
LAN=
if [ "$phone" = yes ]; then
  LAN=$(lan_address)
  case "$LAN" in
    ""|127.*)
      say "Note: this computer has no network address right now, so a phone cannot reach it. Starting without --phone."
      LAN=
      phone=no
      phone_live=no ;;
    *) WEB_BIND=0.0.0.0 ;;
  esac
fi

WEB_PORT=$(free_port) || fail "could not find a free port"
WEB=http://127.0.0.1:$WEB_PORT
"$PY" -m http.server "$WEB_PORT" --bind "$WEB_BIND" -d "$FRONTEND" >"$LOGS/web.log" 2>&1 &
web_pid=$!
# What the page needs to write a link the phone can open: ?lan=<this computer on the network>.
LAN_PARAM=
[ -z "$LAN" ] || LAN_PARAM="lan=http://$LAN:$WEB_PORT"

if [ "$mode" = live ]; then
  API_PORT=$(free_port) || fail "could not find a free port"
  API=http://127.0.0.1:$API_PORT
  # The README's command, from the project folder, so the keys in .env are found and the
  # travellers' sessions and memory are kept where adk keeps them by default (gilmate/.adk/, git-ignored).
  # With --phone-live it also listens on the network and allows the phone's copy of the page.
  PHONE_ORIGIN=$WEB
  if [ "$phone_live" = yes ]; then
    API_HOST=0.0.0.0
    PHONE_ORIGIN=http://$LAN:$WEB_PORT
  fi
  (
    cd "$REPO" && exec "$VENV/bin/adk" api_server --host "$API_HOST" --port "$API_PORT" \
      --allow_origins "$WEB" --allow_origins "http://localhost:$WEB_PORT" --allow_origins "$PHONE_ORIGIN" .
  ) >"$LOGS/api.log" 2>&1 &
  api_pid=$!
  say "Starting the page on port $WEB_PORT and the agent server on port $API_PORT ..."
  wait_for "$WEB/index.html" "$web_pid" "The page server" "$LOGS/web.log"
  wait_for "$API/list-apps" "$api_pid" "The agent server" "$LOGS/api.log"
  ADDRESS="$WEB/?api=$API&root=coordinator${LAN_PARAM:+&$LAN_PARAM}"
  say ""
  say "Gilmate is running on the live agents. Open:"
  say ""
  say "    $ADDRESS"
  say ""
  say "Starting was free. Using the page calls the model and may search the web, which costs money."
else
  say "Starting the page on port $WEB_PORT ..."
  wait_for "$WEB/index.html" "$web_pid" "The page server" "$LOGS/web.log"
  ADDRESS="$WEB/${LAN_PARAM:+?$LAN_PARAM}"
  say ""
  say "Gilmate is running on the saved run (no keys, no model, no search). Open:"
  say ""
  say "    $ADDRESS"
  say ""
fi
if [ "$phone" = yes ]; then
  say "For a phone on the same Wi-Fi: build a route, press the choice that opens it on your phone, and scan the code."
  say "The page folder is served to this network at http://$LAN:$WEB_PORT/ until you stop (static files only)."
  if [ "$mode" = live ] && [ "$phone_live" = yes ]; then
    say "The agent server listens on the network too (http://$LAN:$API_PORT): anyone on this network can send it turns, which costs money."
  elif [ "$mode" = live ]; then
    say "The agent server stays on this computer: \"Fine\" / \"Too far\" on the phone are kept on the phone (--phone-live sends them)."
  fi
  say ""
fi
say "Logs: $LOGS"
say "Press Ctrl-C to stop."

# Stay until Ctrl-C, or until one of the servers stops by itself.
while :; do
  if ! kill -0 "$web_pid" 2>/dev/null; then
    say "The page server stopped by itself. The end of its log:"; tail -n 20 "$LOGS/web.log"; exit 1
  fi
  if [ -n "$api_pid" ] && ! kill -0 "$api_pid" 2>/dev/null; then
    say "The agent server stopped by itself. The end of its log:"; tail -n 20 "$LOGS/api.log"; exit 1
  fi
  sleep 1
done
