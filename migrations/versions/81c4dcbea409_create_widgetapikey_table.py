"""create_widgetapikey_table

Revision ID: 81c4dcbea409
Revises: 739a0a2e8209
Create Date: 2025-05-29 16:07:20.756092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '81c4dcbea409'
down_revision: Union[str, None] = '739a0a2e8209'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('widgetapikey',
        sa.Column('account_unique_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False), # Or sa.String
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=True), # Or sa.String
        sa.Column('display_prefix', sqlmodel.sql.sqltypes.AutoString(), nullable=True), # Or sa.String
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False), # Or sa.String
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('allowed_origins', sa.JSON(), nullable=False), # Default factory in model handles Python side

        sa.ForeignKeyConstraint(['account_unique_id'], ['account.account_unique_id'], name=op.f('fk_widgetapikey_account_unique_id_account')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_widgetapikey')),
        sa.UniqueConstraint('api_key_hash', name=op.f('uq_widgetapikey_api_key_hash'))
    )
    op.create_index(op.f('ix_widgetapikey_account_unique_id'), 'widgetapikey', ['account_unique_id'], unique=False)
    # api_key_hash unique constraint already creates an index typically.
    if op.get_bind().dialect.name != 'sqlite': 
         op.create_index(op.f('ix_widgetapikey_display_prefix'), 'widgetapikey', ['display_prefix'], unique=False)


def downgrade() -> None:
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_index(op.f('ix_widgetapikey_display_prefix'), table_name='widgetapikey')
    op.drop_index(op.f('ix_widgetapikey_account_unique_id'), table_name='widgetapikey')
    op.drop_table('widgetapikey')
