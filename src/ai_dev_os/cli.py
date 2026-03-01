"""
Unified CLI for the AI Development Operating System.

Provides commands for all major subsystems:
- catalog: Agent catalog browsing
- ralph: Ralph Loop management
- spec: Specum pipeline
- plan: RALPLAN deliberation
- gsd: GSD project lifecycle
- team: Team Pipeline execution
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def _print_banner() -> None:
    """Print the ai-dev-os banner."""
    console.print(
        Panel(
            Text.assemble(
                ("AI Development Operating System", "bold magenta"),
                ("\n", ""),
                ("v1.0.0 — Build better software, faster", "dim"),
            ),
            box=box.DOUBLE,
            border_style="magenta",
        )
    )


@click.group()
@click.version_option(version="1.0.0", prog_name="ai-dev-os")
def main() -> None:
    """
    AI Development Operating System CLI.

    Orchestrate Claude Code agents across complex software projects
    using OMC, Ralph Loop, Specum, RALPLAN, GSD, and Team Pipeline.

    \b
    Quick Start:
      ai-dev-os catalog list           # See all 25+ agents
      ai-dev-os ralph start --task "Build auth system"
      ai-dev-os spec new --goal "Implement payment processing"
      ai-dev-os gsd new-project --name myapp
    """


# ============================================================
# CATALOG COMMANDS
# ============================================================

@main.group()
def catalog() -> None:
    """Browse the OMC agent catalog."""


@catalog.command("list")
@click.option("--lane", "-l", type=str, help="Filter by lane (build, review, domain, coordination)")
@click.option("--model", "-m", type=str, help="Filter by model tier (haiku, sonnet, opus)")
@click.option("--tree", is_flag=True, help="Display as tree instead of table")
def catalog_list(lane: Optional[str], model: Optional[str], tree: bool) -> None:
    """Show all agents in the OMC catalog."""
    from ai_dev_os.omc.catalog import AgentCatalog

    cat = AgentCatalog()

    if tree:
        cat.render_lane_tree()
        return

    agents = cat.list_agents()
    if lane:
        agents = [a for a in agents if a.lane == lane]
    if model:
        agents = [a for a in agents if a.model_tier == model]

    table = Table(
        title=f"OMC Agent Catalog ({len(agents)} agents)",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Lane", style="yellow")
    table.add_column("Model", style="green")
    table.add_column("Description")

    for agent in agents:
        table.add_row(agent.name, agent.lane, agent.model_tier, agent.description)

    console.print(table)
    console.print(f"\n[dim]Use 'ai-dev-os catalog show <name>' for full details[/dim]")


@catalog.command("show")
@click.argument("agent_name")
def catalog_show(agent_name: str) -> None:
    """Show full details for a specific agent."""
    from ai_dev_os.omc.catalog import AgentCatalog

    cat = AgentCatalog()
    agent = cat.get_agent(agent_name)

    if agent is None:
        console.print(f"[bold red]Agent '{agent_name}' not found.[/bold red]")
        available = ", ".join(a.name for a in cat.list_agents())
        console.print(f"[dim]Available agents: {available}[/dim]")
        raise click.Abort()

    console.print(agent.to_rich_panel())

    # Also show routing info
    from ai_dev_os.omc.routing import ModelRouter
    router = ModelRouter()
    tier = router.route(agent_name)
    spec = router.get_model_spec(tier)
    cost = router.estimate_cost(tier, 5000, 2000)

    console.print(
        Panel(
            f"[cyan]Canonical Model:[/cyan] {spec.model_id}\n"
            f"[cyan]Tier:[/cyan] {tier.value}\n"
            f"[cyan]Typical Latency:[/cyan] {spec.typical_latency_seconds}s\n"
            f"[cyan]Estimated Cost (5K in / 2K out):[/cyan] ${cost:.4f}",
            title="[bold green]Model Routing[/bold green]",
            border_style="green",
        )
    )


# ============================================================
# RALPH COMMANDS
# ============================================================

@main.group()
def ralph() -> None:
    """Manage Ralph Loop persistent execution sessions."""


@ralph.command("start")
@click.option("--task", "-t", required=True, help="The goal or task to execute")
@click.option("--max-iterations", "-n", default=100, show_default=True, help="Max loop iterations")
@click.option("--state-path", type=click.Path(), help="Custom state file path")
def ralph_start(task: str, max_iterations: int, state_path: Optional[str]) -> None:
    """Start a new Ralph Loop execution session."""
    from ai_dev_os.ralph_loop.loop import RalphLoop

    path = Path(state_path) if state_path else None
    loop = RalphLoop(state_path=path)
    state = loop.start(task, max_iterations=max_iterations)

    console.print(f"\n[bold green]Ralph Loop initialized![/bold green]")
    console.print(f"[dim]Task: {task}[/dim]")
    console.print(f"[dim]State saved to: {loop._state_path}[/dim]")
    console.print(
        f"\n[yellow]To continue execution, call:[/yellow]\n"
        f"  [cyan]ai-dev-os ralph status[/cyan]"
    )


@ralph.command("status")
@click.option("--state-path", type=click.Path(), help="Custom state file path")
def ralph_status(state_path: Optional[str]) -> None:
    """Show current Ralph Loop status and task list."""
    from ai_dev_os.ralph_loop.loop import RalphLoop

    path = Path(state_path) if state_path else None
    loop = RalphLoop(state_path=path)

    try:
        state = loop.load_state()
    except FileNotFoundError:
        console.print("[bold red]No active Ralph Loop found.[/bold red]")
        console.print("[dim]Start one with: ai-dev-os ralph start --task '...'[/dim]")
        return

    console.print(loop.status_table())

    summary = state.progress_summary()
    pct = state.completion_percentage()

    console.print(
        Panel(
            f"[cyan]Status:[/cyan] {state.status.value}\n"
            f"[cyan]Iteration:[/cyan] {state.iteration}/{state.max_iterations}\n"
            f"[cyan]Progress:[/cyan] {pct}% ({summary['completed']}/{summary['total']} tasks)\n"
            f"[cyan]Goal:[/cyan] {state.goal}",
            title="[bold cyan]Ralph Loop Status[/bold cyan]",
            border_style="cyan",
        )
    )


# ============================================================
# SPEC (SPECUM) COMMANDS
# ============================================================

@main.group()
def spec() -> None:
    """Manage Specum specification pipelines."""


@spec.command("new")
@click.option("--goal", "-g", required=True, help="The goal to build toward")
@click.option("--artifacts-dir", type=click.Path(), help="Directory for stage artifacts")
def spec_new(goal: str, artifacts_dir: Optional[str]) -> None:
    """Start a new Specum specification pipeline."""
    from ai_dev_os.specum.pipeline import SpecumPipeline

    artifacts = Path(artifacts_dir) if artifacts_dir else None
    pipeline = SpecumPipeline(artifacts_dir=artifacts)
    pipeline.start(goal)

    console.print(f"\n[bold green]Specum pipeline started![/bold green]")
    console.print(f"[dim]Goal: {goal}[/dim]")
    console.print(
        f"\n[yellow]Advance through stages with:[/yellow]\n"
        f"  [cyan]ai-dev-os spec status[/cyan]"
    )


@spec.command("status")
@click.option("--state-path", type=click.Path(), help="Custom state file path")
def spec_status(state_path: Optional[str]) -> None:
    """Show current Specum pipeline status."""
    from ai_dev_os.specum.pipeline import SpecumPipeline

    path = Path(state_path) if state_path else None
    pipeline = SpecumPipeline(state_path=path)

    state = pipeline.state
    if not state.goal:
        console.print("[bold red]No active Specum pipeline found.[/bold red]")
        console.print("[dim]Start one with: ai-dev-os spec new --goal '...'[/dim]")
        return

    console.print(pipeline.status())


# ============================================================
# PLAN (RALPLAN) COMMANDS
# ============================================================

@main.command("plan")
@click.option("--task", "-t", required=True, help="The task or goal to plan")
@click.option("--consensus", is_flag=True, help="Run adversarial planner-critic deliberation")
@click.option("--deliberate", is_flag=True, help="Extended mode with pre-mortem + expanded test planning")
def plan_command(task: str, consensus: bool, deliberate: bool) -> None:
    """
    Create an implementation plan, optionally with RALPLAN adversarial deliberation.

    Without --consensus: Creates a single plan using the PlannerAgent.
    With --consensus: Runs iterative planner-critic dialogue until approved.
    With --deliberate: Adds pre-mortem analysis and expanded test planning.
    """
    from ai_dev_os.ralplan.deliberate import RalplanDeliberation
    from ai_dev_os.ralplan.planner import PlannerAgent

    if consensus or deliberate:
        console.print(f"[bold blue]Starting RALPLAN deliberation...[/bold blue]")
        deliberation = RalplanDeliberation()
        result = deliberation.start(task, deliberate=deliberate)

        console.print("\n[bold]Final Plan:[/bold]")
        console.print(result.final_plan.to_markdown())

        if result.approved:
            console.print("\n[bold green]✓ Plan approved after deliberation[/bold green]")
        else:
            console.print("\n[bold yellow]⚠ Plan reached max iterations without full consensus[/bold yellow]")
    else:
        planner = PlannerAgent()
        plan = planner.create_plan(task)
        console.print(plan.to_markdown())


# ============================================================
# GSD COMMANDS
# ============================================================

@main.group()
def gsd() -> None:
    """Manage GSD (Get Stuff Done) project lifecycle."""


@gsd.command("new-project")
@click.option("--name", "-n", required=True, help="Short project identifier")
@click.option("--goal", "-g", required=True, help="Clear statement of what the project delivers")
def gsd_new_project(name: str, goal: str) -> None:
    """Create and initialize a new GSD project."""
    from ai_dev_os.gsd.phases import GSDProject

    project = GSDProject()
    project.create_project(name, goal)

    console.print(f"\n[bold green]GSD project '{name}' created![/bold green]")
    console.print(f"[dim]Check progress with: ai-dev-os gsd progress --name {name}[/dim]")


@gsd.command("progress")
@click.option("--name", "-n", required=True, help="Project name")
def gsd_progress(name: str) -> None:
    """Show progress for a GSD project."""
    from ai_dev_os.gsd.phases import GSDProject

    project = GSDProject()
    try:
        project.load_project(name)
    except FileNotFoundError:
        console.print(f"[bold red]No GSD project found with name: {name}[/bold red]")
        return

    console.print(project.progress_table())

    state = project._state
    if state:
        console.print(
            Panel(
                f"[cyan]Current Phase:[/cyan] {state.current_phase.value}\n"
                f"[cyan]Goal:[/cyan] {state.goal}\n"
                f"[cyan]Last Updated:[/cyan] {state.last_updated}",
                title=f"[bold]GSD Project: {name}[/bold]",
                border_style="blue",
            )
        )


# ============================================================
# TEAM COMMANDS
# ============================================================

@main.group()
def team() -> None:
    """Manage Team Pipeline multi-agent execution."""


@team.command("start")
@click.option("--task", "-t", required=True, help="The task to execute")
@click.option("--agents", "-a", default=3, show_default=True, help="Number of parallel agents")
@click.option("--max-fix-loops", default=3, show_default=True, help="Max fix loop iterations")
def team_start(task: str, agents: int, max_fix_loops: int) -> None:
    """Start a Team Pipeline for multi-agent task execution."""
    from ai_dev_os.team_pipeline.pipeline import TeamPipeline

    console.print(
        Panel(
            f"[bold magenta]Starting Team Pipeline[/bold magenta]\n\n"
            f"[cyan]Task:[/cyan] {task}\n"
            f"[cyan]Max Fix Loops:[/cyan] {max_fix_loops}\n"
            f"[cyan]Pipeline:[/cyan] PLAN → PRD → EXEC → VERIFY → FIX",
            border_style="magenta",
        )
    )

    pipeline = TeamPipeline()
    pipeline.start(task, max_fix_loops=max_fix_loops)

    # Run all stages
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_id = progress.add_task("Running pipeline stages...", total=None)
        while not pipeline.state.is_terminal:
            current = pipeline.state.current_stage
            progress.update(task_id, description=f"Running stage: {current.value}")
            pipeline.advance_stage()

    console.print(pipeline.status())
    console.print(
        f"\n[bold]Final Status:[/bold] "
        f"{'[green]COMPLETE[/green]' if pipeline.state.status.value == 'complete' else '[red]' + pipeline.state.status.value.upper() + '[/red]'}"
    )


@team.command("status")
def team_status() -> None:
    """Show current Team Pipeline status."""
    from ai_dev_os.team_pipeline.pipeline import TeamPipeline

    pipeline = TeamPipeline()
    state = pipeline.state

    if not state.task:
        console.print("[bold red]No active Team Pipeline found.[/bold red]")
        console.print("[dim]Start one with: ai-dev-os team start --task '...'[/dim]")
        return

    console.print(pipeline.status())


if __name__ == "__main__":
    main()
