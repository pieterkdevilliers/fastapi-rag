"""add visitor opt-indetails to chatsession model

Revision ID: 821bf28b2317
Revises: 2cc0b1f0e4a4
Create Date: 2025-09-17 13:14:38.771517

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '821bf28b2317'
down_revision: Union[str, None] = '2cc0b1f0e4a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add only the two new fields to existing chatsession table
    with op.batch_alter_table('chatsession', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visitor_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('visitor_email', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    # Remove the two new fields from chatsession table
    with op.batch_alter_table('chatsession', schema=None) as batch_op:
        batch_op.drop_column('visitor_email')
        batch_op.drop_column('visitor_name')