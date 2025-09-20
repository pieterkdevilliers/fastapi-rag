"""merge multiple heads

Revision ID: 857d5dd65127
Revises: change_result_id_to_text, db9ca40feb2a
Create Date: 2025-09-20 14:03:06.615583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '857d5dd65127'
down_revision: Union[str, None] = ('change_result_id_to_text', 'db9ca40feb2a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
