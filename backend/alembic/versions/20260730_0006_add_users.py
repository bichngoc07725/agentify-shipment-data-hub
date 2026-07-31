"""add users table for RBAC login (one role per account)"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0006"
down_revision: Union[str, None] = "20260726_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = postgresql.ENUM(
    "admin",
    "manager",
    "sales_cs",
    "docs",
    "ops",
    "accountant",
    "driver",
    name="user_role",
)


def upgrade() -> None:
    user_role_enum.create(op.get_bind(), checkfirst=True)
    # `create_type=False`: the enum type was just created above. Without this,
    # SQLAlchemy's DDL compiler creates it a second time for this column and
    # Postgres raises DuplicateObject.
    role_column_type = postgresql.ENUM(
        "admin",
        "manager",
        "sales_cs",
        "docs",
        "ops",
        "accountant",
        "driver",
        name="user_role",
        create_type=False,
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", role_column_type, nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
    user_role_enum.drop(op.get_bind(), checkfirst=True)
