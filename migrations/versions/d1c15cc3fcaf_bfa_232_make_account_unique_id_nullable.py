"""bfa-232 make account_unique_id nullable

Revision ID: d1c15cc3fcaf
Revises: 7dc4d2a01a06
Create Date: 2025-06-16 22:35:31.575428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd1c15cc3fcaf'
down_revision: Union[str, None] = '7dc4d2a01a06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Manually edited to remove the dangerous drop_table command ###
    
    # This is the only part we want to run.
    with op.batch_alter_table('stripesubscription', schema=None) as batch_op:
        batch_op.alter_column('account_unique_id',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('current_period_end',
               existing_type=sa.DATETIME(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Manually edited to keep only the relevant downgrade commands ###
    
    # This correctly reverses the upgrade.
    with op.batch_alter_table('stripesubscription', schema=None) as batch_op:
        batch_op.alter_column('current_period_end',
               existing_type=sa.DATETIME(),
               nullable=False)
        batch_op.alter_column('account_unique_id',
               existing_type=sa.VARCHAR(),
               nullable=False)
               
    # ### end Alembic commands ###