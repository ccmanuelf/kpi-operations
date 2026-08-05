"""ATTENDANCE_HOUR_ALLOCATION — intra-day hour ledger child of ATTENDANCE_ENTRY.

Replace-on-write: the API accepts an entry's full allocation list and swaps it
wholesale (no per-row PATCH surface). Cycle 3 PR-A.
"""

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from backend.database import Base


class AttendanceHourAllocation(Base):
    __tablename__ = "ATTENDANCE_HOUR_ALLOCATION"
    __table_args__ = (
        UniqueConstraint("attendance_entry_id", "category", name="uq_attendance_allocation_category"),
        {"extend_existing": True},
    )

    allocation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attendance_entry_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ATTENDANCE_ENTRY.attendance_entry_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    @validates("category")
    def _validate_category(self, key: str, value: str) -> str:
        from backend.orm.labor_taxonomy import HourCategoryEnum

        valid = {c.value for c in HourCategoryEnum}
        if value not in valid:
            raise ValueError(f"category must be one of {sorted(valid)}, got {value!r}")
        return value
