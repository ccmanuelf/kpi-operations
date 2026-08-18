"""Event keys to database primary keys.

The stream identifies entities by stable string business keys; four master
tables (PRODUCTION_LINE, SHIFT, PRODUCT, EMPLOYEE) use autoincrement integer
PKs. Core bulk insert gives no PK round trip, so the materializer allocates
them here and resolves foreign keys through the map.
"""

from sqlalchemy import Connection, Table, func, select


class UnknownEntity(KeyError):
    """A foreign key referenced an entity the stream never created."""


class IdMap:
    def __init__(self) -> None:
        self._by_table: dict[str, dict[str, object]] = {}

    def assign(self, table: str, key: str, value: object) -> None:
        bucket = self._by_table.setdefault(table, {})
        if key in bucket:
            raise ValueError(f"{table}: key {key!r} already assigned to {bucket[key]!r}")
        bucket[key] = value

    def resolve(self, table: str, key: str) -> object:
        try:
            return self._by_table[table][key]
        except KeyError:
            # Bare KeyError surfaces thousands of rows later as a NULL FK or an
            # IntegrityError naming a column, not the ordering bug that caused
            # it. Name both halves.
            raise UnknownEntity(
                f"{table}: no primary key assigned for {key!r} -- the stream referenced "
                "it before the event that creates it, or that event was never emitted"
            ) from None

    def has(self, table: str, key: str) -> bool:
        return key in self._by_table.get(table, {})


class IntPkAllocator:
    """Contiguous integer PKs above the table's current maximum.

    Reads MAX(pk) inside the seeding transaction rather than using a fixed
    offset: EMPLOYEE carries no tenant column, so its integers are shared with
    every real client on a production database.
    """

    def __init__(self, conn: Connection, table: Table) -> None:
        pk = list(table.primary_key.columns)[0]
        self._next = int(conn.execute(select(func.coalesce(func.max(pk), 0))).scalar_one()) + 1

    def next(self) -> int:
        value = self._next
        self._next += 1
        return value
