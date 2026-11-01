"""widen_artifact_and_symbol_columns

Revision ID: 001_widen_columns
Revises: 
Create Date: 2026-10-30 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_widen_columns'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen column definitions to accommodate long qualified identifiers and file paths."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # structural_artifacts
        op.alter_column('structural_artifacts', 'name',
                        type_=sa.String(length=512),
                        existing_type=sa.String(length=255),
                        existing_nullable=False)
        op.alter_column('structural_artifacts', 'qualified_name',
                        type_=sa.String(length=2048),
                        existing_type=sa.String(length=255),
                        existing_nullable=False)
        op.alter_column('structural_artifacts', 'location',
                        type_=sa.String(length=2048),
                        existing_type=sa.String(length=255),
                        existing_nullable=True)

        # code_symbols
        op.alter_column('code_symbols', 'name',
                        type_=sa.String(length=512),
                        existing_type=sa.String(length=255),
                        existing_nullable=False)
        op.alter_column('code_symbols', 'qualified_name',
                        type_=sa.String(length=2048),
                        existing_type=sa.String(length=255),
                        existing_nullable=False)

        # artifact_relationships
        op.alter_column('artifact_relationships', 'source_location',
                        type_=sa.String(length=2048),
                        existing_type=sa.String(length=255),
                        existing_nullable=True)

        # files
        op.alter_column('files', 'path',
                        type_=sa.String(length=2048),
                        existing_type=sa.String(length=255),
                        existing_nullable=False)


def downgrade() -> None:
    """Revert column definitions back to 255 chars if necessary."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.alter_column('files', 'path',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=2048),
                        existing_nullable=False)
        op.alter_column('artifact_relationships', 'source_location',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=2048),
                        existing_nullable=True)
        op.alter_column('code_symbols', 'qualified_name',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=2048),
                        existing_nullable=False)
        op.alter_column('code_symbols', 'name',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=512),
                        existing_nullable=False)
        op.alter_column('structural_artifacts', 'location',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=2048),
                        existing_nullable=True)
        op.alter_column('structural_artifacts', 'qualified_name',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=2048),
                        existing_nullable=False)
        op.alter_column('structural_artifacts', 'name',
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=512),
                        existing_nullable=False)

