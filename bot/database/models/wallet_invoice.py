from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_models import Base


class WalletInvoice(Base):
    __tablename__ = 'wallet_invoices'

    order_id: Mapped[str] = mapped_column(String(32), unique=True)
    provider: Mapped[str] = mapped_column(String(20), default='wallet', server_default='wallet')
    provider_invoice_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    recipient: Mapped[str] = mapped_column(String(32))
    product: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer)
    asset: Mapped[str] = mapped_column(String(4))
    receiver: Mapped[str] = mapped_column(String(100))
    atomic_amount: Mapped[Decimal] = mapped_column(Numeric(30, 0))
    base_stars: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    created: Mapped[int] = mapped_column(BigInteger)
    expires: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), index=True, server_default='pending')
    transaction: Mapped[str | None] = mapped_column(String(64), unique=True)
    delivery_transaction: Mapped[str | None] = mapped_column(String(128))
