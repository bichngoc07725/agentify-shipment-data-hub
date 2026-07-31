"""add exception_actions audit table for resolve/approve on exceptions"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0007"
down_revision: Union[str, None] = "20260730_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exception_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("severity_tier", sa.String(length=20), nullable=False),
        sa.Column("acted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acted_by_username", sa.String(length=100), nullable=False),
        sa.Column("acted_by_role", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["container_id"], ["containers.id"]),
        sa.ForeignKeyConstraint(["acted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exception_actions_container_id",
        "exception_actions",
        ["container_id"],
    )
    op.create_index(
        "ix_exception_actions_container_code",
        "exception_actions",
        ["container_id", "code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exception_actions_container_code", table_name="exception_actions"
    )
    op.drop_index(
        "ix_exception_actions_container_id", table_name="exception_actions"
    )
    op.drop_table("exception_actions")
