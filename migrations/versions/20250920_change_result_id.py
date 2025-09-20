"""Change result_id to string

Revision ID: 20250920_change_result_id
Revises: 7f16f5251cda
Create Date: 2025-09-20 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250920_change_result_id'
down_revision = '7f16f5251cda'
branch_labels = None
depends_on = None

def upgrade():
    # Change result_id from integer to text
    op.alter_column(
        "scorecardresult",
        "result_id",
        existing_type=sa.Integer(),
        type_=sa.Text(),
        postgresql_using="result_id::text",
        existing_nullable=False
    )

def downgrade():
    # Revert back to integer (if needed)
    op.alter_column(
        "scorecardresult",
        "result_id",
        existing_type=sa.Text(),
        type_=sa.Integer(),
        postgresql_using="result_id::integer",
        existing_nullable=False
    )