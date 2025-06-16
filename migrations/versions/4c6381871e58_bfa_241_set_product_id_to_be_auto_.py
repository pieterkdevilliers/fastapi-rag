"""Set product.id to be auto-incrementing on PostgreSQL

Revision ID: 4c6381871e58
Revises: 906de5175540
Create Date: ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4c6381871e58'  # Use your actual revision ID
down_revision: Union[str, None] = '906de5175540'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get the dialect name to run commands conditionally
    dialect = op.get_bind().dialect.name

    # These commands are ONLY for PostgreSQL
    if dialect == 'postgresql':
        op.execute("CREATE SEQUENCE product_id_seq")
        op.execute("ALTER TABLE product ALTER COLUMN id SET DEFAULT nextval('product_id_seq')")
        op.execute("ALTER SEQUENCE product_id_seq OWNED BY product.id")


def downgrade() -> None:
    # Get the dialect name to run commands conditionally
    dialect = op.get_bind().dialect.name

    # These commands are ONLY for PostgreSQL
    if dialect == 'postgresql':
        op.execute("ALTER TABLE product ALTER COLUMN id DROP DEFAULT")
        op.execute("DROP SEQUENCE product_id_seq")