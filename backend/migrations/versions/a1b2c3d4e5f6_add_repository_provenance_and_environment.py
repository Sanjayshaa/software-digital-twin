"""add_repository_provenance_and_environment

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-10-04 03:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add source_type column
    op.add_column('repositories', sa.Column('source_type', sa.String(length=50), server_default='LOCAL', nullable=False))
    
    # 2. Add environment column
    op.add_column('repositories', sa.Column('environment', sa.String(length=50), server_default='USER', nullable=False))
    op.create_index(op.f('ix_repositories_environment'), 'repositories', ['environment'], unique=False)

    # 3. Classify existing polluted test/fixture rows to FIXTURE
    op.execute("""
        UPDATE repositories
        SET environment = 'FIXTURE'
        WHERE local_path LIKE '/tmp/%'
           OR local_path LIKE '/private/var/%'
           OR name LIKE 'controlled-repo-%'
           OR name LIKE 'empty-repo-%'
           OR name LIKE 'foreign_repo_%'
           OR name LIKE 'arch-api-repo-%'
           OR name LIKE 'arch-test-repo-%'
           OR name LIKE 'real-repo-%'
           OR name LIKE 'r1-%'
           OR name LIKE 'r2-%'
           OR name LIKE 'repo_a_%'
           OR name LIKE 'repo_b_%'
           OR name = 'polyglot_microservice';
    """)

    # 4. Classify GitHub repositories based on remote_url
    op.execute("""
        UPDATE repositories
        SET source_type = 'GITHUB'
        WHERE remote_url IS NOT NULL AND remote_url != '';
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_repositories_environment'), table_name='repositories')
    op.drop_column('repositories', 'environment')
    op.drop_column('repositories', 'source_type')
