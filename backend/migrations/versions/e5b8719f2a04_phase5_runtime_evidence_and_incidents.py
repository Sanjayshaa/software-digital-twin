"""phase5_runtime_evidence_and_incidents

Revision ID: e5b8719f2a04
Revises: 92d510a512f1
Create Date: 2026-09-27 14:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b8719f2a04'
down_revision: Union[str, Sequence[str], None] = '92d510a512f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend incidents table
    op.add_column('incidents', sa.Column('repository_id', sa.String(length=36), nullable=True))
    op.add_column('incidents', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.add_column('incidents', sa.Column('environment', sa.String(length=50), server_default='production', nullable=False))
    op.add_column('incidents', sa.Column('affected_component_id', sa.String(length=128), nullable=True))
    op.add_column('incidents', sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=False))

    op.create_index(op.f('ix_incidents_repository_id'), 'incidents', ['repository_id'], unique=False)
    op.create_index(op.f('ix_incidents_snapshot_id'), 'incidents', ['snapshot_id'], unique=False)
    op.create_index(op.f('ix_incidents_environment'), 'incidents', ['environment'], unique=False)
    op.create_index(op.f('ix_incidents_affected_component_id'), 'incidents', ['affected_component_id'], unique=False)

    op.create_foreign_key('fk_incidents_repository_id', 'incidents', 'repositories', ['repository_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_incidents_snapshot_id', 'incidents', 'repository_snapshots', ['snapshot_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_incidents_affected_component_id', 'incidents', 'structural_artifacts', ['affected_component_id'], ['id'], ondelete='SET NULL')

    # 2. Extend runtime_events table
    op.add_column('runtime_events', sa.Column('repository_id', sa.String(length=36), nullable=True))
    op.add_column('runtime_events', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.add_column('runtime_events', sa.Column('incident_id', sa.String(length=36), nullable=True))
    op.add_column('runtime_events', sa.Column('service_name', sa.String(length=255), nullable=True))
    op.add_column('runtime_events', sa.Column('component_artifact_id', sa.String(length=128), nullable=True))
    op.add_column('runtime_events', sa.Column('severity', sa.String(length=50), server_default='INFO', nullable=False))
    op.add_column('runtime_events', sa.Column('environment', sa.String(length=50), server_default='production', nullable=False))
    op.add_column('runtime_events', sa.Column('trace_id', sa.String(length=128), nullable=True))
    op.add_column('runtime_events', sa.Column('span_id', sa.String(length=128), nullable=True))
    op.add_column('runtime_events', sa.Column('message', sa.Text(), nullable=True))

    op.create_index(op.f('ix_runtime_events_repository_id'), 'runtime_events', ['repository_id'], unique=False)
    op.create_index(op.f('ix_runtime_events_snapshot_id'), 'runtime_events', ['snapshot_id'], unique=False)
    op.create_index(op.f('ix_runtime_events_incident_id'), 'runtime_events', ['incident_id'], unique=False)
    op.create_index(op.f('ix_runtime_events_service_name'), 'runtime_events', ['service_name'], unique=False)
    op.create_index(op.f('ix_runtime_events_component_artifact_id'), 'runtime_events', ['component_artifact_id'], unique=False)
    op.create_index(op.f('ix_runtime_events_severity'), 'runtime_events', ['severity'], unique=False)
    op.create_index(op.f('ix_runtime_events_environment'), 'runtime_events', ['environment'], unique=False)
    op.create_index(op.f('ix_runtime_events_trace_id'), 'runtime_events', ['trace_id'], unique=False)
    op.create_index(op.f('ix_runtime_events_timestamp'), 'runtime_events', ['timestamp'], unique=False)

    op.create_foreign_key('fk_runtime_events_repository_id', 'runtime_events', 'repositories', ['repository_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_runtime_events_snapshot_id', 'runtime_events', 'repository_snapshots', ['snapshot_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_runtime_events_incident_id', 'runtime_events', 'incidents', ['incident_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_runtime_events_component_artifact_id', 'runtime_events', 'structural_artifacts', ['component_artifact_id'], ['id'], ondelete='SET NULL')

    # 3. Create incident_evidence_links table
    op.create_table(
        'incident_evidence_links',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('incident_id', sa.String(length=36), nullable=False),
        sa.Column('link_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=128), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_incident_evidence_links_incident_id'), 'incident_evidence_links', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_evidence_links_link_type'), 'incident_evidence_links', ['link_type'], unique=False)
    op.create_index(op.f('ix_incident_evidence_links_target_id'), 'incident_evidence_links', ['target_id'], unique=False)


def downgrade() -> None:
    # 3. Drop incident_evidence_links table
    op.drop_index(op.f('ix_incident_evidence_links_target_id'), table_name='incident_evidence_links')
    op.drop_index(op.f('ix_incident_evidence_links_link_type'), table_name='incident_evidence_links')
    op.drop_index(op.f('ix_incident_evidence_links_incident_id'), table_name='incident_evidence_links')
    op.drop_table('incident_evidence_links')

    # 2. Revert runtime_events table
    op.drop_constraint('fk_runtime_events_component_artifact_id', 'runtime_events', type_='foreignkey')
    op.drop_constraint('fk_runtime_events_incident_id', 'runtime_events', type_='foreignkey')
    op.drop_constraint('fk_runtime_events_snapshot_id', 'runtime_events', type_='foreignkey')
    op.drop_constraint('fk_runtime_events_repository_id', 'runtime_events', type_='foreignkey')

    op.drop_index(op.f('ix_runtime_events_timestamp'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_trace_id'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_environment'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_severity'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_component_artifact_id'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_service_name'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_incident_id'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_snapshot_id'), table_name='runtime_events')
    op.drop_index(op.f('ix_runtime_events_repository_id'), table_name='runtime_events')

    op.drop_column('runtime_events', 'message')
    op.drop_column('runtime_events', 'span_id')
    op.drop_column('runtime_events', 'trace_id')
    op.drop_column('runtime_events', 'environment')
    op.drop_column('runtime_events', 'severity')
    op.drop_column('runtime_events', 'component_artifact_id')
    op.drop_column('runtime_events', 'service_name')
    op.drop_column('runtime_events', 'incident_id')
    op.drop_column('runtime_events', 'snapshot_id')
    op.drop_column('runtime_events', 'repository_id')

    # 1. Revert incidents table
    op.drop_constraint('fk_incidents_affected_component_id', 'incidents', type_='foreignkey')
    op.drop_constraint('fk_incidents_snapshot_id', 'incidents', type_='foreignkey')
    op.drop_constraint('fk_incidents_repository_id', 'incidents', type_='foreignkey')

    op.drop_index(op.f('ix_incidents_affected_component_id'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_environment'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_snapshot_id'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_repository_id'), table_name='incidents')

    op.drop_column('incidents', 'metadata_payload')
    op.drop_column('incidents', 'affected_component_id')
    op.drop_column('incidents', 'environment')
    op.drop_column('incidents', 'snapshot_id')
    op.drop_column('incidents', 'repository_id')
