from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class WishlistStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    ARCHIVED = "ARCHIVED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wishlists: Mapped[list[Wishlist]] = relationship(back_populates="owner")
    reservations: Mapped[list[Reservation]] = relationship(back_populates="guest")


class Wishlist(Base):
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    status: Mapped[WishlistStatus] = mapped_column(SqlEnum(WishlistStatus, name="wishlist_status"), default=WishlistStatus.ACTIVE)
    invite_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    party_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="wishlists")
    gifts: Mapped[list[Gift]] = relationship(back_populates="wishlist")


class Gift(Base):
    __tablename__ = "gifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    wishlist_id: Mapped[int] = mapped_column(ForeignKey("wishlists.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    product_url: Mapped[str | None] = mapped_column(String(1000))
    price_note: Mapped[str | None] = mapped_column(String(60))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    wishlist: Mapped[Wishlist] = relationship(back_populates="gifts")
    reservation: Mapped[Reservation | None] = relationship(back_populates="gift", uselist=False)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (UniqueConstraint("gift_id", name="uq_reservations_gift_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gift_id: Mapped[int] = mapped_column(ForeignKey("gifts.id", ondelete="RESTRICT"))
    guest_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gift: Mapped[Gift] = relationship(back_populates="reservation")
    guest: Mapped[User] = relationship(back_populates="reservations")
