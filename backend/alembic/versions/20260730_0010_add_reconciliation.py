"""add debit_notes + reconciliations (Bước 6 cost reconciliation, GĐ6)"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0010"
down_revision: Union[str, None] = "20260730_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reconciliation_status_enum = postgresql.ENUM(
    "draft", "reviewed", "approved", "escalated", name="reconciliation_status"
)
match_status_enum = postgresql.ENUM(
    "matched", "variance", "missing_actual", "extra_actual",
    name="reconciliation_match_status",
)


def upgrade() -> None:
    reconciliation_status_enum.create(op.get_bind(), checkfirst=True)
    match_status_enum.create(op.get_bind(), checkfirst=True)

    status_col = postgresql.ENUM(
        "draft", "reviewed", "approved", "escalated",
        name="reconciliation_status", create_type=False,
    )
    match_status_col = postgresql.ENUM(
        "matched", "variance", "missing_actual", "extra_actual",
        name="reconciliation_match_status", create_type=False,
    )

    op.create_table(
        "debit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_attachment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("partner_name", sa.String(length=255), nullable=True),
        sa.Column("doc_no", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["container_id"], ["containers.id"]),
        sa.ForeignKeyConstraint(["source_attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debit_notes_container_id", "debit_notes", ["container_id"])

    op.create_table(
        "debit_note_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("debit_note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("charge_code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["debit_note_id"], ["debit_notes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debit_note_charges_debit_note_id", "debit_note_charges", ["debit_note_id"])

    op.create_table(
        "reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", status_col, nullable=False),
        sa.Column("total_quoted", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_actual", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_variance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("needs_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["container_id"], ["containers.id"]),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliations_container_id", "reconciliations", ["container_id"])
    op.create_index("ix_reconciliations_quote_id", "reconciliations", ["quote_id"])

    op.create_table(
        "reconciliation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("charge_code", sa.String(length=50), nullable=False),
        sa.Column("quoted_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("actual_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("variance", sa.Numeric(14, 2), nullable=False),
        sa.Column("match_status", match_status_col, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["reconciliation_id"], ["reconciliations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliation_lines_reconciliation_id", "reconciliation_lines", ["reconciliation_id"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_lines_reconciliation_id", table_name="reconciliation_lines")
    op.drop_table("reconciliation_lines")
    op.drop_index("ix_reconciliations_quote_id", table_name="reconciliations")
    op.drop_index("ix_reconciliations_container_id", table_name="reconciliations")
    op.drop_table("reconciliations")
    op.drop_index("ix_debit_note_charges_debit_note_id", table_name="debit_note_charges")
    op.drop_table("debit_note_charges")
    op.drop_index("ix_debit_notes_container_id", table_name="debit_notes")
    op.drop_table("debit_notes")
    match_status_enum.drop(op.get_bind(), checkfirst=True)
    reconciliation_status_enum.drop(op.get_bind(), checkfirst=True)
