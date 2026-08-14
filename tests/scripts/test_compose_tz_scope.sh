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
  # Both YAML environment styles: list item (`- TZ=...`, what this file uses
  # throughout) and mapping (`TZ: ...`), optionally quoted. Matching only the
  # list form would let a mapping-style TZ through unseen.
  in_services && /^[[:space:]]*-[[:space:]]*["'"'"']?TZ["'"'"']?[=:]/ { print svc }
  in_services && /^[[:space:]]+["'"'"']?TZ["'"'"']?:[[:space:]]/       { print svc }
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

# No service may pull environment from a file: this guard reads the compose
# source, so a TZ smuggled in via env_file would be invisible to it. The stack
# uses inline `environment:` blocks throughout; if that ever changes, this
# guard must be reworked rather than quietly narrowed.
! grep -qE '^[[:space:]]+env_file:' "$COMPOSE"
assert "no service uses env_file (would hide TZ from this guard)" $?

# SCOPE, stated so nobody mistakes this for more than it is: the guard checks
# WHICH services may carry TZ, not WHAT zone resolves. The compose line is
# `TZ=${TZ:-UTC}`, so the value comes from .env at runtime, and .env is not in
# git. The zone written at provisioning time is pinned by
# tests/scripts/test_vm_bootstrap.sh; an ALREADY-provisioned host that predates
# that change keeps its old value silently, so a live host must be checked --
# and corrected -- by hand at deploy time. `docker exec kpi-backup date` is the
# one-command check: it must report CDT in summer and CST in winter, matching
# Brownsville/Matamoros local time, never a fixed CST year-round.

exit $failed
