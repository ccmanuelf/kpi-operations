import ast
import pathlib

FORBIDDEN_IMPORTS = ("sqlalchemy", "backend.database", "backend.orm", "backend.crud")
FORBIDDEN_CALLS = ("now", "today", "utcnow", "uuid4")

SEED_DIR = pathlib.Path(__file__).resolve().parents[2] / "seed"
ENGINE_MODULES = ("events.py", "scenarios.py", "profiles.py", "generator.py")


def _tree(name):
    return ast.parse((SEED_DIR / name).read_text())


def test_engine_modules_import_no_database_machinery():
    """S1a's whole premise is that the engine is provable without a database.
    An import here would silently make that false."""
    offenders = []
    for name in ENGINE_MODULES:
        for node in ast.walk(_tree(name)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                    offenders.append(f"{name}: {m}")
    assert offenders == []


def test_engine_modules_never_read_the_clock_or_generate_uuids():
    """Determinism is the contract: every varying value must derive from the
    seeded RNG and the supplied as_of, never from ambient state."""
    offenders = []
    for name in ENGINE_MODULES:
        for node in ast.walk(_tree(name)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_CALLS:
                    offenders.append(f"{name}: {node.func.attr}()")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    offenders.append(f"{name}: {node.func.id}()")
    assert offenders == []
