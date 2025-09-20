"""add scorecardaccount model

Revision ID: d972acf2da98
Revises: 3cb9386a3d8a
Create Date: 2025-09-20 12:02:22.387102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd972acf2da98'
down_revision: Union[str, None] = '3cb9386a3d8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('scoreapp_account',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scoreapp_id', sa.String(), nullable=False),
        sa.Column('account_unique_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['account_unique_id'], ['account.account_unique_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('scoreapp_account')

    # ### end Alembic commands ###
