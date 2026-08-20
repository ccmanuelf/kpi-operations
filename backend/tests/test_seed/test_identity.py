import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from backend.seed.identity import IdMap, IntPkAllocator, UnknownEntity


def test_resolve_names_the_missing_entity_instead_of_raising_a_bare_keyerror():
    """A silent miss becomes a NULL foreign key thousands of rows later. The
    error has to say which table and which key, or a stream-ordering bug is
    unreadable. The message must render unwrapped, not double-quoted."""
    m = IdMap()
    m.assign("PRODUCTION_LINE", "DEMO-PIECE-LINE-01", 7)

    with pytest.raises(UnknownEntity) as exc:
        m.resolve("PRODUCTION_LINE", "DEMO-PIECE-LINE-99")

    rendered = str(exc.value)
    # Verify message is not double-quoted (KeyError default behavior).
    assert not rendered.startswith('"')
    # Verify both halves are named.
    assert "PRODUCTION_LINE" in rendered
    assert "DEMO-PIECE-LINE-99" in rendered


def test_assigning_the_same_key_twice_is_rejected():
    m = IdMap()
    m.assign("SHIFT", "S1", 1)

    with pytest.raises(ValueError):
        m.assign("SHIFT", "S1", 2)


def test_has_discriminates_assigned_and_unassigned_keys():
    """has() must return True for assigned keys, False for unassigned ones, and
    not raise on unknown tables."""
    m = IdMap()
    m.assign("PRODUCT", "SKU-001", 99)

    # Assigned key in known table returns True.
    assert m.has("PRODUCT", "SKU-001") is True
    # Unassigned key in known table returns False.
    assert m.has("PRODUCT", "SKU-999") is False
    # Unknown table returns False, does not raise.
    assert m.has("UNKNOWN_TABLE", "any_key") is False


def test_allocator_starts_above_the_existing_maximum():
    """EMPLOYEE has no tenant column, so its integers are shared with real
    clients on a production database. Starting at 1 would collide."""
    engine = create_engine("sqlite://")
    md = MetaData()
    t = Table("T", md, Column("id", Integer, primary_key=True), Column("name", String(10)))
    md.create_all(engine)  # schema-guard: allow — throwaway in-memory SQLite fixture

    with engine.begin() as conn:
        conn.execute(insert(t), [{"id": 41, "name": "existing"}])
        alloc = IntPkAllocator(conn, t)

        assert alloc.next() == 42
        assert alloc.next() == 43


def test_allocator_starts_at_one_on_an_empty_table():
    engine = create_engine("sqlite://")
    md = MetaData()
    t = Table("T", md, Column("id", Integer, primary_key=True))
    md.create_all(engine)  # schema-guard: allow — throwaway in-memory SQLite fixture

    with engine.begin() as conn:
        assert IntPkAllocator(conn, t).next() == 1
