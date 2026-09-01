import ast
import pathlib

FORBIDDEN_IMPORTS = ("sqlalchemy", "backend.database", "backend.orm", "backend.crud")

# Split by call shape. `time` belongs to the ATTRIBUTE set only: `time.time()`
# is a clock read, but the bare name `time(6, 0)` is datetime.time and is how
# the generator builds every instant it stamps.
FORBIDDEN_ATTR_CALLS = ("now", "today", "utcnow", "uuid4", "time", "monotonic", "perf_counter")
FORBIDDEN_NAME_CALLS = ("now", "today", "utcnow", "uuid4")

# `random.Random(seed)` is the ONLY sanctioned use of the random module: it
# builds the per-run seeded instance every varying value derives from. Any
# other `random.<x>()` is the process-wide generator, which is ambient state
# and would break determinism.
ALLOWED_RANDOM_NAMES = ("Random",)

SEED_DIR = pathlib.Path(__file__).resolve().parents[2] / "seed"
# The engine's package path, used to resolve relative imports: `from ..orm
# import x` inside backend/seed resolves to backend.orm.
SEED_PACKAGE = ("backend", "seed")

# Modules exempt from purity checks because they intentionally interface with
# the database layer. These are matched by relative path from SEED_DIR to
# preserve the recursive-glob invariant: a module in a subpackage is still
# caught, so only legitimate exemptions reach this set. identity.py talks to
# a live Connection by design; the materializer consumes it to allocate
# integer PKs and map event keys. materialize.py itself talks to the database
# by design too -- it takes a live Connection, executes Core bulk inserts
# against it, and derives INSERT_ORDER from Base.metadata -- so it needs the
# same exemption identity.py has. writers_master.py needs it for the same
# reason again: it takes IntPkAllocator instances (which hold a live
# Connection), imports Base.metadata to build them, and turns master-data
# events into Core bulk-insert rows -- the write side of the same boundary
# materialize.py sits on. writers_operations.py is the operations-band half
# of that same write side: it imports backend.orm.work_order for
# WorkOrderStatus and turns operational events into Core bulk-insert rows.
# cli.py is the production entry point: it opens a real Engine/Connection,
# issues Core deletes for --reset, and its --as-of default is deliberately
# date.today() (the run must anchor to the actual run date in production) --
# the one sanctioned date.today() outside a test, at the CLI boundary rather
# than inside the seeding path itself.
EXEMPTED_MODULE_PATHS = {
    "identity.py",
    "materialize.py",
    "writers_master.py",
    "writers_operations.py",
    # Same write layer as the two writers above: it maps capacity events to
    # rows and needs `Connection` to build its PK allocators. The generation
    # side of the capacity module, emitters_capacity.py, is NOT exempt and
    # stays provable without a database.
    "writers_capacity.py",
    "cli.py",
}


def _engine_modules():
    """Globbed recursively, not hardcoded and not shallow. The previous
    4-tuple gave any NEW module under backend/seed zero coverage; a
    non-recursive glob repeated the same hole one level down -- a module
    dropped into a subpackage (e.g. backend/seed/subpkg/evil.py) carrying a DB
    import, a clock read and module-level randomness passed every guard
    clean, because none of them ever looked past the top level.

    ALLOWLIST: Modules in EXEMPTED_MODULE_PATHS are exempt from purity checks
    because they intentionally talk to the database. Exemptions match by
    relative path (not basename) to preserve the recursive-glob invariant: a
    module in a subpackage is still caught. When adding a module to
    EXEMPTED_MODULE_PATHS, add a comment saying why -- do not weaken the
    checks themselves, and do not go back to an opt-in list.

    `__init__.py` IS INCLUDED. The previous unconditional
    `p.name != "__init__.py"` filter was the last hole of exactly the shape
    the recursive glob closed one level up: backend/seed/__init__.py is in
    neither EXEMPTED_MODULE_PATHS nor test_seed_gates.CLOCK_EXEMPT/WRITE_LAYER,
    so it was covered by NOTHING -- the only file in the package with no guard
    on it at all. It is 0 bytes today, which is the cheapest possible moment
    to bring it under one: a DIRECT database import or clock read there was
    previously caught by nothing at all.

    Be precise about what that does and does not buy, because an earlier
    version of this paragraph claimed more than the guard delivers. The import
    check is PER-FILE and literal-prefix (see FORBIDDEN_IMPORTS); it does not
    follow the import graph. So a convenience re-export -- `from
    backend.seed.cli import seed` -- is NOT caught: `backend.seed.cli` matches
    no forbidden prefix, and the transitive backend.orm it drags in is
    invisible here. What IS caught is `from backend.orm import ...` or
    `date.today()` written directly in this file. Empty subpackage __init__
    files cost nothing to scan.
    """
    all_modules = list(SEED_DIR.rglob("*.py"))
    return sorted(p for p in all_modules if p.relative_to(SEED_DIR).as_posix() not in EXEMPTED_MODULE_PATHS)


