"""Store Telegram user IDs as BIGINT.

Revision ID: 0002_users_telegram_id_bigint
Revises: 0001_initial_schema
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_users_telegram_id_bigint"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        postgresql_using="telegram_id::bigint",
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        postgresql_using="telegram_id::integer",
    )
