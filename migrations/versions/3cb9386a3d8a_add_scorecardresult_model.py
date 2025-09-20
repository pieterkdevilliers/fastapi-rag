"""add scorecardresult model

Revision ID: 3cb9386a3d8a
Revises: fbe9113da9f4
Create Date: 2025-09-20 08:12:30.136229

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cb9386a3d8a'
down_revision: Union[str, None] = 'fbe9113da9f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scorecardresult",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("account_unique_id", sa.String(), sa.ForeignKey("account.account_unique_id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("report_url", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("scorecardresult")
