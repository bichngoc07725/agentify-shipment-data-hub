"""make emails channel-aware so non-mailbox sources can be ingested"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260726_0005"
down_revision: Union[str, None] = "20260726_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "emails",
        sa.Column(
            "channel",
            sa.String(length=32),
            nullable=False,
            server_default="email",
        ),
    )
    op.create_index("ix_emails_channel", "emails", ["channel"])
    # A pasted Zalo message has no mailbox behind it.
    op.alter_column("emails", "gmail_connection_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    # Rows without a mailbox cannot satisfy the restored NOT NULL constraint.
    op.execute("DELETE FROM container_facts WHERE email_id IN (SELECT id FROM emails WHERE gmail_connection_id IS NULL)")
    op.execute("DELETE FROM attachments WHERE email_id IN (SELECT id FROM emails WHERE gmail_connection_id IS NULL)")
    op.execute("DELETE FROM emails WHERE gmail_connection_id IS NULL")
    op.alter_column("emails", "gmail_connection_id", existing_type=sa.UUID(), nullable=False)
    op.drop_index("ix_emails_channel", table_name="emails")
    op.drop_column("emails", "channel")
