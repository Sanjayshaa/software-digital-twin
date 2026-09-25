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


if __name__ == "__main__":
    app()
