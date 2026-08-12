"""add bookings (Bước 2 — đặt chỗ trên tàu)"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0014"
down_revision: Union[str, None] = "20260730_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


booking_status_enum = postgresql.ENUM(
    "requested", "confirmed", "amended", "cancelled", name="booking_status"
)


def upgrade() -> None:
    booking_status_enum.create(op.get_bind(), checkfirst=True)

    status_col = postgresql.ENUM(
        "requested",
        "confirmed",
        "amended",
        "cancelled",
        name="booking_status",
        create_type=False,
    )

    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booking_no", sa.String(length=100), nullable=True),
        sa.Column("status", status_col, nullable=False),
        sa.Column("carrier", sa.String(length=255), nullable=True),
        sa.Column("vessel", sa.String(length=255), nullable=True),
        sa.Column("voyage", sa.String(length=100), nullable=True),
        sa.Column("pol", sa.String(length=255), nullable=True),
        sa.Column("pod", sa.String(length=255), nullable=True),
        sa.Column("etd", sa.Date(), nullable=True),
        sa.Column("eta", sa.Date(), nullable=True),
        sa.Column("si_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vgm_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gate_in_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("container_type", sa.String(length=50), nullable=True),
        sa.Column("container_qty", sa.Integer(), nullable=True),
        sa.Column("empty_pickup_depot", sa.String(length=255), nullable=True),
        sa.Column("freight_rate", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["container_id"], ["containers.id"]),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bookings_container_id", "bookings", ["container_id"], unique=False
    )
    op.create_index("ix_bookings_booking_no", "bookings", ["booking_no"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bookings_booking_no", table_name="bookings")
    op.drop_index("ix_bookings_container_id", table_name="bookings")
    op.drop_table("bookings")
    booking_status_enum.drop(op.get_bind(), checkfirst=True)
