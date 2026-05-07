#!/usr/bin/env bash
#
# check-skipped-tests.sh
#
# Fails CI if any frontend e2e spec contains a `test.describe.skip(`
# or `test.skip(` call without a justifying tag.
#
# Acceptable justifications (one of):
#   1. Title contains `[SKIPPED — ...]` — the convention from the
#      Phase A.13 closeout. Tag must reference a tracker phase
#      (e.g. `Phase B.7`) or a GitHub issue (`#NNN`).
#   2. A `// FIXME(YYYY-MM-DD)` comment on the line above the skip
#      with a target re-enable date.
#
# This guards against the failure mode that triggered Phase B.7:
# the entry-interface migration shipped without updating e2e specs,
# and the obsoleted tests were silently `test.describe.skip`'d as a
# stopgap. The guard prevents a future migration from doing the
# same — every skip must declare why and when it'll be re-enabled.

set -e

# Self-locate so the script works whether invoked from the project
# root (`bash scripts/check-skipped-tests.sh`) or from `frontend/`
# (`bash ../scripts/check-skipped-tests.sh` — the CI invocation).
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_DIR="${PROJECT_ROOT}/frontend/e2e"
EXIT_CODE=0
ORPHAN_SKIPS=()

# Find every `.skip(` call we care about. We DON'T flag the
# conditional/runtime skip pattern `test.skip(condition, reason)`
# (Playwright API for browser/env gating) because the reason string
# is the justification. We DO flag:
#   - test.describe.skip(...)   — file/block-level skip
#   - test.skip()               — bare in-test skip with no condition
# The line-immediately-above check still applies for FIXME comments.
while IFS= read -r match; do
    file="${match%%:*}"
    rest="${match#*:}"
    line_num="${rest%%:*}"

    skip_line=$(sed -n "${line_num}p" "$file")
    # Scan up to 8 lines before the skip for a FIXME — multi-line
    # comment blocks are common (the FIXME header + 2-3 wrapped
    # description lines + the skipped test).
    start_line=$((line_num - 8))
    [[ $start_line -lt 1 ]] && start_line=1
    prev_block=$(sed -n "${start_line},$((line_num - 1))p" "$file")

    # Skip false positives: `test.skip(<condition>, <reason>)` is
    # the Playwright runtime-skip API; the reason argument IS the
    # justification, not a smell.
    if echo "$skip_line" | grep -qE 'test\.skip\([^)]*,\s*['\''"\`]'; then
        continue
    fi

    has_skipped_tag=$(echo "$skip_line" | grep -E '\[SKIPPED' || true)
    has_phase_ref=$(echo "$skip_line" | grep -E 'Phase [A-Z]\.[0-9]+|#[0-9]+' || true)
    has_fixme=$(echo "$prev_block" | grep -E 'FIXME\(20[0-9]{2}-[0-9]{2}-[0-9]{2}\)|FIXME: ' || true)

    if [[ -z "$has_skipped_tag" && -z "$has_fixme" ]]; then
        ORPHAN_SKIPS+=("${file}:${line_num}: ${skip_line}")
        EXIT_CODE=1
    elif [[ -n "$has_skipped_tag" && -z "$has_phase_ref" ]]; then
        ORPHAN_SKIPS+=("${file}:${line_num}: SKIPPED tag missing Phase/issue ref: ${skip_line}")
        EXIT_CODE=1
    fi
done < <(grep -nE '(test\.describe\.skip|test\.skip)\s*\(' "$SPEC_DIR"/*.spec.ts || true)

if [[ ${#ORPHAN_SKIPS[@]} -gt 0 ]]; then
    echo "ERROR: Found $(( ${#ORPHAN_SKIPS[@]} )) skipped test(s) without a tracking justification."
    echo
    echo "Per docs/CONTRIBUTING.md and docs/standards/entry-ui-standard.md, every"
    echo "test.describe.skip(...) or test.skip(...) call MUST include either:"
    echo "  • A '[SKIPPED — ...]' tag in the title with a Phase reference"
    echo "    (e.g., 'Phase B.7') or a GitHub issue link (#123)."
    echo "  • A '// FIXME(YYYY-MM-DD): ...' comment on the line above with a"
    echo "    target re-enable date."
    echo
    echo "Offending lines:"
    for s in "${ORPHAN_SKIPS[@]}"; do
        echo "  ${s}"
    done
    exit 1
fi

echo "OK: all $(grep -cE '(test\.describe\.skip|test\.skip)\s*\(' "$SPEC_DIR"/*.spec.ts | awk -F: '{sum+=$2} END {print sum+0}') skipped tests have tracking justifications."
exit 0
