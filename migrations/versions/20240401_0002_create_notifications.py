"""create notifications audit table"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240401_0002"
down_revision = "20240326_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("playbook", sa.String(length=255), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("adapter", sa.String(length=100), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("notifications")
