"""Gates on .github/workflows/ci.yml itself.

The suite already guards a great deal of production behaviour and nothing at
all about the workflow that runs it. `--no-cov` was deleted from the seed-suite
step once already; put back, the seed suite still reported 151 passed and every
other suite was byte-identical, because
`grep -rn -e workflows -e ci.yml -e no-cov -e fail_under backend/tests tests`
matched only docstrings. This file closes that seam.

PyYAML is already installed by both hash-pinned locks (pyyaml==6.0.3, pulled in
by bandit on the dev side), so no dependency is added here. If it ever stops
being installed, this module fails to import -- a collection error, loud, not a
silent pass.
"""

import pathlib

# PyYAML ships no type stubs and types-PyYAML is not in either lock, so mypy
# reports import-untyped (ignore_missing_imports does not cover an INSTALLED
# package without stubs). warn_unused_ignores is on, so this comment cannot
# outlive the reason for it.
import yaml  # type: ignore[import-untyped]

CI_WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

#: The full-suite target list. Coverage (and therefore backend/.coveragerc's
#: fail_under gate) is meaningful only when the whole pool is measured, so this
#: is the ONE target list allowed to run without --no-cov.
#:
#: A TUPLE compared for EQUALITY, not a name membership-tested with
#: str.startswith. The membership form -- `any(t.startswith("tests/") and t !=
#: FULL_SUITE_TARGET for t in tokens)` -- was defeated by two edits an
#: engineer makes without thinking twice, both of which left the suite green:
#: writing the same path as `./tests/test_seed/` (no token then starts with
#: "tests/"), and wrapping a long command over two lines with a backslash
#: (line 1 tokenises to ["pytest", "\"] and line 2 never begins with pytest).
#: Asking "does this step target the full suite?" instead of "does any token
#: look narrow?" is closed by construction: anything that is not exactly the
#: full suite needs --no-cov, whatever it is spelled like.
FULL_SUITE_TARGETS = ("tests/",)


def _command_tokens(line: str) -> list:
    """Tokens of one shell line with leading VAR=value assignments dropped, or
    [] for a blank or comment line.

    Comment lines matter: the junit-parsing step at ci.yml:319 embeds a Python
    heredoc whose comment reads "# pytest emits either a bare <testsuite>...",
    and a naive substring search counts that as a fourth pytest invocation.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return []
    tokens = stripped.split()
    index = 0
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-"):
        index += 1
    return tokens[index:]


def _shell_commands(run: str) -> list:
    """One entry per COMMAND in a run block, with backslash continuations
    joined back together first.

    Splitting a `run:` block on PHYSICAL lines is what the previous version
    did, and wrapping a long command is routine:

        run: |
          pytest \\
            tests/test_seed/ -v --tb=short

    Line 1 tokenises to ["pytest", "\\"] -- a pytest invocation with no target
    and no --no-cov, which the old narrowness test skipped because no token
    started with "tests/" -- and line 2 never begins with `pytest`, so the
    step vanished from the walk entirely. Measured: 2 passed, exit 0, with the
    seed step's --no-cov effectively unguarded.
    """
    commands, buffer = [], ""
    for line in run.splitlines():
        stripped = line.strip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1].rstrip() + " "
            continue
        commands.append(buffer + stripped)
        buffer = ""
    if buffer:
        commands.append(buffer)
    return commands


def _pytest_invocations(workflow: dict) -> list:
    """(job, step name, tokens) for every step that runs pytest.

    Walks `jobs.*.steps[*].run` and splits each run block into commands, so a
    multi-line shell step -- wrapped or not -- is covered as thoroughly as a
    one-liner. Accepts both `pytest ...` and `python -m pytest ...`.
    """
    found = []
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            run = step.get("run")
            if not isinstance(run, str):
                continue
            for command in _shell_commands(run):
                tokens = _command_tokens(command)
                if tokens[:1] == ["pytest"]:
                    found.append((job_name, step.get("name"), tokens))
                elif tokens[:3] in (["python", "-m", "pytest"], ["python3", "-m", "pytest"]):
                    found.append((job_name, step.get("name"), tokens[2:]))
    return found


def _pytest_targets(tokens: list) -> tuple:
    """The positional targets of one pytest invocation, `./` normalised away.

    `./tests/test_seed/` and `tests/test_seed/` name the same directory and
    pytest treats them identically; only a string check could tell them apart,
    which is exactly the bug. Options are dropped by their leading `-`;
    ci.yml uses only the `--opt=value` form, so no option consumes a following
    token. A STATED LIMITATION: an option written as `-k expr` would leave
    `expr` looking like a target, which fails the gate LOUDLY (the step is
    then not "exactly the full suite") rather than silently -- the safe
    direction for a guard to be wrong in.
    """
    targets = [t for t in tokens[1:] if not t.startswith("-")]
    return tuple(t[2:] if t.startswith("./") else t for t in targets)


def test_every_narrowed_pytest_step_in_ci_disables_coverage():
    """A pytest run narrower than the full suite must pass --no-cov.

    Coverage is configured globally (`addopts` in the root pyproject.toml plus
    backend/.coveragerc's `fail_under = 75`), so a scoped run measures the
    whole pool while exercising a fraction of it, lands far under the
    threshold, and exits 1 -- a PASSING run reported as a CI failure. That is
    what `--no-cov` on ci.yml:352 is for, and what nothing could notice being
    deleted again.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())

    offenders = [
        f"{job}/{name}: {' '.join(tokens)}"
        for job, name, tokens in _pytest_invocations(workflow)
        if _pytest_targets(tokens) != FULL_SUITE_TARGETS and "--no-cov" not in tokens
    ]

    assert offenders == []


