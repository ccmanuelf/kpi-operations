"""Structural gates on the path-param registry.

Everything here is pure: no database, no HTTP. The behavioural half -- that
each SEEDED_ROW spec finds a row, that each BLOCKED spec's table is still
empty, and that the resulting URLs contain no braces -- lives in
`test_golden_master.py`, where a seeded database already exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import pytest

from backend.tests.contract.param_resolution import UnresolvableParam, blocked_shape, spec_key
from backend.tests.contract.param_specs import COMPOSITES, FAMILY_ROUTER, REGISTRY, Kind

GOLDEN = Path(__file__).parent / "golden" / "api_shapes.json"


def _golden_params() -> Dict[str, List[str]]:
    """param name -> the golden route keys that carry it."""
    found: Dict[str, List[str]] = {}
    for route in sorted(json.loads(GOLDEN.read_text(encoding="utf-8"))):
        for param in re.findall(r"\{(\w+)\}", route):
            found.setdefault(param, []).append(route)
    return found


def test_every_spec_carries_exactly_what_its_kind_requires():
    """One `sql`, one `literal` or one `reason`, never two, never none.

    A SEEDED_ROW with a `literal` set would silently prefer the hardcoded
    value and never touch the database -- which is precisely the drift this
    module exists to prevent -- and a BLOCKED spec with no reason is an
    undocumented gap, indistinguishable at the call site from a bug.
    """
    for key, spec in sorted(REGISTRY.items()):
        filled = tuple(sorted(name for name in ("sql", "literal", "reason") if getattr(spec, name)))
        expected = {
            Kind.SEEDED_ROW: ("sql",),
            Kind.LITERAL: ("literal",),
            Kind.BLOCKED: ("reason",),
        }[spec.kind]

        assert filled == expected, f"{key} ({spec.kind}) filled {filled}"
        assert spec.key == key, f"{key} disagrees with its own .key ({spec.key})"


def test_row_backed_specs_name_the_table_they_read():
    """SEEDED_ROW needs it so a seeder regression can name the table it
    expected rows in; BLOCKED needs it so the staleness gate has something to
    count. LITERAL must NOT have one -- the param is not a row at all, and a
    table there would invite someone to "fix" it into a query.
    """
    tables = {key: spec.table for key, spec in sorted(REGISTRY.items())}
    row_backed = {key for key, spec in REGISTRY.items() if spec.kind is not Kind.LITERAL}

    assert {key for key, table in tables.items() if table} == row_backed


def test_a_seeded_spec_reads_the_table_it_names():
    """`spec.table` must be the table `spec.sql` actually queries.

    Resolution never reads `.table` -- `Resolver.resolve` executes `spec.sql`
    and nothing else -- so for a SEEDED_ROW spec the label is decorative: it
    feeds error text and the staleness gate. Nothing tied it to the query,
    which meant a spec could name one table and read another and stay green.

    Reproduced before this test existed: pointing `catalog_id@hold-reason` at
    `SELECT catalog_id FROM HOLD_STATUS_CATALOG ... OFFSET 5` -- an id that
    exists in both catalogs, so it cannot 404 -- left the label untouched and
    the whole suite passed, 41 tests, golden file unmoved. That is a DELETE
    issued against hold reason #6 with an id taken from the status table: the
    exact wrong-entity resolution this harness exists to prevent, invisible
    because both catalog routes record `<non-json>`.

    Checks the FROM clause, not `spec.table in spec.sql`: a substring test
    passes on a mention in a trailing comment or in a column name. Exactly one
    FROM per spec is asserted too, so a JOIN -- which would make "the table
    this spec reads" ambiguous -- has to be a deliberate widening of this rule
    rather than a silent exemption.

    COMPOSITES have no `table` to compare against and are deliberately out of
    scope here; their only route's golden entry DISCRIMINATES (a bogus id
    404s), so a wrong table there fails `test_no_route_lost_a_field`.
    """
    from_clause = re.compile(r'\bFROM\s+"?(\w+)"?', re.IGNORECASE)
    reads = {
        key: from_clause.findall(spec.sql or "")
        for key, spec in sorted(REGISTRY.items())
        if spec.kind is Kind.SEEDED_ROW
    }
    mismatched = {key: tables for key, tables in reads.items() if tables != [REGISTRY[key].table]}

    assert mismatched == {}
    assert len(reads) == 16


def test_registry_keys_parse_as_param_or_param_at_family():
    """A key is either a bare param name or `param@family`. Anything else
    means `spec_key` can never produce it, so the spec is unreachable."""
    malformed = [key for key in REGISTRY if not re.fullmatch(r"\w+(@[\w-]+)?", key)]

    assert malformed == []


def test_registry_covers_every_golden_path_param_and_nothing_else():
    """Both directions, because both failures are silent.

    A param with no spec fails the capture at request time with an opaque
    error; a spec no golden route uses is dead weight that reads as coverage.
    `kpi_key` is deliberately absent from REGISTRY: it is half of a composite
    PK and is resolved by COMPOSITES, so it is counted from there.
    """
    from_golden = set(_golden_params())
    from_registry = {key.split("@")[0] for key in REGISTRY}
    from_composites = {param for _, params in COMPOSITES.values() for param in params}

    assert from_golden == from_registry | from_composites


def test_kpi_key_is_resolved_only_as_a_composite():
    """`kpi_key` is meaningless without its paired `client_id` -- they are a
    composite PK on KPI_THRESHOLD. Two independent queries could pick a
    `kpi_key` that does not exist for the chosen `client_id`, and the route
    would answer 404: indistinguishable from a bad id, and the golden master
    would record it as this route's answer.
    """
    assert "kpi_key" not in REGISTRY
    assert COMPOSITES["/api/kpi-thresholds/{client_id}/{kpi_key}"][1] == ("client_id", "kpi_key")


def test_catalog_id_resolves_to_a_different_table_per_route_family():
    """The single most dangerous entry in the resolution map.

    Same param name, same COLUMN name, two tables, both plain autoincrement
    ints starting at 1, both fully seeded, ranges overlapping. Feeding a
    status id to the reasons route cannot be caught by looking at the
    response -- both answer 204 with an empty body -- so it can only be
    prevented structurally, here.
    """
    statuses = spec_key("catalog_id", "/api/hold-catalogs/statuses/{catalog_id}")
    reasons = spec_key("catalog_id", "/api/hold-catalogs/reasons/{catalog_id}")

    assert statuses == "catalog_id@hold-status"
    assert reasons == "catalog_id@hold-reason"
    assert REGISTRY[statuses].table == "HOLD_STATUS_CATALOG"
    assert REGISTRY[reasons].table == "HOLD_REASON_CATALOG"


def test_a_collision_prone_param_on_an_unrouted_family_raises():
    """The guard that catches a NEW route family added later against an
    already-colliding name. Falling back to the bare param name would resolve
    `catalog_id` against whichever table happened to be registered first and
    return a wrong-entity 200 -- so an unrouted family must raise instead.
    """
    with pytest.raises(UnresolvableParam) as raised:
        spec_key("catalog_id", "/api/hold-catalogs/severities/{catalog_id}")

    assert raised.value.route == "/api/hold-catalogs/severities/{catalog_id}"
    assert "FAMILY_ROUTER" in raised.value.reason


def test_an_uncollided_param_keys_on_its_bare_name():
    """The other side of the same rule: only the four names that genuinely
    mean two entities are routed. Routing everything would turn every new
    route into a registry edit for no safety gain."""
    assert spec_key("work_order_id", "/api/work-orders/{work_order_id}/progress") == "work_order_id"
    assert "work_order_id" not in FAMILY_ROUTER


def test_a_blocked_shape_is_not_a_status_placeholder():
    """`<status:404>` says "the route answered, and this is what it said".
    For a blocked route nothing was ever sent, so recording a status would be
    a lie of exactly the kind this task exists to remove -- and it would be
    indistinguishable from the literal-brace 404s it replaces.
    """
    assert blocked_shape("job_id") == ["<blocked:job_id>"]
