"""Add extracted_report_text field

Revision ID: 445ee874ab83
Revises: fresh_scorecardresult
Create Date: 2025-09-22 08:36:30.031343

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '445ee874ab83'
down_revision: Union[str, None] = 'fresh_scorecardresult'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add only the new field you want
    op.add_column('scorecardresult', sa.Column('extracted_report_text', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove the field if rolling back
    op.drop_column('scorecardresult', 'extracted_report_text')