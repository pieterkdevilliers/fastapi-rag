"""create accountprompts table

Revision ID: b8c0a7a2b2a2
Revises: 9710743376dc
Create Date: 2025-09-09 14:10:15.998992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b8c0a7a2b2a2'
down_revision: Union[str, None] = '9710743376dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accountprompts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('account_unique_id', sa.String, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('prompt_key', sa.String, nullable=False),
        sa.Column('prompt_text', sa.String, nullable=False),
        sa.ForeignKeyConstraint(['account_unique_id'], ['account.account_unique_id']),
    )

def downgrade() -> None:
    op.drop_table('accountprompts')