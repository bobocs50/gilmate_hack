#!/bin/sh
# Run every free drill and stop with an error when one fails. No network, no key, no model.
#   scripts/drills.sh          uses the project's .venv when there is one, otherwise python3
here=$(cd "$(dirname "$0")/.." && pwd -P) || exit 1
py=$here/.venv/bin/python
[ -x "$py" ] || py=python3
failed=0
for drill in "$here"/tests/drill_*.py; do
  if out=$("$py" "$drill" 2>&1); then
    printf 'ok    %s\n' "$(basename "$drill")"
  else
    printf 'FAIL  %s\n' "$(basename "$drill")"
    printf '%s\n' "$out" | grep -v '^ok' | cut -c1-400
    failed=1
  fi
done
[ "$failed" -eq 0 ] && echo "all drills passed" || echo "DRILLS FAILED"
exit $failed
