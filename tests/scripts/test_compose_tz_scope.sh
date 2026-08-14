#!/usr/bin/env bash
# Guards the CLOCK INVARIANT documented in
# backend/calculations/wip_aging.py:active_as_of.
#
# HOLD_STATUS_TRANSITION.transitioned_at is stamped with datetime.utcnow(),
# while WIP-aging callers derive `as_of` from a server-local calendar date
# (date.today()). active_as_of compares that UTC column against a cutoff built
# from the local date, so the backend container MUST run UTC. If someone set TZ
# on the backend service -- an easy, well-meaning change for readable logs --
# a transition recorded after local evening would land on the wrong side of the
# cutoff and today's WIP-aging dashboard would show a stale status until local
# midnight. Nothing would error; the number would just be wrong.
#
# Only the backup sidecar may carry TZ: BACKUP_HOUR is interpreted in it, which
# is the entire reason the variable exists in this stack.
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
COMPOSE=docker-compose.prod.yml
failed=0

assert() { # assert <label> <status>
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; failed=1; fi
}

[ -f "$COMPOSE" ]; assert "$COMPOSE exists" $?

# Walk the file tracking the current top-level service, and collect every
# service whose environment block declares TZ. Top-level services are indented
# two spaces under `services:`; anything deeper belongs to the current one.
services_with_tz=$(awk '
  /^services:/ { in_services = 1; next }
  # Leave the services: block only on another TOP-LEVEL YAML KEY. Testing for
  # any column-0 line is wrong: this file carries column-0 `#` comments inside
  # service blocks (see the gunicorn worker note under `backend`), and treating
  # one as the end of the block silently truncated the walk after `backend`,
  # so every later service -- including `backup`, the only one that may set TZ
  # -- became invisible and the guard passed while checking nothing.
  in_services && /^[a-zA-Z_][a-zA-Z0-9_-]*:/ { in_services = 0 }
  in_services && /^  [a-zA-Z0-9_-]+:/ {
      svc = $1; sub(/:$/, "", svc); next
  }
  in_services && /^[[:space:]]*-[[:space:]]*TZ=/ { print svc }
' "$COMPOSE" | sort -u)

[ "$services_with_tz" = "backup" ]
assert "only the backup sidecar declares TZ (found: ${services_with_tz:-none})" $?

# Stated separately from the check above so a regression names the service that
# actually matters, rather than only reporting that the set changed.
! grep -q '^backend$' <<<"$services_with_tz"
assert "backend does not declare TZ (CLOCK INVARIANT: it must stay UTC)" $?

# The zone itself is pinned by tests/scripts/test_vm_bootstrap.sh; here we only
# assert the comment still steers readers away from the wrong-but-obvious one,
# since a Tamaulipas deployment reads America/Monterrey as the natural choice
# and it is an hour off local time for the whole DST half of the year.
grep -q 'America/Matamoros' "$COMPOSE"
assert "compose comment names the border DST zone" $?

exit $failed
