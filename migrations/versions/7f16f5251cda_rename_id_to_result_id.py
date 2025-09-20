"""rename id to result_id

Revision ID: 7f16f5251cda
Revises: d972acf2da98
Create Date: 2025-09-20 13:03:40.224170
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f16f5251cda'
down_revision: Union[str, None] = 'd972acf2da98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scorecardresult", schema=None) as batch_op:
        batch_op.alter_column(
            "id",
            new_column_name="result_id",
            existing_type=sa.Integer(),
            existing_nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("scorecardresult", schema=None) as batch_op:
        batch_op.alter_column(
            "result_id",
            new_column_name="id",
            existing_type=sa.Integer(),
            existing_nullable=False
        )
