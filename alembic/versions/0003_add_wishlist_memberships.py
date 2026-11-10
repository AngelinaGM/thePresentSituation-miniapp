"""Add saved access for wishlists shared with a user.

Revision ID: 0003_add_wishlist_memberships
Revises: 0002_users_telegram_id_bigint
Create Date: 2026-11-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_wishlist_memberships"
down_revision = "0002_users_telegram_id_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wishlist_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wishlist_id", sa.Integer(), sa.ForeignKey("wishlists.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("first_opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("wishlist_id", "user_id", name="uq_wishlist_memberships_wishlist_user"),
    )
    op.create_index("ix_wishlist_memberships_wishlist_id", "wishlist_memberships", ["wishlist_id"])
    op.create_index("ix_wishlist_memberships_user_id", "wishlist_memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_wishlist_memberships_user_id", table_name="wishlist_memberships")
    op.drop_index("ix_wishlist_memberships_wishlist_id", table_name="wishlist_memberships")
    op.drop_table("wishlist_memberships")
