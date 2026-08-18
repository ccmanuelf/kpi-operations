import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from backend.seed.identity import IdMap, IntPkAllocator, UnknownEntity


def test_resolve_names_the_missing_entity_instead_of_raising_a_bare_keyerror():
    """A silent miss becomes a NULL foreign key thousands of rows later. The
    error has to say which table and which key, or a stream-ordering bug is
    unreadable."""
    m = IdMap()
    m.assign("PRODUCTION_LINE", "DEMO-PIECE-LINE-01", 7)

    with pytest.raises(UnknownEntity) as exc:
        m.resolve("PRODUCTION_LINE", "DEMO-PIECE-LINE-99")

    assert "PRODUCTION_LINE" in str(exc.value)
    assert "DEMO-PIECE-LINE-99" in str(exc.value)


def test_assigning_the_same_key_twice_is_rejected():
    m = IdMap()
    m.assign("SHIFT", "S1", 1)

    with pytest.raises(ValueError):
        m.assign("SHIFT", "S1", 2)


def test_allocator_starts_above_the_existing_maximum():
    """EMPLOYEE has no tenant column, so its integers are shared with real
    clients on a production database. Starting at 1 would collide."""
    engine = create_engine("sqlite://")
    md = MetaData()
    t = Table("T", md, Column("id", Integer, primary_key=True), Column("name", String(10)))
    md.create_all(engine)

    with engine.begin() as conn:
        conn.execute(insert(t), [{"id": 41, "name": "existing"}])
        alloc = IntPkAllocator(conn, t)

        assert alloc.next() == 42
        assert alloc.next() == 43


def test_allocator_starts_at_one_on_an_empty_table():
    engine = create_engine("sqlite://")
    md = MetaData()
    t = Table("T", md, Column("id", Integer, primary_key=True))
    md.create_all(engine)

    with engine.begin() as conn:
        assert IntPkAllocator(conn, t).next() == 1
