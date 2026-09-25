import uuid
from sqlalchemy.orm import Session
from app.models.entities import (
    Project,
    Repository,
    Service,
    APIEndpoint,
    CodeSymbol,
    File,
    Dependency,
    Test,
    Change,
    RiskAssessment,
)


def test_create_and_query_project_hierarchy(db_session: Session):
    unique_suffix = str(uuid.uuid4())[:8]
    project_name = f"Test-Project-{unique_suffix}"

    # 1. Create Project
    project = Project(
        name=project_name,
        description="Engineering verification project for Digital Twin"
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    assert project.id is not None
    assert project.name == project_name

    # 2. Create Repository
    repo = Repository(
        project_id=project.id,
        name=f"repo-{unique_suffix}",
        local_path=f"/tmp/repos/{unique_suffix}",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    assert repo.id is not None
    assert repo.project_id == project.id

    # 3. Create File & CodeSymbol
    file_record = File(
        repository_id=repo.id,
        path="src/payment_service.py",
        file_name="payment_service.py",
        extension=".py",
        language="python",
        line_count=120,
        is_test=False
    )
    db_session.add(file_record)
    db_session.commit()
    db_session.refresh(file_record)

    symbol = CodeSymbol(
        file_id=file_record.id,
        name="process_payment",
        symbol_type="function",
        signature="def process_payment(amount: float) -> bool",
        start_line=10,
        end_line=25,
        is_exported=True
    )
    db_session.add(symbol)
    db_session.commit()
    db_session.refresh(symbol)

    # 4. Create Service & APIEndpoint
    service = Service(
        project_id=project.id,
        name="payment-service",
        service_type="backend_service",
        runtime="python",
        root_directory="services/payment"
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    endpoint = APIEndpoint(
        service_id=service.id,
        file_id=file_record.id,
        symbol_id=symbol.id,
        route_path="/api/v1/payments",
        http_method="POST",
        description="Process payment charge"
    )
    db_session.add(endpoint)
    db_session.commit()
    db_session.refresh(endpoint)

    # 5. Create Dependency edge
    dep = Dependency(
        project_id=project.id,
        source_type="service",
        source_id=service.id,
        target_type="symbol",
        target_id=symbol.id,
        relation_type="CALLS",
        weight=1.0,
        metadata_payload={"protocol": "in_process"}
    )
    db_session.add(dep)
    db_session.commit()
    db_session.refresh(dep)

    # 6. Verify associations
    queried_project = db_session.query(Project).filter_by(id=project.id).first()
    assert len(queried_project.repositories) == 1
    assert len(queried_project.services) == 1
    assert len(queried_project.services[0].api_endpoints) == 1

    # Cleanup
    db_session.delete(queried_project)
    db_session.commit()
