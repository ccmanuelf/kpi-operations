"""S1c Task 3: the boot path seeds via backend.seed and can no longer drop
the database. See backend/bootstrap/lifecycle.py::_auto_seed_demo_data.
"""


def test_expected_clients_is_the_seeder_allowlist():
    """Derived, not literal. A hardcoded set that names different clients than
    the seeder produces makes every boot decide the demo is incomplete and
    re-seed forever -- and with the old destructive rebuild in front of it, that
    was an infinite data-loss loop."""
    import backend.bootstrap.lifecycle as lifecycle
    from backend.seed.cli import ALLOWLIST

    assert lifecycle._expected_clients() == set(ALLOWLIST)


def test_the_boot_path_cannot_reach_rebuild_schema():
    """The destructive path is gone by construction, not by configuration.

    Asserted against the AST, not the raw source: a substring check would also
    match COMMENTS, forbidding the explanatory note this removal deserves and
    training the next reader to delete the comment to make the test pass. This
    checks what actually executes -- no import of rebuild_schema, no call to it.
    """
    import ast
    import inspect
    import backend.bootstrap.lifecycle as lifecycle

    tree = ast.parse(inspect.getsource(lifecycle))
    imported = {
        alias.name.split(".")[-1] if alias.asname is None else alias.asname
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called = {ast.unparse(node.func).split(".")[-1] for node in ast.walk(tree) if isinstance(node, ast.Call)}

    assert "rebuild_schema" not in imported
    assert "rebuild_schema" not in called
