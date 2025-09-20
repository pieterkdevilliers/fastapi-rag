"""create scorecardresult table fresh

Revision ID: fresh_scorecardresult
Revises: e29af2822c66
Create Date: 2025-09-20 17:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "fresh_scorecardresult"
down_revision = "e29af2822c66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scorecardresult",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("result_id", sa.String, nullable=False, unique=True),
        sa.Column(
            "account_unique_id",
            sa.String,
            sa.ForeignKey("account.account_unique_id"),
            nullable=False,
        ),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("first_name", sa.String, nullable=True),
        sa.Column("last_name", sa.String, nullable=True),
        sa.Column("email", sa.String, nullable=True),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("report_url", sa.String, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("scorecardresult")
