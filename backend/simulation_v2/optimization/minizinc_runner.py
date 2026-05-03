"""
Subprocess wrapper for the MiniZinc CLI.

The Pattern 1+ optimization services build a `.dzn` data file from a
SimulationConfig, point MiniZinc at the corresponding `.mzn` model,
solve, and parse the result. This module owns the bits that DON'T
depend on which pattern is being solved:

  - locating the MZ binary,
  - spawning the subprocess with sane timeout + flag defaults,
  - turning errors into Python exceptions,
  - parsing the `output [...]` block when the model emits structured
    JSON (the convention this codebase uses).

The model files themselves are responsible for emitting JSON via
`output [show_json(...)]` so we can decode the result without a custom
parser per pattern.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Errors
# =============================================================================


class MiniZincNotAvailableError(RuntimeError):
    """Raised when the MiniZinc CLI is not installed on this host."""


class MiniZincSolveError(RuntimeError):
    """Raised when MiniZinc returns a non-zero exit code or unparseable output."""


# =============================================================================
# Result container
# =============================================================================


@dataclass
class MiniZincResult:
    """
    Structured solver output.

    `solution` is the JSON object the model emitted on the first solution
    line. `status` is the trimmed status line MZ prints between solutions
    (e.g. `==========`, `=====UNKNOWN=====`, `=====UNSATISFIABLE=====`).
    `is_optimal` reflects MZ's `=====OPTIMAL=====` separator.
    """

    solution: Optional[Dict[str, Any]] = None
    is_satisfied: bool = False
    is_optimal: bool = False
    status_line: str = ""
    raw_stdout: str = ""
    raw_stderr: str = ""
    solve_time_seconds: Optional[float] = None
    extra_solutions: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Public API
# =============================================================================


def is_minizinc_available() -> bool:
    """Cheap precheck — does the MZ CLI resolve on PATH?"""
    return shutil.which("minizinc") is not None or _candidate_macos_path() is not None


def run_minizinc(
    model_path: Path,
    data: Dict[str, Any],
    *,
    solver: str = "gecode",
    timeout_seconds: int = 30,
    extra_args: Optional[List[str]] = None,
) -> MiniZincResult:
    """
    Solve `model_path` against the given `data` dict.

    The data dict is converted to a temp `.dzn` file (one `name = value;`
    line per key). Strings/ints/floats/bool/list-of-int/list-of-list-of-int
    are supported — anything else raises a TypeError.

    The model is expected to emit a JSON-shaped solution via
    `output [show_json(...)]` so we can `json.loads` the line. If the
    model emits multiple solutions (without `--all-solutions`), only the
    last one before the `==========` separator counts as the optimal.
    """
    binary = _resolve_minizinc()

    dzn_path = _write_dzn(data, model_path.parent)

    # Note: we deliberately do NOT pass `--output-mode json`. That flag
    # tells MiniZinc to dump every model variable as multi-line JSON,
    # which overrides the model's custom `output [...]` block. Our
    # convention is to let the model emit a single one-line JSON object
    # via its own `output` block; the parser below picks that up.
    cmd = [
        binary,
        "--solver",
        solver,
        "--time-limit",
        str(timeout_seconds * 1000),  # MZ takes ms
        str(model_path),
        str(dzn_path),
    ]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Running MiniZinc: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 5,  # belt-and-suspenders over MZ's own --time-limit
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise MiniZincSolveError(f"MiniZinc timed out after {timeout_seconds}s") from e
    finally:
        try:
            dzn_path.unlink()
        except OSError:
            pass

    if proc.returncode != 0:
        raise MiniZincSolveError(
            f"MiniZinc exited {proc.returncode}: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )

    return _parse_output(proc.stdout, proc.stderr)


# =============================================================================
# Internal helpers
# =============================================================================


def _candidate_macos_path() -> Optional[str]:
    """Default MiniZinc IDE install path on macOS dev machines."""
    candidate = "/Applications/MiniZincIDE.app/Contents/Resources/minizinc"
    return candidate if os.path.isfile(candidate) and os.access(candidate, os.X_OK) else None


def _resolve_minizinc() -> str:
    """Find the MZ binary or raise a clear error."""
    on_path = shutil.which("minizinc")
    if on_path:
        return on_path
    macos = _candidate_macos_path()
    if macos:
        return macos
    raise MiniZincNotAvailableError(
        "MiniZinc binary not found on PATH or in /Applications/MiniZincIDE.app — "
        "install via `apt install minizinc` (Linux) or download the IDE bundle (macOS)."
    )


def _format_dzn_value(value: Any) -> str:
    """Format a Python value as a MiniZinc data-file literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value!r}"
    if isinstance(value, str):
        # MZ string literal — use double quotes, escape internal quotes/backslashes.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        if not value:
            return "[]"
        if isinstance(value[0], list):
            # 2D array → MZ matrix syntax: [| 1, 2, 3 | 4, 5, 6 |]
            rows = ["| " + ", ".join(_format_dzn_value(c) for c in r) for r in value]
            return "[" + " ".join(rows) + " |]"
        return "[" + ", ".join(_format_dzn_value(v) for v in value) + "]"
    raise TypeError(f"Unsupported MZ data value type: {type(value).__name__}")


