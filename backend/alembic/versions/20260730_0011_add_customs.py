"""add customs_declarations + customs_channel_history (Bước 4, GĐ7A)"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0011"
down_revision: Union[str, None] = "20260730_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


declaration_type_enum = postgresql.ENUM(
    "import", "export", name="customs_declaration_type"
)
channel_enum = postgresql.ENUM("green", "yellow", "red", name="customs_channel")


def upgrade() -> None:
    declaration_type_enum.create(op.get_bind(), checkfirst=True)
    channel_enum.create(op.get_bind(), checkfirst=True)

    declaration_type_col = postgresql.ENUM(
        "import", "export", name="customs_declaration_type", create_type=False
    )
    channel_col = postgresql.ENUM(
        "green", "yellow", "red", name="customs_channel", create_type=False
    )

    op.create_table(
        "customs_declarations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("declaration_no", sa.String(length=100), nullable=True),
        sa.Column("declaration_type", declaration_type_col, nullable=False),
        sa.Column("channel", channel_col, nullable=True),
        sa.Column("hs_code", sa.String(length=50), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["container_id"], ["containers.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customs_declarations_container_id", "customs_declarations", ["container_id"])

    channel_col_2 = postgresql.ENUM(
        "green", "yellow", "red", name="customs_channel", create_type=False
    )
    op.create_table(
        "customs_channel_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("declaration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_channel", channel_col, nullable=True),
        sa.Column("to_channel", channel_col_2, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["declaration_id"], ["customs_declarations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customs_channel_history_declaration_id", "customs_channel_history", ["declaration_id"])


def downgrade() -> None:
    op.drop_index("ix_customs_channel_history_declaration_id", table_name="customs_channel_history")
    op.drop_table("customs_channel_history")
    op.drop_index("ix_customs_declarations_container_id", table_name="customs_declarations")
    op.drop_table("customs_declarations")
    channel_enum.drop(op.get_bind(), checkfirst=True)
    declaration_type_enum.drop(op.get_bind(), checkfirst=True)
