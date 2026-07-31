"""add quotes + quote_charges (RFQ/Quote baseline for cost reconciliation)"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0008"
down_revision: Union[str, None] = "20260730_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


quote_status_enum = postgresql.ENUM(
    "draft", "sent", "accepted", "rejected", "expired", name="quote_status"
)
charge_group_enum = postgresql.ENUM(
    "ocean_freight", "surcharge", "local", name="quote_charge_group"
)


def upgrade() -> None:
    quote_status_enum.create(op.get_bind(), checkfirst=True)
    charge_group_enum.create(op.get_bind(), checkfirst=True)

    status_col = postgresql.ENUM(
        "draft", "sent", "accepted", "rejected", "expired",
        name="quote_status", create_type=False,
    )
    charge_group_col = postgresql.ENUM(
        "ocean_freight", "surcharge", "local",
        name="quote_charge_group", create_type=False,
    )

    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_no", sa.String(length=50), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("status", status_col, nullable=False),
        sa.Column("pol", sa.String(length=255), nullable=True),
        sa.Column("pod", sa.String(length=255), nullable=True),
        sa.Column("commodity", sa.String(length=255), nullable=True),
        sa.Column("is_dangerous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_reefer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("container_type", sa.String(length=50), nullable=True),
        sa.Column("container_qty", sa.Integer(), nullable=True),
        sa.Column("gross_weight_kg", sa.Numeric(12, 2), nullable=True),
        sa.Column("cargo_ready_date", sa.Date(), nullable=True),
        sa.Column("incoterm", sa.String(length=20), nullable=True),
        sa.Column("payment_term", sa.String(length=255), nullable=True),
        sa.Column("transit_time", sa.String(length=100), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["container_id"], ["containers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_no", name="uq_quotes_quote_no"),
    )
    op.create_index("ix_quotes_quote_no", "quotes", ["quote_no"])
    op.create_index("ix_quotes_container_id", "quotes", ["container_id"])

    op.create_table(
        "quote_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("charge_group", charge_group_col, nullable=False),
        sa.Column("charge_code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_charges_quote_id", "quote_charges", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_quote_charges_quote_id", table_name="quote_charges")
    op.drop_table("quote_charges")
    op.drop_index("ix_quotes_container_id", table_name="quotes")
    op.drop_index("ix_quotes_quote_no", table_name="quotes")
    op.drop_table("quotes")
    charge_group_enum.drop(op.get_bind(), checkfirst=True)
    quote_status_enum.drop(op.get_bind(), checkfirst=True)
