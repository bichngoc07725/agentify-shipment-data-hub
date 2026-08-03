"""add shipments (Kanban job board, GĐ7B) + containers.shipment_id"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0012"
down_revision: Union[str, None] = "20260730_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


direction_enum = postgresql.ENUM("import", "export", name="shipment_direction")
stage_enum = postgresql.ENUM(
    "rfq", "booking", "documents", "customs", "delivery", "reconciliation", "closed",
    name="shipment_stage",
)
# `user_role` already exists (migration 20260730_0006) — referenced here, not created.
user_role_col = postgresql.ENUM(
    "admin", "manager", "sales_cs", "docs", "ops", "accountant", "driver",
    name="user_role", create_type=False,
)


def upgrade() -> None:
    direction_enum.create(op.get_bind(), checkfirst=True)
    stage_enum.create(op.get_bind(), checkfirst=True)

    direction_col = postgresql.ENUM(
        "import", "export", name="shipment_direction", create_type=False
    )
    stage_col = postgresql.ENUM(
        "rfq", "booking", "documents", "customs", "delivery", "reconciliation", "closed",
        name="shipment_stage", create_type=False,
    )

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_no", sa.String(length=50), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("direction", direction_col, nullable=True),
        sa.Column("stage", stage_col, nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_role", user_role_col, nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_no", name="uq_shipments_shipment_no"),
    )
    op.create_index("ix_shipments_shipment_no", "shipments", ["shipment_no"])

    op.add_column(
        "containers", sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_containers_shipment_id", "containers", "shipments", ["shipment_id"], ["id"]
    )
    op.create_index("ix_containers_shipment_id", "containers", ["shipment_id"])


def downgrade() -> None:
    op.drop_index("ix_containers_shipment_id", table_name="containers")
    op.drop_constraint("fk_containers_shipment_id", "containers", type_="foreignkey")
    op.drop_column("containers", "shipment_id")
    op.drop_index("ix_shipments_shipment_no", table_name="shipments")
    op.drop_table("shipments")
    stage_enum.drop(op.get_bind(), checkfirst=True)
    direction_enum.drop(op.get_bind(), checkfirst=True)
