"""set k_value to 7 and add temperature to account table

Revision ID: e0cf51caf684
Revises: b8c0a7a2b2a2
Create Date: 2025-09-11 09:45:58.921860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e0cf51caf684'
down_revision: Union[str, None] = 'b8c0a7a2b2a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    with op.batch_alter_table('account', schema=None) as batch_op:
        batch_op.add_column(sa.Column('temperature', sa.Float(), nullable=True))
        batch_op.alter_column(
            'k_value',
            existing_type=sa.Integer(),
            nullable=True,
            server_default="7"
        )


def downgrade() -> None:
    with op.batch_alter_table('account', schema=None) as batch_op:
        batch_op.drop_column('temperature')
        batch_op.alter_column(
            'k_value',
            existing_type=sa.Integer(),
            nullable=True,
            server_default="4"
        )