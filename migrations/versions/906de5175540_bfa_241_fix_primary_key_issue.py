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
    # ### Manually corrected migration using BATCH MODE for SQLite ###
    # For an unnamed PK, we only need to create the new one.
    # The old one is implicitly replaced during the table recreation.
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.create_primary_key('product_pkey', ['id'])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Manually corrected downgrade using BATCH MODE for SQLite ###
    # The same logic applies in reverse for the downgrade.
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.create_primary_key('product_pkey', ['product_id'])

    # ### end Alembic commands ###