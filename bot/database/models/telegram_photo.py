from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_models import Base


class TelegramPhoto(Base):
    __tablename__ = 'telegram_photos'
    __table_args__ = (UniqueConstraint('bot_id', 'sha256'),)

    bot_id: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    file_id: Mapped[str] = mapped_column(String(512))
