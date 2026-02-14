"""
Product ORM schema (SQLAlchemy)
"""
from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, Text, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from backend.database import Base


class Product(Base):
    """Product table ORM"""
    __tablename__ = "PRODUCT"
    __table_args__ = (
        UniqueConstraint('client_id', 'product_code', name='uq_product_client_code'),
        {"extend_existing": True}
    )

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)
    product_code = Column(String(50), nullable=False, index=True)
    product_name = Column(String(100), nullable=False)
    description = Column(Text)
    ideal_cycle_time = Column(
        DECIMAL(8, 4), nullable=True, comment="Hours per unit - NULL triggers inference"
    )
    unit_of_measure = Column(String(20), nullable=False, default="units")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )
