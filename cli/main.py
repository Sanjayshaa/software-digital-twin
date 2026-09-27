import os
import sys
from typing import Optional

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from app.services.discovery.engine import discovery_engine

app = typer.Typer(
    name="digital-twin",
    help="AI-Powered Software Digital Twin Engineering CLI",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main_callback():
    """AI-Powered Software Digital Twin - Engineering Intelligence Suite."""
    pass


@app.command("version")
def version():
    """Print the Digital Twin version."""
    console.print("[bold cyan]digital-twin[/bold cyan] version 0.1.0")


@app.command("discover")
def discover(

    repo_path: str = typer.Argument(".", help="Path to software repository to discover"),
):
    """
    Scans a software repository and executes the Software Project Discovery & Intelligence Brain.
    Produces deterministic project profiles, capability detection, and analysis plans.
    """
    abs_path = os.path.abspath(repo_path)
    if not os.path.exists(abs_path):
        console.print(f"[bold red]Error:[/bold red] Path '{repo_path}' does not exist.")
        raise typer.Exit(code=1)

    console.print()
    console.print(Panel(
        f"[bold cyan]PROJECT DISCOVERY & INTELLIGENCE BRAIN[/bold cyan]\n"
        f"[dim]Deterministic Scanning, Technology Profiling & Capability Planning[/dim]\n"
        f"Target Repository: [green]{abs_path}[/green]",
        border_style="cyan"
    ))

    try:
        profile, plan = discovery_engine.discover(abs_path)
    except Exception as e:
        console.print(f"[bold red]Discovery Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    # 1. Overview Table
    metrics_table = Table(title="Repository Inventory", border_style="dim")
    metrics_table.add_column("Total Files Scanned", justify="center", style="bold")
    metrics_table.add_column("Total Lines of Code", justify="center", style="bold")
    metrics_table.add_column("Primary Language", justify="center", style="cyan")
    metrics_table.add_column("Total Analysis Steps Planned", justify="center", style="magenta")

    primary_lang = profile.languages[0].name if profile.languages else "none"
    metrics_table.add_row(
        str(profile.total_files_scanned),
        str(profile.total_lines_of_code),
        primary_lang,
        str(plan.total_steps),
    )
    console.print(metrics_table)
    console.print()

    # 2. Languages Table
    lang_table = Table(title="Detected Languages", border_style="cyan")
    lang_table.add_column("Language", style="bold")
    lang_table.add_column("Lines", justify="right")
    lang_table.add_column("% Codebase", justify="right")
    lang_table.add_column("Confidence", justify="center")
    lang_table.add_column("Capability Level", justify="center")
    lang_table.add_column("Evidence", style="dim")

    for l in profile.languages:
        ev_sample = l.evidence[0].snippet if l.evidence else "extension match"
        lang_table.add_row(
            l.name,
            str(l.line_count),
            f"{l.percentage}%",
            f"{l.confidence * 100:.0f}%",
            f"Level {l.capability_level}",
            ev_sample,
        )
    console.print(lang_table)
    console.print()

    # 3. Technologies & Frameworks Table
    tech_table = Table(title="Detected Frameworks, Build & Data Systems", border_style="green")
    tech_table.add_column("Category", style="bold")
    tech_table.add_column("Technology", style="cyan")
    tech_table.add_column("Version", justify="center")
    tech_table.add_column("Status", justify="center")
    tech_table.add_column("Evidence Source", style="dim")

    for fw in profile.frameworks:
        ev = fw.evidence[0].snippet if fw.evidence else ""
        tech_table.add_row("Framework", fw.name, fw.version or "detected", f"[bold green]{fw.detection_status.value}[/bold green]", ev)

    for bm in profile.build_systems:
        ev = bm.evidence[0].snippet if bm.evidence else ""
        tech_table.add_row("Build System", bm.name, "-", "[bold green]OBSERVED[/bold green]", ev)

    for pm in profile.package_managers:
        ev = pm.evidence[0].snippet if pm.evidence else ""
        tech_table.add_row("Package Manager", pm.name, "-", "[bold green]OBSERVED[/bold green]", ev)

    for db in profile.databases:
        ev = db.evidence[0].snippet if db.evidence else ""
        color = "green" if db.detection_status.value == "OBSERVED" else "yellow"
        tech_table.add_row(f"Database ({db.category})", db.name, "-", f"[bold {color}]{db.detection_status.value}[/bold {color}]", ev)

    for api in profile.api_technologies:
        ev = api.evidence[0].snippet if api.evidence else ""
        tech_table.add_row("API Technology", api.name, "-", "[bold green]OBSERVED[/bold green]", ev)

    for tf in profile.testing_frameworks:
        ev = tf.evidence[0].snippet if tf.evidence else ""
        tech_table.add_row("Testing Framework", tf.name, "-", "[bold green]OBSERVED[/bold green]", ev)

    for inf in profile.infrastructure:
        ev = inf.evidence[0].snippet if inf.evidence else ""
        tech_table.add_row("Infrastructure", inf.name, "-", "[bold green]OBSERVED[/bold green]", ev)

    console.print(tech_table)
    console.print()

    # 4. Architecture Signals
    if profile.architecture_signals:
        arch_table = Table(title="Architecture Signals (Evidence-Based)", border_style="yellow")
        arch_table.add_column("Signal", style="bold yellow")
        arch_table.add_column("Confidence", justify="center")
        arch_table.add_column("Summary")
        for s in profile.architecture_signals:
            arch_table.add_row(
                s.signal,
                f"{s.confidence * 100:.0f}%",
                s.summary,
            )
        console.print(arch_table)
        console.print()

    # 5. Analysis Plan
    plan_table = Table(title="Deterministic Analysis Plan", border_style="magenta")
    plan_table.add_column("#", justify="center", style="bold")
    plan_table.add_column("Step Name", style="bold")
    plan_table.add_column("Target Tech", style="cyan")
    plan_table.add_column("Analyzer", style="dim")
    plan_table.add_column("Level", justify="center")
    plan_table.add_column("Objective", style="dim")

    for s in plan.steps:
        plan_table.add_row(
            str(s.step_number),
            s.step_name,
            s.target_technology,
            s.analyzer_name,
            f"L{s.capability_level}",
            s.description,
        )
    console.print(plan_table)
    console.print()


@app.command("analyze")
def analyze(
    repo_path: str = typer.Argument(".", help="Path to software repository to analyze"),
    commit_hash: str = typer.Option("HEAD", "--commit", "-c", help="Commit hash for snapshot"),
    branch_name: str = typer.Option("main", "--branch", "-b", help="Branch name"),
    baseline: Optional[str] = typer.Option(None, "--baseline", "-B", help="Path to architecture baseline YAML"),
):
    """
    Executes Phase 3 Structural Intelligence & Digital Twin Builder.
    Parses code with Tree-sitter, extracts artifacts & relationships, and builds a snapshot-aware Twin.
    """
    from app.core.database import SessionLocal
    from app.models.entities import Project, Repository
    from app.services.analysis.engine import structural_twin_engine

    abs_path = os.path.abspath(repo_path)
    if not os.path.exists(abs_path):
        console.print(f"[bold red]Error:[/bold red] Path '{repo_path}' does not exist.")
        raise typer.Exit(code=1)

    repo_name = os.path.basename(abs_path.rstrip("/\\")) or "repo"

    console.print()
    console.print(Panel(
        f"[bold magenta]DIGITAL TWIN STRUCTURAL INTELLIGENCE & BUILDER[/bold magenta]\n"
        f"[dim]Deterministic AST Parsing, Snapshot Modeling & Relationship Graph[/dim]\n"
        f"Target Repository: [green]{abs_path}[/green] | Commit: [cyan]{commit_hash}[/cyan] | Branch: [cyan]{branch_name}[/cyan]",
        border_style="magenta"
    ))

    db = SessionLocal()
    try:
        # Find or create Project & Repository records for CLI run
        proj = db.query(Project).filter_by(name=f"CLI-{repo_name}").first()
        if not proj:
            proj = Project(name=f"CLI-{repo_name}", description="Project created via CLI analyze")
            db.add(proj)
            db.commit()
            db.refresh(proj)

        repo = db.query(Repository).filter_by(local_path=abs_path).first()
        if not repo:
            repo = Repository(
                project_id=proj.id,
                name=repo_name,
                local_path=abs_path,
                default_branch=branch_name,
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)

        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash=commit_hash,
            branch_name=branch_name,
        )

        # Print Execution Table
        summary_table = Table(title="Digital Twin Analysis Summary", border_style="cyan")
        summary_table.add_column("Metric", style="bold")
        summary_table.add_column("Value", style="green")

        summary_table.add_row("Repository", repo_name)
        summary_table.add_row("Snapshot ID", snapshot_id)
        summary_table.add_row("Status", f"[bold green]{result.status}[/bold green]" if result.status == "COMPLETED" else f"[bold yellow]{result.status}[/bold yellow]")
        summary_table.add_row("Files Analyzed", str(result.files_scanned))
        summary_table.add_row("Structural Artifacts", str(len(result.artifacts)))
        summary_table.add_row("Typed Relationships", str(len(result.relationships)))
        summary_table.add_row("Evidence Records", str(len(result.evidence_items)))
        summary_table.add_row("Analyzers Executed", ", ".join(result.analyzer_names))
        summary_table.add_row("Warnings", str(len(result.warnings)))
        summary_table.add_row("Errors", str(len(result.errors)))

        console.print(summary_table)
        console.print()

        # Artifact Breakdown Table
        type_counts = {}
        for a in result.artifacts:
            type_counts[a.artifact_type.value] = type_counts.get(a.artifact_type.value, 0) + 1

        if type_counts:
            art_table = Table(title="Extracted Artifacts by Category", border_style="green")
            art_table.add_column("Artifact Type", style="bold")
            art_table.add_column("Count", justify="right", style="cyan")
            for t, c in sorted(type_counts.items()):
                art_table.add_row(t, str(c))
            console.print(art_table)
            console.print()

        # Relationship Breakdown Table
        rel_counts = {}
        for r in result.relationships:
            rel_counts[r.relationship_type.value] = rel_counts.get(r.relationship_type.value, 0) + 1

        if rel_counts:
            rel_table = Table(title="Extracted Relationships by Semantic Type", border_style="yellow")
            rel_table.add_column("Relationship Type", style="bold")
            rel_table.add_column("Count", justify="right", style="magenta")
            for t, c in sorted(rel_counts.items()):
                rel_table.add_row(t, str(c))
            console.print(rel_table)
            console.print()

        console.print(f"[bold green]✔ Digital Twin snapshot '{snapshot_id}' built and persisted successfully.[/bold green]")
        console.print()

        # Continuous Architecture Drift Detection
        detected_baseline = baseline
        if not detected_baseline:
            candidates = [
                os.path.join(abs_path, "architecture-baseline.yaml"),
                os.path.join(abs_path, "docs", "architecture-baseline.yaml"),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    detected_baseline = cand
                    break

        if detected_baseline and os.path.exists(detected_baseline):
            from app.services.architecture.service import architecture_service
            arch_report = architecture_service.evaluate_repository(
                repository_path=abs_path,
                baseline_path=detected_baseline,
                snapshot_id=snapshot_id,
                repository_id=repo.id,
            )
            architecture_service.persist_report(
                db=db,
                report=arch_report,
                repository_id=repo.id,
                snapshot_id=snapshot_id,
            )
            arch_table = Table(title="Continuous Architecture Conformance", border_style="cyan")
            arch_table.add_column("Metric", style="bold")
            arch_table.add_column("Value", style="green")
            arch_table.add_row("Baseline Version", arch_report.baseline_version)
            arch_table.add_row("Conformance", f"{arch_report.conformance_percentage:.1f}%")
            arch_table.add_row("Violations", str(arch_report.violations))
            arch_table.add_row("Circular Cycles", str(arch_report.circular_dependencies))
            console.print(arch_table)
            console.print()

        # Graph Projection Summary
        from app.services.analysis.graph.projection import twin_graph_projection
        graph_proj = twin_graph_projection.project_graph(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
        )
        graph_table = Table(title="Interactive Digital Twin Graph Projection", border_style="magenta")
        graph_table.add_column("Metric", style="bold")
        graph_table.add_column("Value", style="cyan")
        graph_table.add_row("Total Graph Nodes", str(graph_proj["summary"]["total_nodes"]))
        graph_table.add_row("Total Graph Edges", str(graph_proj["summary"]["total_edges"]))
        graph_table.add_row("Interactive Obsidian View", f"http://localhost:8000/app?repo={repo.id}&snapshot={snapshot_id}")
        console.print(graph_table)
        console.print()

    except Exception as exc:
        console.print(f"[bold red]Analysis failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)
    finally:
        db.close()


@app.command("status")
def status_cmd():
    """
    Displays the authoritative project execution status.
    Calculates completion percentage deterministically from explicit verified milestones.
    Separates Project Progress from Architecture Conformance.
    """
    from app.services.status.tracker import project_status_tracker

    status = project_status_tracker.get_status()

    console.print()
    console.print(Panel(
        f"[bold cyan]{status.project_name}[/bold cyan]\n"
        f"[dim]Authoritative Milestone-Based Execution Status & Architecture Conformance[/dim]\n"
        f"Current Phase: [bold magenta]{status.current_phase}[/bold magenta] | Status: [bold green]{status.verification_status}[/bold green]",
        border_style="cyan"
    ))

    # Progress Summary
    progress_table = Table(title="Progress & Conformance Overview", border_style="dim")
    progress_table.add_column("Metric", style="bold")
    progress_table.add_column("Score / Status", justify="center", style="bold green")
    progress_table.add_column("Measurement Basis", style="dim")

    progress_table.add_row(
        "Overall Project Progress",
        f"[bold green]{status.overall_project_progress}%[/bold green]",
        "Completed phases (Phases 1-3 of 10 verified)"
    )
    p3 = next((p for p in status.phases if p.phase_number == 3), None)
    p3_milestone_str = f"{p3.verified_milestones} / {p3.total_milestones} Milestones VERIFIED with tests" if p3 else "All Milestones VERIFIED"

    progress_table.add_row(
        "Current Phase Progress (Phase 3)",
        f"[bold green]{status.current_phase_progress}%[/bold green]",
        p3_milestone_str
    )
    progress_table.add_row(
        "Architecture Conformance",
        f"[bold cyan]{status.architecture_conformance}%[/bold cyan]",
        "Structural AST measurement against docs/architecture-baseline.yaml"
    )
    progress_table.add_row(
        "Detected Architecture Drift",
        f"[bold green]{status.architecture_status.detected_drift_count}[/bold green]",
        "Evidence-based boundary violations in active code"
    )
    progress_table.add_row(
        "Database Architecture",
        f"{status.database_status.provider} on {status.database_status.target_host_port}",
        f"{status.database_status.total_tables} tables, migration {status.database_status.migrations_head}"
    )
    progress_table.add_row(
        "Test Suite Status",
        f"[bold green]{status.test_status}[/bold green]",
        "Automated Pytest regression suite"
    )
    progress_table.add_row(
        "Last Verified",
        status.last_verified,
        "Continuous verification pipeline"
    )

    console.print(progress_table)
    console.print()

    # Phase Breakdown
    phase_table = Table(title="Phase Lifecycle Status", border_style="magenta")
    phase_table.add_column("Phase #", justify="center", style="bold")
    phase_table.add_column("Phase Name", style="bold")
    phase_table.add_column("Status", justify="center")
    phase_table.add_column("Milestones", justify="center")
    phase_table.add_column("Progress", justify="right")

    for p in status.phases:
        status_color = "green" if p.status == "COMPLETE" else ("yellow" if p.status == "IN_PROGRESS" else "dim")
        phase_table.add_row(
            str(p.phase_number),
            p.phase_name,
            f"[{status_color}]{p.status}[/{status_color}]",
            f"{p.verified_milestones}/{p.total_milestones}",
            f"{p.completion_percentage}%",
        )

    console.print(phase_table)
    console.print()

    # Phase 3 Milestones Detailed Table
    p3 = next((p for p in status.phases if p.phase_number == 3), None)
    if p3 and p3.milestones:
        m_table = Table(title="Phase 3 Milestones & Verification Evidence", border_style="green")
        m_table.add_column("ID", justify="center", style="dim")
        m_table.add_column("Milestone", style="bold")
        m_table.add_column("State", justify="center")
        m_table.add_column("Verification Evidence", style="cyan")

        for m in p3.milestones:
            state_color = "green" if m.state.value == "VERIFIED" else ("yellow" if m.state.value == "IN_PROGRESS" else "dim")
            m_table.add_row(
                m.id,
                m.name,
                f"[{state_color}]{m.state.value}[/{state_color}]",
                m.verification_evidence or "-",
            )

        console.print(m_table)
        console.print()

    # Known Limitations
    if status.known_limitations:
        lim_table = Table(title="Known Limitations & Future Phase Scope", border_style="yellow")
        lim_table.add_column("#", justify="center", style="dim")
        lim_table.add_column("Limitation / Scope Constraint", style="yellow")
        for idx, lim in enumerate(status.known_limitations, 1):
            lim_table.add_row(str(idx), lim)
        console.print(lim_table)
        console.print()


arch_app = typer.Typer(
    name="arch",
    help="Architecture baseline, AST drift detection, and conformance reports",
    no_args_is_help=True,
)
app.add_typer(arch_app, name="arch")


@arch_app.command("check")
def arch_check_cmd(
    repo_path: str = typer.Argument(".", help="Path to software repository to analyze"),
    baseline: Optional[str] = typer.Option(None, "--baseline", "-b", help="Path to custom architecture-baseline.yaml"),
):
    """
    Evaluates architecture drift from repository evidence (AST / import relationships)
    against the machine-readable architecture baseline.
    """
    from app.services.architecture.service import architecture_service

    abs_path = os.path.abspath(repo_path)
    if not os.path.exists(abs_path):
        console.print(f"[bold red]Error:[/bold red] Path '{repo_path}' does not exist.")
        raise typer.Exit(code=1)

    console.print()
    console.print(Panel(
        f"[bold cyan]ARCHITECTURE DRIFT & CONFORMANCE DETECTOR[/bold cyan]\n"
        f"[dim]Deterministic AST Import Analysis against Baseline Contract[/dim]\n"
        f"Target Repository: [green]{abs_path}[/green]",
        border_style="cyan"
    ))

    try:
        report = architecture_service.evaluate_repository(
            repository_path=abs_path,
            baseline_path=baseline,
        )

        conf_color = "green" if report.conformance_percentage >= 95.0 else ("yellow" if report.conformance_percentage >= 80.0 else "red")

        rep_table = Table(title="Architecture Conformance Summary", border_style="dim")
        rep_table.add_column("Metric", style="bold")
        rep_table.add_column("Value", justify="center", style="bold")

        rep_table.add_row("Expected Boundaries Checked", str(report.expected_boundaries))
        rep_table.add_row("Validated Boundary Rules", str(report.validated_boundaries))
        rep_table.add_row("Violations Detected", f"[bold red]{report.violations}[/bold red]" if report.violations > 0 else "[bold green]0[/bold green]")
        rep_table.add_row("Circular Dependencies", f"[bold red]{report.circular_dependencies}[/bold red]" if report.circular_dependencies > 0 else "[bold green]0[/bold green]")
        rep_table.add_row("Unexpected External Dependencies", f"[bold red]{report.unexpected_dependencies}[/bold red]" if report.unexpected_dependencies > 0 else "[bold green]0[/bold green]")
        rep_table.add_row("Architecture Conformance", f"[{conf_color}]{report.conformance_percentage}%[/{conf_color}]")

        console.print(rep_table)
        console.print()

        if report.drifts:
            drift_table = Table(title="Detected Architecture Drift (Repository Evidence)", border_style="red")
            drift_table.add_column("Category", style="bold magenta")
            drift_table.add_column("Severity", justify="center")
            drift_table.add_column("Source -> Target", style="cyan")
            drift_table.add_column("File:Line", style="yellow")
            drift_table.add_column("Confidence", justify="center")
            drift_table.add_column("Rule / Evidence", style="dim")

            for d in report.drifts:
                cat_val = getattr(d.category, "value", str(d.category))
                sev_val = getattr(d.severity, "value", str(d.severity))
                sev_color = "red" if sev_val in ("CRITICAL", "HIGH") else "yellow"
                drift_table.add_row(
                    cat_val,
                    f"[{sev_color}]{sev_val}[/{sev_color}]",
                    f"{d.source} -> {d.target}",
                    f"{d.file}:{d.line}",
                    f"{d.confidence * 100:.0f}%",
                    f"{d.expected_rule}\nEvidence: {d.actual_evidence}",
                )

            console.print(drift_table)
            console.print()
        else:
            console.print("[bold green]✔ Zero architectural violations detected. 100% boundary conformance.[/bold green]")
            console.print()

    except Exception as exc:
        console.print(f"[bold red]Architecture check failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)


@arch_app.command("compare")
def arch_compare_cmd(
    snapshot_a: str = typer.Argument(..., help="First snapshot ID (baseline)"),
    snapshot_b: str = typer.Argument(..., help="Second snapshot ID (target)"),
):
    """
    Compares architecture drift reports between two snapshots in PostgreSQL.
    Identifies newly introduced drifts, resolved drifts, and net conformance delta.
    """
    from app.core.database import SessionLocal
    from app.services.architecture.service import architecture_service

    db = SessionLocal()
    try:
        res = architecture_service.compare_snapshots(db, snapshot_a, snapshot_b)

        console.print()
        console.print(Panel(
            f"[bold cyan]SNAPSHOT ARCHITECTURE DRIFT COMPARISON[/bold cyan]\n"
            f"[dim]{res.snapshot_a}  →  {res.snapshot_b}[/dim]",
            border_style="cyan"
        ))

        delta_color = "green" if res.conformance_delta >= 0 else "red"
        diff_table = Table(title="Conformance Comparison", border_style="dim")
        diff_table.add_column("Snapshot A Conformance", justify="center")
        diff_table.add_column("Snapshot B Conformance", justify="center")
        diff_table.add_column("Delta", justify="center", style=f"bold {delta_color}")
        diff_table.add_column("New Drifts", justify="center", style="bold red")
        diff_table.add_column("Resolved Drifts", justify="center", style="bold green")

        diff_table.add_row(
            f"{res.conformance_a}%",
            f"{res.conformance_b}%",
            f"{'+' if res.conformance_delta >= 0 else ''}{res.conformance_delta}%",
            str(len(res.new_drifts)),
            str(len(res.resolved_drifts)),
        )
        console.print(diff_table)
        console.print()

        if res.new_drifts:
            console.print("[bold red]Newly Introduced Drifts:[/bold red]")
            for d in res.new_drifts:
                s_val = getattr(d.severity, "value", str(d.severity))
                console.print(f"  [red]+[/red] [{s_val}] {d.source} -> {d.target} at {d.file}:{d.line}")
            console.print()

        if res.resolved_drifts:
            console.print("[bold green]Resolved Drifts:[/bold green]")
            for d in res.resolved_drifts:
                s_val = getattr(d.severity, "value", str(d.severity))
                console.print(f"  [green]✔[/green] [{s_val}] {d.source} -> {d.target} (Fixed)")
            console.print()

    except Exception as exc:
        console.print(f"[bold red]Comparison failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)
    finally:
        db.close()


@app.command("graph")
def graph_cmd(
    repo_path: str = typer.Argument(".", help="Path to software repository"),
    snapshot_id: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Specific snapshot ID"),
    depth: int = typer.Option(2, "--depth", "-d", help="Neighborhood depth"),
    level: int = typer.Option(2, "--level", "-l", help="Hierarchical level (1: Modules, 2: Components, 3: Members, 4: All)"),
):
    """
    Projects and displays the Interactive Digital Twin Graph statistics.
    Provides direct access URL to the Obsidian-style visualization layer.
    """
    from app.core.database import SessionLocal
    from app.models.entities import Repository, RepositorySnapshot
    from app.services.analysis.graph.projection import twin_graph_projection

    abs_path = os.path.abspath(repo_path)
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter_by(local_path=abs_path).first()
        if not repo:
            console.print(f"[bold red]Error:[/bold red] Repository at '{abs_path}' not found in Digital Twin database.")
            console.print("Run [bold cyan]./digital-twin analyze <path>[/bold cyan] first.")
            raise typer.Exit(code=1)

        target_snap_id = snapshot_id
        if not target_snap_id:
            snap = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()
            if not snap:
                console.print(f"[bold red]Error:[/bold red] No snapshots found for repository '{repo.name}'.")
                raise typer.Exit(code=1)
            target_snap_id = snap.id

        graph_proj = twin_graph_projection.project_graph(
            db=db,
            repository_id=repo.id,
            snapshot_id=target_snap_id,
            level=level,
            depth=depth,
        )

        console.print()
        console.print(Panel(
            f"[bold magenta]DIGITAL TWIN ARCHITECTURE GRAPH PROJECTION[/bold magenta]\n"
            f"Repository: [green]{repo.name}[/green] | Snapshot: [cyan]{target_snap_id}[/cyan] | Level: [yellow]{level}[/yellow]",
            border_style="magenta"
        ))

        summary = graph_proj["summary"]
        table = Table(title="Graph Projection Overview", border_style="cyan")
        table.add_column("Property", style="bold")
        table.add_column("Count / Details", style="green")
        table.add_row("Nodes Rendered", str(summary["total_nodes"]))
        table.add_row("Edges Rendered", str(summary["total_edges"]))
        table.add_row("Hierarchical Level", f"Level {level}")
        table.add_row("Violations Present", str(len(graph_proj.get("drift_violations", []))))
        table.add_row("Interactive URL", f"http://localhost:8000/app?repo={repo.id}&snapshot={target_snap_id}")
        console.print(table)
        console.print()

        # Breakdown by Node Type
        type_counts = {}
        for n in graph_proj["nodes"]:
            t = n.get("type", "UNKNOWN")
            type_counts[t] = type_counts.get(t, 0) + 1

        if type_counts:
            t_table = Table(title="Rendered Graph Nodes by Type", border_style="green")
            t_table.add_column("Node Type", style="bold")
            t_table.add_column("Count", justify="right", style="cyan")
            for t, c in sorted(type_counts.items()):
                t_table.add_row(t, str(c))
            console.print(t_table)
            console.print()

    except Exception as exc:
        console.print(f"[bold red]Graph projection failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)
    finally:
        db.close()


@app.command("impact-analysis")
def impact_analysis_cmd(
    repository: str = typer.Option(..., "--repository", "-r", help="Repository ID, name, or local path"),
    base_snapshot: str = typer.Option(..., "--base", "-b", help="Baseline Snapshot ID (before change)"),
    target_snapshot: str = typer.Option(..., "--target", "-t", help="Target Snapshot ID (after change)"),
    max_depth: int = typer.Option(5, "--max-depth", "-d", help="Maximum propagation traversal depth"),
    include_tests: bool = typer.Option(True, "--include-tests/--no-tests", help="Include test suite impacts"),
    include_processes: bool = typer.Option(True, "--include-processes/--no-processes", help="Include business process impacts"),
    include_apis: bool = typer.Option(True, "--include-apis/--no-apis", help="Include API endpoint impacts"),
):
    """
    Executes Phase 4 Change Impact & Blast Radius analysis between two snapshots.
    Determines directly and indirectly affected components, APIs, processes, and tests.
    """
    from app.core.database import SessionLocal
    from app.models.entities import Repository
    from app.services.impact import change_impact_service, ImpactConfig
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        repo = (
            db.query(Repository)
            .filter(
                or_(
                    Repository.id == repository,
                    Repository.name == repository,
                    Repository.local_path == os.path.abspath(repository),
                )
            )
            .first()
        )
        if not repo:
            console.print(f"[bold red]Error:[/bold red] Repository '{repository}' not found in Digital Twin database.")
            raise typer.Exit(code=1)

        console.print()
        console.print(Panel(
            f"[bold cyan]PHASE 4 — CHANGE IMPACT / BLAST-RADIUS ANALYSIS[/bold cyan]\n"
            f"Repository: [green]{repo.name}[/green] ({repo.id})\n"
            f"Base Snapshot (A): [cyan]{base_snapshot}[/cyan]\n"
            f"Target Snapshot (B): [yellow]{target_snapshot}[/yellow]\n"
            f"Max Traversal Depth: [magenta]{max_depth}[/magenta]",
            border_style="cyan"
        ))

        config = ImpactConfig(
            max_depth=max_depth,
            include_tests=include_tests,
            include_processes=include_processes,
            include_apis=include_apis,
        )

        result = change_impact_service.run_impact_analysis(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=base_snapshot,
            target_snapshot_id=target_snapshot,
            config=config,
        )

        s = result.summary
        metrics_table = Table(title="Change Impact Summary", border_style="cyan")
        metrics_table.add_column("Impact Metric", style="bold")
        metrics_table.add_column("Count", justify="center", style="green")

        metrics_table.add_row("Changed Entities", str(s.changed))
        metrics_table.add_row("Directly Affected (Level 1)", str(s.directly_affected))
        metrics_table.add_row("Indirectly Affected (Level 2+)", str(s.indirectly_affected))
        metrics_table.add_row("Affected Components", str(s.affected_components))
        metrics_table.add_row("Affected Services", str(s.affected_services))
        metrics_table.add_row("Affected APIs", str(s.affected_apis))
        metrics_table.add_row("Affected Processes", str(s.affected_processes))
        metrics_table.add_row("Affected Tests", str(s.affected_tests))
        metrics_table.add_row("Max Depth Reached", str(s.max_depth_reached))
        metrics_table.add_row("Execution Time", f"{result.execution_time_ms} ms")

        console.print(metrics_table)
        console.print()

        # Display Changed Entities
        if result.changes:
            ch_table = Table(title="Detected Changes", border_style="yellow")
            ch_table.add_column("Type", style="bold")
            ch_table.add_column("Symbol / Artifact", style="cyan")
            ch_table.add_column("Kind", style="dim")
            ch_table.add_column("File / Location", style="dim")
            ch_table.add_column("Level", justify="center")

            for c in result.changes:
                ch_table.add_row(
                    c.change_type.value,
                    c.qualified_name,
                    c.artifact_type,
                    c.source_file,
                    "Symbol" if c.is_symbol_level else "File",
                )
            console.print(ch_table)
            console.print()

        # Display Impact Paths
        if result.paths:
            path_table = Table(title="Causal Impact Paths", border_style="magenta")
            path_table.add_column("Depth", justify="center", style="bold")
            path_table.add_column("Root Cause", style="cyan")
            path_table.add_column("Impact Chain", style="white")
            path_table.add_column("Terminal Entity", style="yellow")
            path_table.add_column("Terminal Category", style="dim")
            path_table.add_column("Confidence", justify="right", style="green")

            for p in result.paths[:25]:  # Show top 25 paths
                chain_str = " -> ".join(p.nodes)
                path_table.add_row(
                    str(p.depth),
                    p.root_symbol,
                    chain_str,
                    p.target_symbol,
                    p.terminal_type,
                    f"{p.confidence * 100:.1f}%",
                )
            console.print(path_table)
            if len(result.paths) > 25:
                console.print(f"[dim]Showing top 25 of {len(result.paths)} paths.[/dim]")
            console.print()

        console.print(f"[bold green]✔[/bold green] Impact analysis recorded: [cyan]{result.analysis_id}[/cyan]")
        console.print(f"[dim]Web Inspector: http://localhost:8000/app?repo={repo.id}&analysis={result.analysis_id}[/dim]\n")

    except Exception as exc:
        console.print(f"[bold red]Impact analysis failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)
    finally:
        db.close()


# ====================================================================
# PHASE 5 CLI SUBCOMMANDS: RUNTIME, PROCESS, INCIDENT
# ====================================================================

runtime_app = typer.Typer(help="Runtime Evidence Ingestion and Querying", no_args_is_help=True)
app.add_typer(runtime_app, name="runtime")

process_app = typer.Typer(help="Process Twin Discovery and Workflow Inspection", no_args_is_help=True)
app.add_typer(process_app, name="process")

incident_app = typer.Typer(help="Incident Intelligence & Causal Investigation", no_args_is_help=True)
app.add_typer(incident_app, name="incident")


@runtime_app.command("ingest")
def runtime_ingest(
    file_path: str = typer.Argument(..., help="Path to JSON or JSONL runtime event file"),
    repository: str = typer.Option(..., "--repository", "-r", help="Repository ID or Name"),
    snapshot: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Snapshot ID (optional)"),
    environment: str = typer.Option("production", "--environment", "-e", help="Environment name"),
):
    """Ingests, sanitizes, and correlates runtime events from a JSON/JSONL file."""
    from app.core.database import SessionLocal
    from app.models.entities import Repository
    from app.services.runtime import runtime_evidence_service
    from sqlalchemy import or_

    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File '{file_path}' does not exist.")
        raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(
            or_(Repository.id == repository, Repository.name == repository)
        ).first()
        if not repo:
            console.print(f"[bold red]Error:[/bold red] Repository '{repository}' not found.")
            raise typer.Exit(code=1)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = runtime_evidence_service.ingest_json_or_jsonl(
            db=db,
            repository_id=repo.id,
            content=content,
            snapshot_id=snapshot,
            default_environment=environment,
        )

        console.print(f"\n[bold green]✔ Runtime Evidence Ingested Successfully[/bold green]")
        console.print(f"  Repository: [cyan]{repo.name}[/cyan] ({repo.id})")
        console.print(f"  Ingested Events: [bold]{result.ingested_count}[/bold]")
        console.print(f"  Correlated to Twin: [bold green]{result.correlated_count}[/bold green]")
        console.print(f"  Redacted Sensitive Fields: [yellow]{result.redacted_count}[/yellow]")
        console.print(f"  Execution Time: [dim]{result.execution_time_ms} ms[/dim]\n")
    finally:
        db.close()


@runtime_app.command("list")
def runtime_list(
    repository: str = typer.Option(..., "--repository", "-r", help="Repository ID or Name"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity (ERROR, WARN, INFO)"),
    event_type: Optional[str] = typer.Option(None, "--event-type", help="Filter by event type"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max events to display"),
):
    """Lists recent normalized runtime events."""
    from app.core.database import SessionLocal
    from app.models.entities import Repository
    from app.services.runtime import runtime_evidence_service
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(
            or_(Repository.id == repository, Repository.name == repository)
        ).first()
        if not repo:
            console.print(f"[bold red]Error:[/bold red] Repository '{repository}' not found.")
            raise typer.Exit(code=1)

        page = runtime_evidence_service.list_events(
            db=db,
            repository_id=repo.id,
            severity=severity,
            event_type=event_type,
            limit=limit,
        )

        table = Table(title=f"Runtime Events ({page.total} total)", border_style="cyan")
        table.add_column("Timestamp", style="dim")
        table.add_column("Type", style="bold")
        table.add_column("Severity", style="yellow")
        table.add_column("Service", style="cyan")
        table.add_column("Message", style="white")
        table.add_column("Correlated", style="green")

        for ev in page.events:
            sev_color = "red" if ev.severity in ("ERROR", "CRITICAL") else "yellow" if ev.severity == "WARN" else "green"
            table.add_row(
                ev.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                ev.event_type,
                f"[{sev_color}]{ev.severity}[/{sev_color}]",
                ev.service_name or "-",
                (ev.message or "-")[:50],
                f"{ev.correlation_method} ({ev.correlation_confidence * 100:.0f}%)" if ev.component_artifact_id else "[dim]Unmatched[/dim]",
            )
        console.print(table)
    finally:
        db.close()


@process_app.command("discover")
def process_discover(
    repository: str = typer.Option(..., "--repository", "-r", help="Repository ID or Name"),
    snapshot: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Snapshot ID (optional)"),
):
    """Executes deterministic Process Twin discovery from AST call chains."""
    from app.core.database import SessionLocal
    from app.models.entities import Repository
    from app.services.process import process_service
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(
            or_(Repository.id == repository, Repository.name == repository)
        ).first()
        if not repo:
            console.print(f"[bold red]Error:[/bold red] Repository '{repository}' not found.")
            raise typer.Exit(code=1)

        result = process_service.discover_processes(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot,
        )

        console.print(f"\n[bold green]✔ Process Twin Discovery Complete[/bold green]")
        console.print(f"  Discovered Workflows: [bold cyan]{result.total_processes}[/bold cyan]")
        console.print(f"  Execution Steps: [bold]{result.total_steps}[/bold]")
        console.print(f"  Process Transitions: [bold]{result.total_transitions}[/bold]")
        console.print(f"  Execution Time: [dim]{result.execution_time_ms} ms[/dim]\n")

        for p in result.processes:
            console.print(f"  • [bold]{p.name}[/bold] ({p.steps_count} steps, {p.transitions_count} transitions)")
        console.print()
    finally:
        db.close()


@incident_app.command("create")
def incident_create(
    repository: str = typer.Option(..., "--repository", "-r", help="Repository ID or Name"),
    title: str = typer.Option(..., "--title", "-t", help="Incident title"),
    severity: str = typer.Option("medium", "--severity", help="Severity (low, medium, high, critical)"),
    environment: str = typer.Option("production", "--environment", "-e", help="Environment"),
    description: Optional[str] = typer.Option(None, "--desc", help="Incident description"),
):
    """Creates a new incident record."""
    from app.core.database import SessionLocal
    from app.models.entities import Repository
    from app.services.incident import incident_service, IncidentCreate
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(
            or_(Repository.id == repository, Repository.name == repository)
        ).first()
        if not repo:
            console.print(f"[bold red]Error:[/bold red] Repository '{repository}' not found.")
            raise typer.Exit(code=1)

        req = IncidentCreate(
            title=title,
            description=description,
            severity=severity,
            environment=environment,
        )
        inc = incident_service.create_incident(db, repo.id, req)
        console.print(f"\n[bold green]✔ Incident Created:[/bold green] [cyan]{inc.id}[/cyan]")
        console.print(f"  Title: {inc.title}")
        console.print(f"  Severity: {inc.severity.upper()} · Status: {inc.status.upper()}\n")
    finally:
        db.close()


@incident_app.command("investigate")
def incident_investigate(
    incident_id: str = typer.Argument(..., help="Incident ID to investigate"),
):
    """Runs deterministic causal investigation for an incident."""
    from app.core.database import SessionLocal
    from app.services.incident import incident_service

    db = SessionLocal()
    try:
        result = incident_service.investigate_incident(db, incident_id)

        console.print(Panel(
            f"[bold]Incident Investigation:[/bold] {result.incident_title}\n"
            f"[dim]Severity:[/dim] {result.severity.upper()}  [dim]Environment:[/dim] {result.environment}",
            title="🔍 Digital Twin Incident Intelligence",
            border_style="red" if result.severity in ("high", "critical") else "yellow",
        ))

        if result.affected_component:
            comp = result.affected_component
            console.print(f"[bold]Primary Affected Component:[/bold] [cyan]{comp['name']}[/cyan] ({comp['type']})")
            if comp.get("location"):
                console.print(f"  Location: [dim]{comp['location']}[/dim]")
            console.print()

        # Candidate Causal Paths
        if result.candidate_causal_paths:
            path_table = Table(title="Candidate Causal Paths (Evidence-Backed)", border_style="magenta")
            path_table.add_column("Hops", justify="center", style="bold")
            path_table.add_column("Recent Change", style="cyan")
            path_table.add_column("Type", style="yellow")
            path_table.add_column("Chain to Incident Target", style="white")
            path_table.add_column("Confidence", justify="right", style="green")

            for path in result.candidate_causal_paths:
                node_names = [n["name"] for n in path.path_nodes]
                chain_str = " -> ".join(node_names) if len(node_names) > 1 else "[bold cyan]Direct Modification[/bold cyan]"
                path_table.add_row(
                    str(path.hop_count),
                    path.changed_artifact_name,
                    path.change_type,
                    chain_str,
                    f"{path.confidence * 100:.0f}%",
                )
            console.print(path_table)
            console.print()
        else:
            console.print("[dim]No candidate recent change paths linked to this component.[/dim]\n")

        # Affected Processes
        if result.affected_processes:
            console.print("[bold]Affected Business & Service Processes:[/bold]")
            for p in result.affected_processes:
                console.print(f"  • [bold]{p['name']}[/bold] (Step: {p['step_name']})")
            console.print()

        # Related Tests
        if result.related_tests:
            console.print(f"[bold]Related Tests to Execute ({len(result.related_tests)}):[/bold]")
            for t in result.related_tests[:5]:
                console.print(f"  • [green]{t['test_name']}[/green] [dim]({t['location']})[/dim]")
            console.print()

        console.print(f"[dim italic]{result.disclaimer}[/dim italic]\n")

    except Exception as exc:
        console.print(f"[bold red]Investigation failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)
    finally:
        db.close()


if __name__ == "__main__":
    app()

