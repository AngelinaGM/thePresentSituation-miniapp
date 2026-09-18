"""initial schema

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0001_initial_schema"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    # Create the named PostgreSQL type exactly once.  `create_type=False`
    # prevents op.create_table() from emitting a second CREATE TYPE statement.
    state=postgresql.ENUM("ACTIVE","FROZEN","ARCHIVED",name="wishlist_status",create_type=False)
    state.create(op.get_bind(),checkfirst=True)
    op.create_table("users",sa.Column("id",sa.Integer,primary_key=True),sa.Column("telegram_id",sa.BigInteger,nullable=False,unique=True),sa.Column("username",sa.String(255)),sa.Column("first_name",sa.String(255),nullable=False),sa.Column("last_name",sa.String(255)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False))
    op.create_table("wishlists",sa.Column("id",sa.Integer,primary_key=True),sa.Column("owner_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),sa.Column("title",sa.String(100),nullable=False),sa.Column("status",state,nullable=False,server_default="ACTIVE"),sa.Column("invite_token",sa.String(64),nullable=False,unique=True),sa.Column("party_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("archived_at",sa.DateTime(timezone=True)))
    op.create_table("gifts",sa.Column("id",sa.Integer,primary_key=True),sa.Column("wishlist_id",sa.Integer,sa.ForeignKey("wishlists.id"),nullable=False),sa.Column("title",sa.String(160),nullable=False),sa.Column("product_url",sa.String(1000)),sa.Column("price_note",sa.String(60)),sa.Column("comment",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)))
    op.create_table("reservations",sa.Column("id",sa.Integer,primary_key=True),sa.Column("gift_id",sa.Integer,sa.ForeignKey("gifts.id"),nullable=False,unique=True),sa.Column("guest_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False))
def downgrade():
    op.drop_table("reservations"); op.drop_table("gifts"); op.drop_table("wishlists"); op.drop_table("users"); state=postgresql.ENUM("ACTIVE","FROZEN","ARCHIVED",name="wishlist_status",create_type=False); state.drop(op.get_bind(),checkfirst=True)
