"""
Product ORM schema (SQLAlchemy)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, TIMESTAMP, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class Product(Base):
    """Product table ORM"""

    __tablename__ = "PRODUCT"
    __table_args__ = (
        UniqueConstraint("client_id", "product_code", name="uq_product_client_code"),
        {"extend_existing": True},
    )

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    ideal_cycle_time: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(8, 4), nullable=True, comment="Hours per unit - NULL triggers inference"
    )
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False, default="units")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )
