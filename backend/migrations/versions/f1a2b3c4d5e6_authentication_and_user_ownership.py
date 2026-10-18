"""authentication_and_user_ownership

Revision ID: f1a2b3c4d5e6
Revises: e5b8719f2a04
Create Date: 2026-10-03 01:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5b8719f2a04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='engineer', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Add owner_id to repositories
    op.add_column('repositories', sa.Column('owner_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_repositories_owner_id'), 'repositories', ['owner_id'], unique=False)
    op.create_foreign_key(
        'fk_repositories_owner_id_users',
        'repositories', 'users',
        ['owner_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_repositories_owner_id_users', 'repositories', type_='foreignkey')
    op.drop_index(op.f('ix_repositories_owner_id'), table_name='repositories')
    op.drop_column('repositories', 'owner_id')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
