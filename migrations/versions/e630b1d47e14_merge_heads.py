"""merge heads

Revision ID: e630b1d47e14
Revises: 0844758a423b, 19091980090802
Create Date: 2025-09-20 16:31:31.023492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e630b1d47e14'
down_revision: Union[str, None] = ('0844758a423b', '19091980090802')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
