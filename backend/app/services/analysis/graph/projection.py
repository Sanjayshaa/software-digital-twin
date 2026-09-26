import networkx as nx
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.analysis.query.twin_query_service import twin_query_service
from app.models.entities import StructuralArtifact, ArtifactRelationship


class TwinGraphProjection:
    """Projects persisted PostgreSQL Digital Twin data into a NetworkX MultiDiGraph on demand."""

    def build_graph(self, db: Session, snapshot_id: str) -> nx.MultiDiGraph:
        """
        Deterministically constructs a directed multi-graph from PostgreSQL artifacts and relationships.
        Never makes in-memory graph the only source of truth.
        """
        graph = nx.MultiDiGraph(snapshot_id=snapshot_id)

        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id).all()

        # Add Nodes
        for art in artifacts:
            graph.add_node(
                art.id,
                artifact_type=art.artifact_type,
                language=art.language,
                name=art.name,
                qualified_name=art.qualified_name,
                location=art.location,
                confidence=art.confidence,
                analyzer_source=art.analyzer_source,
            )

        # Add Directed Edges
        for rel in relationships:
            graph.add_edge(
                rel.source_artifact_id,
                rel.target_artifact_id,
                key=rel.id,
                relationship_type=rel.relationship_type,
                confidence=rel.confidence,
                detection_method=rel.detection_method,
                source_location=rel.source_location,
            )

        return graph

    def get_subgraph_for_artifact(
        self,
        graph: nx.MultiDiGraph,
        artifact_id: str,
        depth: int = 2
    ) -> nx.MultiDiGraph:
        """Extracts ego-network neighborhood around an artifact."""
        if artifact_id not in graph:
            return nx.MultiDiGraph()
        nodes = {artifact_id}
        current_layer = {artifact_id}
        for _ in range(depth):
            next_layer = set()
            for n in current_layer:
                next_layer.update(graph.successors(n))
                next_layer.update(graph.predecessors(n))
            nodes.update(next_layer)
            current_layer = next_layer
        return graph.subgraph(nodes).copy()


    def project_to_networkx(self, db: Session, snapshot_id: str) -> nx.MultiDiGraph:
        """Alias for build_graph."""
        return self.build_graph(db, snapshot_id)

    def get_graph_summary(self, db: Session, snapshot_id: str) -> Dict[str, Any]:
        """Returns node and edge summary for snapshot."""
        g = self.build_graph(db, snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
        }


twin_graph_projection = TwinGraphProjection()
graph_projection_service = twin_graph_projection