def _imported_modules(node, module_path):
    """Every module name an import node pulls in, with relative imports
    resolved to absolute -- including names imported FROM a package, not just
    the package path itself.

    `from ..orm import work_order` has ImportFrom.module == "orm" and level 2,
    so a plain prefix match against "backend.orm" finds nothing -- a relative
    database import is a violation that nothing else on the branch would
    surface. Resolving the base module handles that case, but the base alone
    still misses `from backend import orm` (module == "backend", the forbidden
    package arrives as a NAME in node.names) and `from .. import orm` (same
    shape, relative). Joining each imported name onto the resolved base closes
    both: the prefix check then sees "backend.orm" either way.
    """
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    if not node.level:
        base = node.module or ""
    else:
        # level 1 == this package, level 2 == its parent, and so on.
        base = ".".join(module_path[: len(module_path) - (node.level - 1)])
        if node.module:
            base = f"{base}.{node.module}" if base else node.module
    modules = [base] if base else []
    modules += [f"{base}.{a.name}" if base else a.name for a in node.names]
    return modules


def test_engine_modules_import_no_database_machinery():
    """S1a's whole premise is that the engine is provable without a database.
    An import here would silently make that false."""
    offenders = []
    for path in _engine_modules():
        for node in ast.walk(ast.parse(path.read_text())):
            for m in _imported_modules(node, SEED_PACKAGE):
                if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                    offenders.append(f"{path.name}: {m}")
    assert offenders == []


def test_engine_modules_never_read_the_clock_or_generate_uuids():
    """Determinism is the contract: every varying value must derive from the
    seeded RNG and the supplied as_of, never from ambient state."""
    offenders = []
    for path in _engine_modules():
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_ATTR_CALLS:
                offenders.append(f"{path.name}: .{node.func.attr}()")
            elif isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAME_CALLS:
                offenders.append(f"{path.name}: {node.func.id}()")
    assert offenders == []


def test_engine_modules_never_use_the_module_level_rng():
    """The plan forbids module-level randomness, but nothing checked it: a
    bare `random.randint(1, 5)` draws from the process-wide generator, which
    is seeded from ambient entropy and would make two runs with identical
    inputs diverge. Only random.Random(seed) is allowed through."""
    offenders = []
    for path in _engine_modules():
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "random"
                and node.func.attr not in ALLOWED_RANDOM_NAMES
            ):
                offenders.append(f"{path.name}: random.{node.func.attr}()")
            # `from random import randint` smuggles the same generator in
            # under a bare name, which the call check above cannot see.
            if isinstance(node, ast.ImportFrom) and not node.level and node.module == "random":
                offenders += [
                    f"{path.name}: from random import {a.name}"
                    for a in node.names
                    if a.name not in ALLOWED_RANDOM_NAMES
                ]
    assert offenders == []


def test_the_guard_actually_covers_every_engine_module():
    """The check above globs; assert the glob is non-empty and reaches the
    modules that matter, so a rename cannot silently empty it."""
    names = {p.name for p in _engine_modules()}
    assert {
        "events.py",
        "scenarios.py",
        "profiles.py",
        "generator.py",
        # The generator's split (I4): a module that carries emission logic out
        # of generator.py must be named here too, or a future rename could
        # quietly drop the biggest source files from the guard while the
        # subset assertion above stayed green on the four originals.
        "narrative.py",
        "emitters_master.py",
        "emitters_operations.py",
        # The package __init__, named so it cannot fall back out of the glob.
        # It was covered by no guard at all until it was named here.
        "__init__.py",
    } <= names


def test_exemption_does_not_fail_open_to_subpackages(tmp_path, monkeypatch):
    """Exemptions match by relative path, not basename. A module in a subpackage
    bearing the same name as an exempted file is NOT automatically exempted --
    the recursive glob invariant is preserved. This test drives the REAL
    _engine_modules() against a temporary directory with a subpackage."""
    import sys

    # Create a temporary backend/seed structure.
    temp_seed = tmp_path / "seed"
    temp_seed.mkdir()
    (temp_seed / "__init__.py").touch()

    # Create a subpackage with a probe file named identity.py.
    subpkg = temp_seed / "subpkg"
    subpkg.mkdir()
    (subpkg / "__init__.py").touch()
    (subpkg / "identity.py").write_text("# probe file\n")

    # Patch SEED_DIR in this module's namespace. Get the module from sys.modules
    # to ensure we patch the right namespace that _engine_modules() will read from.
    this_module = sys.modules[__name__]
    monkeypatch.setattr(this_module, "SEED_DIR", temp_seed)

    # Call the real _engine_modules() with the patched SEED_DIR.
    modules = _engine_modules()

    # The subpackage module MUST be included. If exemptions matched by basename,
    # subpkg/identity.py would be wrongly excluded.
    relative_paths = {p.relative_to(temp_seed).as_posix() for p in modules}
    assert (
        "subpkg/identity.py" in relative_paths
    ), f"Guard failed open: subpkg/identity.py was exempted by basename. Modules seen: {relative_paths}"
