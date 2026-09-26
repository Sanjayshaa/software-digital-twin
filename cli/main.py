import os
import sys

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

    except Exception as exc:
        console.print(f"[bold red]Analysis failed:[/bold red] {str(exc)}")
        raise typer.Exit(code=1)
    finally:
        db.close()


if __name__ == "__main__":
    app()

