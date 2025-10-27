"""create uploaded files table"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240326_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=512), nullable=False),
        sa.Column("mime", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("uploaded_files")
