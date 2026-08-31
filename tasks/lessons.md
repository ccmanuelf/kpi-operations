
## 2026-08-29 — A `language: system` hook runs whatever is first on PATH, not your toolchain

**Pattern:** `.pre-commit-config.yaml` declared `entry: python -m mypy backend` with
`language: system`, and a comment claiming it "matches CI and the local dev workflow
exactly". It did not. `python` resolved to `/opt/anaconda3/bin/python`, whose mypy reported
"No issues found" for a file the repo's pinned mypy 2.1.0 rejects outright. Every commit on
the branch showed `mypy (backend, whole-package)... Passed` while CI's `backend-tests`
failed on that same file — and because the branch had never run CI, nobody saw the
disagreement for 56 commits. The error itself was trivial (`set[str] | None` needs the None
case before `in`); the gate silently answering a different question was not.

**Rule:** A hook that names a bare executable (`python`, `mypy`, `flake8`, `node`) is
resolved against PATH at run time and is therefore a different tool per machine. Pin the
interpreter — `backend/.venv/bin/python` — and make a missing one FAIL rather than fall
back, because silent fallback is exactly how the divergence hides. When a gate and CI
disagree, do not assume the environment differs in some benign way: run CI's literal command
locally and compare exit codes, not output. And beware measuring a pipeline's exit status:
`cmd | grep ...; echo $?` reports grep's status, which made the first attempt here look like
mypy had passed.

## 2026-08-29 — `git checkout <file>` to undo a mutation destroys uncommitted work in that file

**Pattern:** While mutation-testing the fetch-failure guards I reverted one mutant with
`git checkout -- frontend/src/composables/useHoldGridForms.ts`. That file also held three
*uncommitted* edits from the same work session — a tightened return type and two refresh
guards — and the checkout took all of them back to HEAD along with the mutant. The damage
arrived disguised as a test result: the post-restore run still showed one assertion failure,
which read like a flaky test rather than a file I had just emptied. This exact trap is already
recorded twice in this project's memory and I still walked into it, because the other three
mutations in the same loop were reverted correctly from `cp` backups and the habit lapsed on
the fourth.

**Rule:** Never revert a mutation with git. Copy the file aside first (`cp f "$SCRATCH/f.orig"`)
and restore from that copy — the backup is scoped to exactly the file and moment you intend,
where `git checkout` is scoped to the last commit. Commit finished work *before* starting a
mutation loop so the blast radius is empty even if you slip. And when a "restored" run does not
return to the baseline number, suspect the restore before suspecting the test: a mutation loop
whose baseline and restored figures disagree has corrupted its own subject.

## 2026-08-10 — A guard whose fixtures avoid the failing case is not a guard
**Pattern:** PR #171 added a structural test asserting `/wip-aging/trend` agrees with the `/wip-aging` snapshot for the same date, and it passed. It passed because every fixture `hold_date` was at midnight. `date_diff_days` returns FRACTIONAL days, so a hold opened at 09:00 aged 44.625 on the trend line and 45 in the snapshot — the two surfaces disagreed on every hold with a time component, which in production is all of them. Midnight fixtures made the truncation being tested a no-op. A cross-model reviewer found it; the test could not.
**Rule:** After writing a guard, revert the fix and confirm the guard FAILS — an unverified guard is an assertion about a test, not about the code. Then check the fixture data actually exercises the failing case: for time-of-day bugs use non-zero times, for boundary bugs include the equality case (a test with no `resume_date == cutoff` row passes under both `>` and `>=`), for empty-table "it executes" tests remember `AVG` over zero rows is NULL however wrong the arithmetic is.

## 2026-08-10 — Portability gates that hand-copy a query shape go green while dead
**Pattern:** `test_mariadb_portability.py` proved the WIP-aging SQL ran on MariaDB by restating the route's query in the test. When #171 changed the real query (`ORDER BY date_diff_days` + `hold_status` filter → `_active_as_of` + `ORDER BY hold_date`), the copy kept passing while asserting SQL the application no longer builds. The check was green and proved nothing — same class as the reporting-wiring bug where unit tests asserted the broken paths.
**Rule:** A portability/integration gate must IMPORT the production expression, never restate it. Also confirm the job actually covers your change before trusting its green: the MariaDB job runs only `test_mariadb_portability.py`, so tests added elsewhere never execute against MariaDB no matter how green the badge looks. Watch fixture scope when adding seeded rows — `mariadb_schema` is `scope="module"`, so rows persist across tests in the file and any `assert rows == []` elsewhere becomes order-coupled.

## 2026-08-06 — Derived-metric honesty: rescaling an average-of-averages is not "the same formula"
**Pattern:** Cycle 3 PR-B tried to ship an "available-basis efficiency" on the dashboard by algebraically rescaling `avg_efficiency × (scheduled/available)`. The identity only holds when the base is a ratio of sums; the dashboard's figure is an unweighted average of per-entry percentages, so the rescaled number drifted 16 points in a routine two-entry scenario (Simpson-style), and the two "scheduled" sources (production crew-hours vs attendance rows) didn't even match.
**Rule:** A derived management metric must be computed as a ratio of sums from its own primary data, in one home, or not shipped at all. Never rescale an average-of-averages and label it as the underlying formula; never blend estimated/inferred components into a metric whose value is being "hard and auditable" (exclude + surface an `excluded_entries` count instead — inference chains that reverse-derive from prior efficiency numbers are circular). When a spec's literal wording is impossible at an endpoint, escalate the semantics decision instead of approximating silently.

## Run `black` before `git commit`, not via the hook

**Pattern:** Committed twice with a message written from a green test run; the
pre-commit `black` hook reformatted a file each time, which ABORTS the commit.
Both times the output began with `ok N files changed`, so it read as success —
but HEAD had not moved, and the next command (a `cross-review-mark`, a push)
then ran against the OLD commit. The second time it marked the review for the
previous SHA.

**Rule:** run `backend/.venv/bin/python -m black backend` (or stage after the
hook rewrites) BEFORE `git commit`. After any commit whose hook output contains
`files were modified by this hook`, verify with `git rev-parse --short HEAD`
before doing anything that depends on the commit existing.

**Generalised (third occurrence):** it is not only black. ANY failing
pre-commit hook aborts the commit — flake8 caught a duplicate import once and
the same thing happened: `ok N files changed` printed, HEAD had not moved, and
the subsequent `cross-review-mark` + `git push` both landed on the PREVIOUS
commit. Treat `git commit` as unverified until `git rev-parse --short HEAD`
shows a new sha. Run black AND flake8 locally first.
