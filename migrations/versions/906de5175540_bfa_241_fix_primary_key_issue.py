"""bfa-241 fix primary key issue

Revision ID: 906de5175540
Revises: 60422a85b48f
Create Date: ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '906de5175540'
down_revision: Union[str, None] = '60422a85b48f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Manually corrected migration with conditional logic for different DBs ###
    dialect = op.get_bind().dialect.name

    with op.batch_alter_table('product', schema=None) as batch_op:
        # This DROP command will ONLY run on PostgreSQL, where the constraint is named.
        # It will be skipped on SQLite, avoiding the "no such constraint" error.
        if dialect == 'postgresql':
            batch_op.drop_constraint('product_pkey', type_='primary')

        # This CREATE command will run on both.
        # On SQLite, it defines the PK for the new table.
        # On PostgreSQL, it adds the new PK to the existing table (which now works).
        batch_op.create_primary_key('product_pkey', ['id'])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Manually corrected downgrade with conditional logic ###
    dialect = op.get_bind().dialect.name

    with op.batch_alter_table('product', schema=None) as batch_op:
        # This DROP command will ONLY run on PostgreSQL.
        if dialect == 'postgresql':
            batch_op.drop_constraint('product_pkey', type_='primary')

        # This CREATE command will run on both to restore the original state.
        batch_op.create_primary_key('product_pkey', ['product_id'])

    # ### end Alembic commands ###