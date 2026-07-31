"""allow field-photo attachments/facts with no email behind them

A driver's container/seal/EIR/POD photo doesn't arrive via an email message,
so `attachments.email_id` and `container_facts.email_id` can no longer be
NOT NULL — both change to nullable. `attachments.source_channel` tells a
Gmail attachment apart from a field upload.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0009"
down_revision: Union[str, None] = "20260730_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("attachments", "email_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("container_facts", "email_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "attachments",
        sa.Column(
            "source_channel",
            sa.String(length=20),
            nullable=False,
            server_default="gmail",
        ),
    )


def downgrade() -> None:
    op.drop_column("attachments", "source_channel")
    # Rows saved with no email would violate the restored NOT NULL constraint.
    op.execute("DELETE FROM container_facts WHERE email_id IS NULL")
    op.execute("DELETE FROM attachments WHERE email_id IS NULL")
    op.alter_column("container_facts", "email_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("attachments", "email_id", existing_type=sa.UUID(), nullable=False)
