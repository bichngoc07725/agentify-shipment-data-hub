"""bookings.container_id nullable — đặt chỗ xảy ra trước khi có container"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0015"
down_revision: Union[str, None] = "20260730_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "bookings",
        "container_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Bản ghi đặt chỗ chưa gắn container không biểu diễn được ở schema cũ, nên
    # phải bỏ đi trước khi siết lại cột — nếu không ALTER sẽ hỏng.
    op.execute(sa.text("DELETE FROM bookings WHERE container_id IS NULL"))
    op.alter_column(
        "bookings",
        "container_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
