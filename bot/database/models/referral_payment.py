from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base_models import Base


class ReferralPayment(Base):
    __tablename__ = 'referral_payments'
    __table_args__ = (UniqueConstraint('provider', 'payment_id'),)

    provider: Mapped[str] = mapped_column(String(20))
    payment_id: Mapped[str] = mapped_column(String(100))
    buyer_id: Mapped[int] = mapped_column(BigInteger)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    base_stars: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    reward_stars: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(20), server_default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
