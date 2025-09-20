"""create scorecard tables for Postgres

Revision ID: 0844758a423b
Revises: 4307c0f89549
Create Date: 2025-09-20 15:34:08.682745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0844758a423b'
down_revision: Union[str, None] = '4307c0f89549'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scoreapp_account table
    op.create_table(
        "scoreapp_account",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scoreapp_id", sa.String(length=255), nullable=False),
        sa.Column("account_unique_id", sa.String(length=255), sa.ForeignKey("account.account_unique_id")),
    )

    # Create scorecardresult table
    op.create_table(
        "scorecardresult",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_unique_id", sa.String(length=255), sa.ForeignKey("account.account_unique_id")),
        sa.Column("status", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("report_url", sa.String(length=255), nullable=False),
        sa.Column("result_id", sa.String(length=255), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("scorecardresult")
    op.drop_table("scoreapp_account")
