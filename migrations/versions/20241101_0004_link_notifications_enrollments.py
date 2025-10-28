"""Add enrollment linkage to notifications."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20241101_0004"
down_revision = "20240415_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("enrollment_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_notifications_enrollment_id",
        "notifications",
        ["enrollment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_notifications_enrollment_id_enrollments",
        "notifications",
        "enrollments",
        ["enrollment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_notifications_enrollment_id_enrollments",
        "notifications",
        type_="foreignkey",
    )
    op.drop_index("ix_notifications_enrollment_id", table_name="notifications")
    op.drop_column("notifications", "enrollment_id")

