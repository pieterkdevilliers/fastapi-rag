from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "db9ca40feb2a"
down_revision = "7f16f5251cda"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old primary key (on "id")
    op.drop_constraint("scorecardresult_pkey", "scorecardresult", type_="primary")

    # Drop the old id column
    op.drop_column("scorecardresult", "id")

    # Make result_id the new primary key
    op.create_primary_key("scorecardresult_pkey", "scorecardresult", ["result_id"])


def downgrade():
    # Drop the PK on result_id
    op.drop_constraint("scorecardresult_pkey", "scorecardresult", type_="primary")

    # Recreate the id column
    op.add_column(
        "scorecardresult",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    )

    # Add back the primary key on id
    op.create_primary_key("scorecardresult_pkey", "scorecardresult", ["id"])
