from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_models import Base


class NotificationOrder(Base):
    __tablename__ = 'notification_orders'

    payment_id: Mapped[str] = mapped_column(String(100), unique=True)
    shop_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3))
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, server_default='false')
