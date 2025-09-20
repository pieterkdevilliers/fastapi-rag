"""create scorecardresult table from scratch

Revision ID: 19091980090802
Revises: None
Create Date: 2025-09-20 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '19091980090802'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scorecardresult',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('result_id', sa.String(), nullable=False, unique=True),
        sa.Column('account_unique_id', sa.String(), sa.ForeignKey('account.account_unique_id')),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('report_url', sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('scorecardresult')