def test_the_ci_workflow_parser_finds_every_pytest_step():
    """The anti-vacuity control, and the entire point of it.

    A parser that silently finds nothing is exactly how this class of guard
    dies: rename `jobs`, restructure a step, switch a `run:` to a composite
    action, and the walk above returns an empty list and reports green forever.
    So the three known invocations are pinned by name. A step legitimately
    added or removed updates this list deliberately.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())

    steps = sorted(
        (job, name, _pytest_targets(tokens), "--no-cov" in tokens)
        for job, name, tokens in _pytest_invocations(workflow)
    )

    assert steps == [
        ("backend-tests", "Run tests with coverage", ("tests/",), False),
        ("mariadb-portability", "Run MariaDB portability tests", ("tests/test_mariadb_portability.py",), True),
        ("mariadb-portability", "Seed suite on MariaDB", ("tests/test_seed/",), True),
    ]


def test_the_seed_suite_step_still_points_at_the_live_mariadb_service():
    """The other half of the SEED_TEST_DATABASE_URL defence, and the half
    nothing could see.

    conftest.resolve_seed_test_url hardened SET-BUT-EMPTY into a hard failure,
    but UNSET remains a deliberate silent SQLite fallback (the developer-laptop
    path), and both tests pinning that behaviour set or delete the variable
    themselves via monkeypatch -- so neither is structurally capable of
    observing whether CI still sets it at all. Deleting the two lines of
    step-level `env:` at ci.yml:350-351 moves this job back into the UNSET
    partition and restores wave 1's exact failure: "Seed suite on MariaDB"
    passes, green, with no MariaDB anywhere near it.

    EXACT EQUALITY on the whole mapping, not membership: an added second key
    is a change to what this step runs against and should be a deliberate,
    reviewable edit. The step NAME is not pinned here on purpose -- the
    anti-vacuity control above already pins it, so a rename fails loudly there
    rather than turning this lookup into a silent no-match.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    steps = workflow["jobs"]["mariadb-portability"]["steps"]
    step = next(s for s in steps if s.get("name") == "Seed suite on MariaDB")

    assert step.get("env") == {"SEED_TEST_DATABASE_URL": "${{ env.DATABASE_URL }}"}
