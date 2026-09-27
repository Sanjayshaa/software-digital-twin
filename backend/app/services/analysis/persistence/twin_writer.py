import uuid
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.services.discovery.scanner import FileInventory
from app.services.analysis.runtime.result import AnalysisRunResult, ArtifactType, ExtractedArtifact
from app.services.analysis.normalizers.identity import build_artifact_id
from app.models.entities import (
    Repository,
    RepositorySnapshot,
    File as FileModel,
    StructuralArtifact as StructuralArtifactModel,
    ArtifactRelationship as ArtifactRelationshipModel,
    Evidence as EvidenceModel,
    AnalysisRun as AnalysisRunModel,
)


class TwinPersistenceWriter:
    """Idempotently writes snapshots, files, structural artifacts, relationships, and evidence to PostgreSQL."""

    def write_twin(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: str,
        inventory: FileInventory,
        result: AnalysisRunResult,
        commit_hash: str = "HEAD",
        branch_name: str = "main",
    ) -> AnalysisRunModel:
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository '{repository_id}' does not exist.")

        # 1. Upsert RepositorySnapshot
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id).first()
        if not snapshot:
            snapshot = RepositorySnapshot(
                id=snapshot_id,
                repository_id=repository_id,
                commit_hash=commit_hash,
                branch_name=branch_name,
                total_files=inventory.total_files,
                total_symbols=len(result.artifacts),
                snapshot_metadata={
                    "total_lines": inventory.total_lines,
                    "analyzers": result.analyzer_names,
                },
            )
            db.add(snapshot)
            db.flush()
        else:
            snapshot.total_files = inventory.total_files
            snapshot.total_symbols = len(result.artifacts)

        # 2. Upsert Source Files
        file_record_map: Dict[str, str] = {}
        for sf in inventory.files:
            file_rec = db.query(FileModel).filter_by(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                path=sf.relative_path
            ).first()

            if not file_rec:
                file_rec = FileModel(
                    repository_id=repository_id,
                    snapshot_id=snapshot_id,
                    path=sf.relative_path,
                    file_name=sf.file_name,
                    extension=sf.extension,
                    language=None,
                    line_count=sf.line_count,
                    is_test="test" in sf.relative_path.lower(),
                )
                db.add(file_rec)
                db.flush()
            file_record_map[sf.relative_path] = file_rec.id

        # 3. Idempotently write Structural Artifacts
        qual_to_id_map: Dict[str, str] = {}
        for art in result.artifacts:
            file_id = file_record_map.get(art.file_path)
            existing_art = db.query(StructuralArtifactModel).filter_by(id=art.id).first()
            if not existing_art:
                db_art = StructuralArtifactModel(
                    id=art.id,
                    repository_id=repository_id,
                    snapshot_id=snapshot_id,
                    file_id=file_id,
                    artifact_type=art.artifact_type.value,
                    language=art.language,
                    name=art.name,
                    qualified_name=art.qualified_name,
                    signature=art.signature,
                    docstring=art.docstring,
                    location=f"{art.file_path}:{art.line_start or 1}",
                    line_start=art.line_start,
                    line_end=art.line_end,
                    analyzer_source=art.analyzer_source,
                    confidence=art.confidence,
                    metadata_payload=art.metadata,
                )
                db.add(db_art)
            qual_to_id_map[art.qualified_name] = art.id

        db.flush()

        for art in result.artifacts:
            qual_to_id_map[art.id] = art.id

        # 4. Idempotently write Artifact Relationships
        for rel in result.relationships:
            src_id = qual_to_id_map.get(rel.source_qualified_name)
            if not src_id:
                src_art = db.query(StructuralArtifactModel).filter_by(id=rel.source_qualified_name).first()
                if src_art:
                    src_id = src_art.id
                else:
                    src_id = build_artifact_id(
                        snapshot_id=snapshot_id,
                        language="generic",
                        file_path="<source>",
                        artifact_type=ArtifactType.PACKAGE.value,
                        qualified_name=rel.source_qualified_name,
                    )
                    src_rec = db.query(StructuralArtifactModel).filter_by(id=src_id).first()
                    if not src_rec:
                        src_rec = StructuralArtifactModel(
                            id=src_id,
                            repository_id=repository_id,
                            snapshot_id=snapshot_id,
                            file_id=None,
                            artifact_type=ArtifactType.PACKAGE.value,
                            language="generic",
                            name=rel.source_qualified_name.split(".")[-1],
                            qualified_name=rel.source_qualified_name,
                            location="<source>",
                            analyzer_source="source_resolver",
                            confidence=1.0,
                            metadata_payload={"inferred": True},
                        )
                        db.add(src_rec)
                        db.flush()
                        result.artifacts.append(ExtractedArtifact(
                            id=src_id,
                            artifact_type=ArtifactType.PACKAGE,
                            language="generic",
                            name=rel.source_qualified_name.split(".")[-1],
                            qualified_name=rel.source_qualified_name,
                            file_path="<source>",
                            line_start=1,
                            line_end=1,
                            analyzer_source="source_resolver",
                            confidence=1.0,
                            metadata={"inferred": True},
                        ))
                    qual_to_id_map[rel.source_qualified_name] = src_id

            tgt_id = qual_to_id_map.get(rel.target_qualified_name)
            if not tgt_id:
                tgt_art = db.query(StructuralArtifactModel).filter_by(id=rel.target_qualified_name).first()
                if tgt_art:
                    tgt_id = tgt_art.id
                else:
                    tgt_id = build_artifact_id(
                        snapshot_id=snapshot_id,
                        language="external",
                        file_path="<external>",
                        artifact_type=ArtifactType.EXTERNAL_DEPENDENCY.value,
                        qualified_name=rel.target_qualified_name,
                    )
                    ext_rec = db.query(StructuralArtifactModel).filter_by(id=tgt_id).first()
                    if not ext_rec:
                        ext_rec = StructuralArtifactModel(
                            id=tgt_id,
                            repository_id=repository_id,
                            snapshot_id=snapshot_id,
                            file_id=None,
                            artifact_type=ArtifactType.EXTERNAL_DEPENDENCY.value,
                            language="external",
                            name=rel.target_qualified_name.split(".")[-1],
                            qualified_name=rel.target_qualified_name,
                            location="<external>",
                            analyzer_source="external_dependency_resolver",
                            confidence=1.0,
                            metadata_payload={"external": True},
                        )
                        db.add(ext_rec)
                        db.flush()
                        result.artifacts.append(ExtractedArtifact(
                            id=tgt_id,
                            artifact_type=ArtifactType.EXTERNAL_DEPENDENCY,
                            language="external",
                            name=rel.target_qualified_name.split(".")[-1],
                            qualified_name=rel.target_qualified_name,
                            file_path="<external>",
                            line_start=1,
                            line_end=1,
                            analyzer_source="external_dependency_resolver",
                            confidence=1.0,
                            metadata={"external": True},
                        ))
                    qual_to_id_map[rel.target_qualified_name] = tgt_id

            if src_id and tgt_id:
                existing_rel = db.query(ArtifactRelationshipModel).filter_by(id=rel.id).first()
                if not existing_rel:
                    db_rel = ArtifactRelationshipModel(
                        id=rel.id,
                        repository_id=repository_id,
                        snapshot_id=snapshot_id,
                        source_artifact_id=src_id,
                        target_artifact_id=tgt_id,
                        relationship_type=rel.relationship_type.value,
                        confidence=rel.confidence,
                        detection_method=rel.detection_method,
                        source_location=rel.source_location,
                        metadata_payload=rel.metadata,
                    )
                    db.add(db_rel)

        # 5. Write AnalysisRun
        analysis_run = AnalysisRunModel(
            id=result.run_id,
            project_id=repo.project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            run_type="structural_digital_twin",
            status=result.status,
            analyzer_names=result.analyzer_names,
            files_scanned=result.files_scanned,
            artifacts_created=len(result.artifacts),
            relationships_created=len(result.relationships),
            warnings=result.warnings,
            errors=result.errors,
            summary=result.summary,
            created_at=result.started_at,
            completed_at=result.completed_at,
        )
        db.add(analysis_run)
        db.flush()

        # 6. Write Evidence linked to AnalysisRun
        for ev in result.evidence_items:
            db.add(EvidenceModel(
                project_id=repo.project_id,
                analysis_run_id=analysis_run.id,
                source_type="DIRECT",
                source_reference=ev.source_reference,
                description=ev.description,
                confidence=ev.confidence,
                payload=ev.payload,
            ))

        db.commit()
        return analysis_run


twin_writer = TwinPersistenceWriter()
