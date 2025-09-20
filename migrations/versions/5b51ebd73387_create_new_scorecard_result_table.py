"""create scorecardresult table

Revision ID: 5b51ebd73387
Revises: 0844758a423b
Create Date: 2025-09-20 15:51:25.891429
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5b51ebd73387'
down_revision = '0844758a423b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old table if it exists (safe for SQLite and Postgres)
    op.execute("DROP TABLE IF EXISTS scorecardresult")

    # Create new scorecardresult table
    op.create_table(
        'scorecardresult',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('result_id', sa.String, nullable=False, unique=True),
        sa.Column('account_unique_id', sa.String, sa.ForeignKey('account.account_unique_id')),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('first_name', sa.String, nullable=True),
        sa.Column('last_name', sa.String, nullable=True),
        sa.Column('email', sa.String, nullable=True),
        sa.Column('key', sa.String, nullable=False),
        sa.Column('report_url', sa.String, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('scorecardresult')
