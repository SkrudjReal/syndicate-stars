from typing import Optional

from sqlalchemy import BigInteger, Column, String, Integer, Float, Numeric, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped

from .base_models import Base
from .types import str_32


class User(Base):
    __tablename__ = 'users'

    username: Mapped[Optional[str_32]] = mapped_column(nullable=True)
    full_name: Mapped[str] = mapped_column(nullable=False)
    referrer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    welcome_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    welcome_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')


class Stars(Base):
    __tablename__ = 'stars'

    course = Column(Integer, nullable=False, server_default='150')


class UserStars(Base):
    __tablename__ = 'user_stars'

    user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    stars = Column(Numeric(20, 2), nullable=False, server_default='0')


class UserWithdraws(Base):
    __tablename__ = 'user_withdraws'
    __table_args__ = (UniqueConstraint('user_id', 'request_id'),)

    user_id = Column(BigInteger, index=True, nullable=False)
    stars = Column(Float, nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    whom = Column(String, nullable=False)
    request_id = Column(BigInteger, nullable=True)
    status = Column(String(20), nullable=False, server_default='sent')
    tx_hash = Column(String(128), nullable=True)
