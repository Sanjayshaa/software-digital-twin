"""add_pull_request_records

Revision ID: 002_add_pull_request_records
Revises: 001_widen_columns
Create Date: 2026-11-03 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_pull_request_records'
down_revision: Union[str, Sequence[str], None] = '001_widen_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pull_request_records',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('delivery_id', sa.String(length=128), unique=True, nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='github'),
        sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_repository', sa.String(length=255), nullable=True),
        sa.Column('pull_request_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('sender', sa.String(length=255), nullable=True),
        sa.Column('base_branch', sa.String(length=255), nullable=False),
        sa.Column('base_commit_sha', sa.String(length=64), nullable=False),
        sa.Column('head_branch', sa.String(length=255), nullable=False),
        sa.Column('head_commit_sha', sa.String(length=64), nullable=False),
        sa.Column('base_snapshot_id', sa.String(length=36), sa.ForeignKey('repository_snapshots.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_snapshot_id', sa.String(length=36), sa.ForeignKey('repository_snapshots.id', ondelete='SET NULL'), nullable=True),
        sa.Column('analysis_run_id', sa.String(length=36), sa.ForeignKey('analysis_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='QUEUED'),
        sa.Column('ci_recommendation', sa.String(length=50), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('report_markdown', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_pull_request_records_delivery_id', 'pull_request_records', ['delivery_id'])
    op.create_index('ix_pull_request_records_repository_id', 'pull_request_records', ['repository_id'])
    op.create_index('ix_pull_request_records_pull_request_number', 'pull_request_records', ['pull_request_number'])


def downgrade() -> None:
    op.drop_index('ix_pull_request_records_pull_request_number', table_name='pull_request_records')
    op.drop_index('ix_pull_request_records_repository_id', table_name='pull_request_records')
    op.drop_index('ix_pull_request_records_delivery_id', table_name='pull_request_records')
    op.drop_table('pull_request_records')
