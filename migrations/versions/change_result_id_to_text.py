"""Alter result_id to Text for PostgreSQL

Revision ID: change_result_id_to_text
Revises: 20250920_change_result_id
Create Date: 2025-09-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "change_result_id_to_text"
down_revision = "20250920_change_result_id"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Drop the primary key constraint temporarily
    op.drop_constraint("scorecardresult_pkey", "scorecardresult", type_="primary")

    # 2. Alter the column type from INTEGER to TEXT
    op.alter_column(
        "scorecardresult",
        "result_id",
        type_=sa.Text(),
        existing_type=sa.Integer(),
        postgresql_using="result_id::text"
    )

    # 3. Re-create the primary key constraint
    op.create_primary_key("scorecardresult_pkey", "scorecardresult", ["result_id"])


def downgrade():
    # 1. Drop the primary key constraint temporarily
    op.drop_constraint("scorecardresult_pkey", "scorecardresult", type_="primary")

    # 2. Alter the column type back from TEXT to INTEGER
    op.alter_column(
        "scorecardresult",
        "result_id",
        type_=sa.Integer(),
        existing_type=sa.Text(),
        postgresql_using="result_id::integer"
    )

    # 3. Re-create the primary key constraint
    op.create_primary_key("scorecardresult_pkey", "scorecardresult", ["result_id"])
