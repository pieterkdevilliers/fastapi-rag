"""create new scorecard result table

Revision ID: 92d5a05b4570
Revises: 5b51ebd73387
Create Date: 2025-09-20 16:03:10.997761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92d5a05b4570'
down_revision: Union[str, None] = '5b51ebd73387'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new scorecardresult table
    op.create_table(
        'scorecardresult',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('result_id', sa.String, nullable=False, unique=True),
        sa.Column('account_unique_id', sa.String, sa.ForeignKey('account.account_unique_id')),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('first_name', sa.String, nullable=True),
        sa.Column('last_name', sa.String, nullable=True),
        sa.Column('email', sa.String, nullable=True),
        sa.Column('key', sa.String, nullable=False),
        sa.Column('report_url', sa.String, nullable=False),
    )


def downgrade() -> None:
    # Drop the table if downgrading
    op.drop_table('scorecardresult')
