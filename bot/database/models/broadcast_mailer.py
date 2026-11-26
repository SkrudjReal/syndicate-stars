from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base_models import Base


class BroadcastMailer(Base):
    __tablename__ = 'broadcast_mailers'
    data: Mapped[str] = mapped_column(String())