def _write_dzn(data: Dict[str, Any], directory: Path) -> Path:
    """Write `data` to a temp .dzn file in the given directory; return the path."""
    import tempfile

    fd, name = tempfile.mkstemp(suffix=".dzn", dir=str(directory))
    try:
        with os.fdopen(fd, "w") as fh:
            for key, value in data.items():
                fh.write(f"{key} = {_format_dzn_value(value)};\n")
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
    return Path(name)


# Pre-compiled pattern for JSON-shaped solution lines emitted via `show_json`.
_JSON_LINE_RE = re.compile(r"^\s*\{.*\}\s*$")


def _parse_output(stdout: str, stderr: str) -> MiniZincResult:
    """
    Walk MiniZinc's stdout looking for JSON solutions and status separators.

    Convention: models emit one or more lines of `{ "key": value, ... }`
    via `show_json`, separated by `----------` after each solution. The
    last separator is `==========` (search complete) or
    `=====OPTIMAL=====` (proven optimal). Errors land on stderr or in
    `=====UNSATISFIABLE=====` / `=====UNKNOWN=====`.
    """
    result = MiniZincResult(raw_stdout=stdout, raw_stderr=stderr)
    solutions: List[Dict[str, Any]] = []

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped == "==========":
            # `==========` after one or more solutions means search
            # complete; for `solve minimize/maximize` problems the last
            # solution IS the optimal one (Gecode in particular emits
            # this rather than `=====OPTIMAL=====`).
            result.status_line = stripped
            result.is_satisfied = bool(solutions)
            result.is_optimal = bool(solutions)
            continue
        if stripped == "=====OPTIMAL=====":
            result.status_line = stripped
            result.is_satisfied = True
            result.is_optimal = True
            continue
        if stripped == "=====UNSATISFIABLE=====":
            result.status_line = stripped
            result.is_satisfied = False
            continue
        if stripped == "=====UNKNOWN=====":
            result.status_line = stripped
            continue
        if stripped == "----------":
            # solution-separator marker; collected via the line(s) before it.
            continue

        # Try to parse the line as JSON; ignore non-JSON noise.
        if _JSON_LINE_RE.match(stripped):
            try:
                solutions.append(json.loads(stripped))
            except json.JSONDecodeError:
                logger.debug("MZ line not valid JSON, skipped: %r", stripped)

    if solutions:
        result.solution = solutions[-1]
        result.extra_solutions = solutions[:-1]
        if not result.status_line:
            # No explicit separator (rare) — assume satisfied.
            result.is_satisfied = True

    return result
