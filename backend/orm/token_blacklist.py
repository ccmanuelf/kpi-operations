"""
Token blacklist ORM schema (SQLAlchemy)

Database-backed JWT revocation (Run 7 T1.4). Rows are keyed by the token's
jti claim (sha256 digest of the raw token for legacy tokens minted before the
jti claim existed). Revocation must live in the database — not process
memory — so logout survives restarts/redeploys and is visible to every
worker. Expired rows are pruned opportunistically on insert, bounding growth
to the set of tokens revoked within their own lifetime.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class TokenBlacklist(Base):
    """TOKEN_BLACKLIST table ORM - revoked (logged-out) JWTs by jti"""

    __tablename__ = "TOKEN_BLACKLIST"
    __table_args__ = {"extend_existing": True}

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Token's own exp — once this passes, the row is prunable (the JWT is
    # rejected by signature/exp validation anyway).
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
