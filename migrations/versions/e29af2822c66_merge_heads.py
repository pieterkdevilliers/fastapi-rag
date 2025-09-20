"""merge heads

Revision ID: e29af2822c66
Revises: 5b51ebd73387, e630b1d47e14
Create Date: 2025-09-20 16:42:11.845233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e29af2822c66'
down_revision: Union[str, None] = ('5b51ebd73387', 'e630b1d47e14')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
