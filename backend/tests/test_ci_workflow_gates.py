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

#: The full-suite path. Coverage (and therefore backend/.coveragerc's
#: fail_under gate) is meaningful only when the whole pool is measured, so this
#: is the ONE pytest target allowed to run without --no-cov.
FULL_SUITE_TARGET = "tests/"


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


def _pytest_invocations(workflow: dict) -> list:
    """(job, step name, tokens) for every step that runs pytest.

    Walks `jobs.*.steps[*].run` and splits each run block by line, so a
    multi-line shell step is covered as thoroughly as a one-liner. Accepts
    both `pytest ...` and `python -m pytest ...`.
    """
    found = []
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            run = step.get("run")
            if not isinstance(run, str):
                continue
            for line in run.splitlines():
                tokens = _command_tokens(line)
                if tokens[:1] == ["pytest"]:
                    found.append((job_name, step.get("name"), tokens))
                elif tokens[:3] in (["python", "-m", "pytest"], ["python3", "-m", "pytest"]):
                    found.append((job_name, step.get("name"), tokens[2:]))
    return found


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
        if any(t.startswith("tests/") and t != FULL_SUITE_TARGET for t in tokens) and "--no-cov" not in tokens
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

    steps = sorted((job, name) for job, name, _ in _pytest_invocations(workflow))

    assert steps == [
        ("backend-tests", "Run tests with coverage"),
        ("mariadb-portability", "Run MariaDB portability tests"),
        ("mariadb-portability", "Seed suite on MariaDB"),
    ]
