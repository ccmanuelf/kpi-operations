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
# a live Connection by design; the materializer will consume it to allocate
# integer PKs and map event keys.
EXEMPTED_MODULE_PATHS = {"identity.py"}


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
    """
    all_modules = [p for p in SEED_DIR.rglob("*.py") if p.name != "__init__.py"]
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
    } <= names


def test_exemption_does_not_fail_open_to_subpackages(tmp_path):
    """Exemptions match by relative path, not basename. A module in a subpackage
    bearing the same name as an exempted file is NOT automatically exempted --
    the recursive glob invariant is preserved. This test temporarily plants a
    SQLAlchemy import in a subpackage and verifies the guard catches it."""
    # Create a temporary backend/seed structure.
    temp_seed = tmp_path / "seed"
    temp_seed.mkdir()
    (temp_seed / "__init__.py").touch()

    # Create a subpackage with a file named identity.py containing an import.
    subpkg = temp_seed / "subpkg"
    subpkg.mkdir()
    (subpkg / "__init__.py").touch()
    (subpkg / "identity.py").write_text("import sqlalchemy\n")

    # Temporarily replace SEED_DIR and re-run the glob.
    # We cannot directly patch SEED_DIR because it is evaluated at module load time,
    # so we work around by creating a local _engine_modules with the temp dir.
    def _temp_engine_modules():
        all_modules = [p for p in temp_seed.rglob("*.py") if p.name != "__init__.py"]
        return sorted(p for p in all_modules if p.relative_to(temp_seed).as_posix() not in EXEMPTED_MODULE_PATHS)

    # The subpackage module should be included (not exempted by basename).
    modules = _temp_engine_modules()
    found_subpkg = any(p.as_posix().endswith("subpkg/identity.py") for p in modules)
    assert found_subpkg, "Guard failed open: subpkg/identity.py was exempted by basename"

    # Now verify the guard catches the SQLAlchemy import.
    offenders = []
    for path in modules:
        for node in ast.walk(ast.parse(path.read_text())):
            for m in _imported_modules(node, ("temp", "seed")):
                if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                    offenders.append(f"{path.relative_to(temp_seed).as_posix()}: {m}")

    assert offenders, "Guard failed to catch SQLAlchemy import in subpkg/identity.py"
    assert "subpkg/identity.py" in offenders[0]
