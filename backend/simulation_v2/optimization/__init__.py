"""
Prescriptive optimization layer for SimPy V2.

Pairs MiniZinc deterministic optimization with SimPy stochastic simulation
following the patterns described in `memory/simpy-enhancement-plan.md`:

  - Pattern 1: operator allocation       (MZ optimizes → SimPy validates)
  - Pattern 2: bottleneck rebalancing    (SimPy detects → MZ solves)
  - Pattern 3: product sequencing        (MZ orders → SimPy simulates)
  - Pattern 4: planning vs. execution    (MZ for week/month, SimPy for day)

Models live in `*.mzn` files alongside their Python service wrappers.
The shared subprocess plumbing is in `minizinc_runner.py`.
"""

from .minizinc_runner import (
    MiniZincNotAvailableError,
    MiniZincSolveError,
    MiniZincResult,
    is_minizinc_available,
    run_minizinc,
)

__all__ = [
    "MiniZincNotAvailableError",
    "MiniZincSolveError",
    "MiniZincResult",
    "is_minizinc_available",
    "run_minizinc",
]
