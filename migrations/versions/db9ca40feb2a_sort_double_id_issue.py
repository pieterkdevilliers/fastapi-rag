from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic
revision = "db9ca40feb2a"
down_revision = "7f16f5251cda"
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    columns = [c['name'] for c in inspector.get_columns('scorecardresult')]

    # Drop the old primary key if it exists
    if 'id' in columns:
        op.drop_constraint("scorecardresult_pkey", "scorecardresult", type_="primary")
        op.drop_column("scorecardresult", "id")

    # Make result_id the new primary key
    existing_pkeys = [c['name'] for c in inspector.get_pk_constraint('scorecardresult')['constrained_columns']]
    if 'result_id' not in existing_pkeys:
        op.create_primary_key("scorecardresult_pkey", "scorecardresult", ["result_id"])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('scorecardresult')]

    # Drop PK on result_id if it exists
    existing_pkeys = [c['name'] for c in inspector.get_pk_constraint('scorecardresult')['constrained_columns']]
    if 'result_id' in existing_pkeys:
        op.drop_constraint("scorecardresult_pkey", "scorecardresult", type_="primary")

    # Recreate id column if missing
    if 'id' not in columns:
        op.add_column(
            "scorecardresult",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        )

    # Add back primary key on id
    existing_pkeys = [c['name'] for c in inspector.get_pk_constraint('scorecardresult')['constrained_columns']]
    if 'id' not in existing_pkeys:
        op.create_primary_key("scorecardresult_pkey", "scorecardresult", ["id"])
