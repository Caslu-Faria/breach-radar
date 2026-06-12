"""Models ORM (SQLAlchemy) da aplicação."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Breach(Base):
    __tablename__ = "breaches"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    breach_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    added_date: Mapped[str | None] = mapped_column(String(25), nullable=True)
    pwn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_classes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_spam_list: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
