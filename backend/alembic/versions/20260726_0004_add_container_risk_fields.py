"""add container risk fields used by the exception engine"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260726_0004"
down_revision: Union[str, None] = "20260610_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("containers", sa.Column("do_no", sa.String(length=255), nullable=True))
    op.add_column("containers", sa.Column("ata", sa.Date(), nullable=True))
    op.add_column("containers", sa.Column("free_time_days", sa.Integer(), nullable=True))
    op.create_index("ix_containers_do_no", "containers", ["do_no"])


def downgrade() -> None:
    op.drop_index("ix_containers_do_no", table_name="containers")
    op.drop_column("containers", "free_time_days")
    op.drop_column("containers", "ata")
    op.drop_column("containers", "do_no")
