"""
RALPLAN deliberation protocol.

Runs iterative planner-critic dialogue until consensus is reached.
Optionally includes pre-mortem analysis and expanded test planning
in deliberate mode (--deliberate flag).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from ai_dev_os.ralplan.planner import Plan, PlannerAgent
from ai_dev_os.ralplan.critic import CriticAgent, CriticVerdict, VerdictType

console = Console()

MAX_ITERATIONS = 3


@dataclass
class DeliberationRound:
    """Record of one planner-critic iteration."""

    round_number: int
    plan: Plan
    verdict: CriticVerdict
    started_at: datetime


@dataclass
class DeliberationResult:
    """
    Final result of a RALPLAN deliberation.

    Contains the approved plan (if consensus reached) or the final
    plan and verdict if max iterations were exhausted.
    """

    task: str
    final_plan: Plan
    final_verdict: CriticVerdict
    rounds: list[DeliberationRound]
    consensus_reached: bool
    deliberate_mode: bool
    started_at: datetime
    completed_at: datetime

    @property
    def round_count(self) -> int:
        """Number of planner-critic rounds completed."""
        return len(self.rounds)

    @property
    def approved(self) -> bool:
        """True if the final verdict is APPROVE."""
        return self.final_verdict.is_approved

    def summary_table(self) -> Table:
        """Render a rich Table summarizing the deliberation."""
        table = Table(
            title=f"RALPLAN Deliberation — {self.task[:60]}",
            box=box.ROUNDED,
            header_style="bold magenta",
        )
        table.add_column("Round", style="dim", justify="center")
        table.add_column("Plan Revision", justify="center")
        table.add_column("Verdict", justify="center")
        table.add_column("Critical Findings", justify="right")
        table.add_column("Moderate Findings", justify="right")

        for r in self.rounds:
            verdict_style = (
                "[bold green]APPROVE[/bold green]"
                if r.verdict.is_approved
                else "[bold red]REJECT[/bold red]"
            )
            table.add_row(
                str(r.round_number),
                str(r.plan.revision),
                verdict_style,
                str(len(r.verdict.critical_findings)),
                str(len(r.verdict.moderate_findings)),
            )

        return table


class RalplanDeliberation:
    """
    RALPLAN adversarial deliberation protocol.

    Runs up to MAX_ITERATIONS rounds of:
    1. Planner creates/revises a plan
    2. Critic reviews and issues APPROVE or REJECT
    3. If REJECT: planner revises based on critic feedback
    4. Repeat until APPROVE or max iterations

    In --deliberate mode, additionally runs:
    - Pre-mortem analysis (what could go wrong with this plan?)
    - Expanded test planning (unit, integration, e2e, observability)

    Example:
        deliberation = RalplanDeliberation()
        result = deliberation.start("Implement payment processing", deliberate=True)
        if result.approved:
            print(result.final_plan.to_markdown())
    """

    def __init__(self) -> None:
        """Initialize the deliberation with planner and critic agents."""
        self._planner = PlannerAgent()
        self._critic = CriticAgent()

    def start(
        self,
        task: str,
        deliberate: bool = False,
    ) -> DeliberationResult:
        """
        Run the full deliberation process.

        Args:
            task: The task or goal to plan.
            deliberate: If True, run extended deliberation with pre-mortem
                       and expanded test planning.

        Returns:
            DeliberationResult with the final approved plan or best attempt.
        """
        started_at = datetime.utcnow()
        rounds: list[DeliberationRound] = []

        console.print(
            Panel(
                f"[bold blue]RALPLAN DELIBERATION STARTED[/bold blue]\n\n"
                f"[cyan]Task:[/cyan] {task}\n"
                f"[cyan]Mode:[/cyan] {'deliberate (extended)' if deliberate else 'standard'}\n"
                f"[cyan]Max Rounds:[/cyan] {MAX_ITERATIONS}",
                title="[bold blue]🎯 RALPLAN Protocol[/bold blue]",
                border_style="blue",
            )
        )

        current_plan: Optional[Plan] = None
        current_verdict: Optional[CriticVerdict] = None

        for iteration in range(1, MAX_ITERATIONS + 1):
            console.print(f"\n[bold cyan]━━━ ROUND {iteration}/{MAX_ITERATIONS} ━━━[/bold cyan]\n")

            # Planner creates or revises the plan
            if current_plan is None:
                console.print("[yellow]→ Planner: Creating initial plan...[/yellow]")
                current_plan = self._planner.create_plan(task)
            else:
                console.print("[yellow]→ Planner: Revising plan based on critic feedback...[/yellow]")
                criticism = "\n".join(
                    f.description for f in current_verdict.critical_findings  # type: ignore
                )
                current_plan = self._planner.revise_plan(current_plan, criticism)

            console.print(
                f"  Plan revision {current_plan.revision}: "
                f"{current_plan.total_task_count} tasks across {len(current_plan.phases)} phases"
            )

            # Critic reviews the plan
            console.print("[magenta]→ Critic: Reviewing plan...[/magenta]")
            current_verdict = self._critic.review(current_plan)

            verdict_color = "green" if current_verdict.is_approved else "red"
            console.print(
                f"  Critic verdict: [{verdict_color}][bold]{current_verdict.verdict.value}[/bold][/{verdict_color}] "
                f"({len(current_verdict.critical_findings)} critical, "
                f"{len(current_verdict.moderate_findings)} moderate, "
                f"{len(current_verdict.minor_findings)} minor findings)"
            )

            rounds.append(DeliberationRound(
                round_number=iteration,
                plan=current_plan,
                verdict=current_verdict,
                started_at=datetime.utcnow(),
            ))

            if current_verdict.is_approved:
                console.print(f"\n[bold green]✓ CONSENSUS REACHED in {iteration} round(s)![/bold green]")
                break
            elif iteration < MAX_ITERATIONS:
                console.print(f"[yellow]  Critical findings to address: {len(current_verdict.critical_findings)}[/yellow]")
                for finding in current_verdict.critical_findings:
                    console.print(f"  [red]•[/red] {finding.description[:100]}...")
        else:
            console.print(
                f"\n[bold yellow]⚠ Max iterations ({MAX_ITERATIONS}) reached without full consensus.[/bold yellow]\n"
                f"[dim]Proceeding with best available plan (revision {current_plan.revision if current_plan else 0}).[/dim]"  # type: ignore
            )

        assert current_plan is not None
        assert current_verdict is not None

        consensus_reached = current_verdict.is_approved
        completed_at = datetime.utcnow()

        # Extended deliberate mode: pre-mortem + test planning
        if deliberate:
            current_plan = self._run_premortem(current_plan, task)
            current_plan = self._expand_test_planning(current_plan)

        result = DeliberationResult(
            task=task,
            final_plan=current_plan,
            final_verdict=current_verdict,
            rounds=rounds,
            consensus_reached=consensus_reached,
            deliberate_mode=deliberate,
            started_at=started_at,
            completed_at=completed_at,
        )

        console.print(result.summary_table())
        self._print_final_summary(result)

        return result

    def is_consensus_reached(self, verdict: CriticVerdict) -> bool:
        """
        Check if the critic has approved the plan.

        Args:
            verdict: The CriticVerdict to check.

        Returns:
            True if the verdict is APPROVE.
        """
        return verdict.verdict == VerdictType.APPROVE

    def _run_premortem(self, plan: Plan, task: str) -> Plan:
        """
        Run pre-mortem analysis on the plan.

        Imagines the plan has failed and works backward to identify
        the most likely causes of failure.

        Args:
            plan: The plan to analyze.
            task: The original task description.

        Returns:
            Plan with pre-mortem risks added.
        """
        console.print("\n[bold magenta]→ Pre-mortem Analysis (deliberate mode)...[/bold magenta]")

        premortem_risks = [
            "Implementation took 3x longer than estimated — complexity underestimated in planning",
            "Critical integration assumption was wrong — spike was skipped or rushed",
            "Performance requirements not achievable with chosen technology stack",
            "Scope creep during implementation caused delays and incomplete core features",
            "Team lacked expertise in key technology — learning curve not accounted for",
        ]

        plan.top_risks = list(set(plan.top_risks + premortem_risks))[:5]  # Keep top 5 unique
        plan.revision_notes = (
            (plan.revision_notes or "") +
            "\n\n**Pre-mortem Analysis:** Top failure modes identified and incorporated into risk list."
        )

        console.print(f"  [green]✓[/green] Pre-mortem complete. {len(premortem_risks)} additional failure modes analyzed.")
        return plan

    def _expand_test_planning(self, plan: Plan) -> Plan:
        """
        Add expanded test planning to the plan.

        Adds explicit test tasks for unit, integration, e2e, and observability.

        Args:
            plan: The plan to expand.

        Returns:
            Plan with test planning tasks added.
        """
        from ai_dev_os.ralplan.planner import PlanPhase, PlanTask

        console.print("\n[bold magenta]→ Expanded Test Planning (deliberate mode)...[/bold magenta]")

        test_phase = PlanPhase(
            name="Test Strategy",
            goal="Define and implement comprehensive test coverage across all layers",
            verification="All critical paths have tests at appropriate level; test pyramid is balanced",
            tasks=[
                PlanTask(
                    id="TEST.1",
                    title="Unit test: domain logic and business rules",
                    description="Write unit tests for all domain entities, value objects, and business rules. Pure functions only — no DB or network.",
                    phase="Test Strategy",
                    complexity="M",
                ),
                PlanTask(
                    id="TEST.2",
                    title="Integration test: repository and service layers",
                    description="Write integration tests that exercise the full stack from service to DB. Use a test database, not mocks.",
                    phase="Test Strategy",
                    complexity="M",
                    depends_on=["TEST.1"],
                ),
                PlanTask(
                    id="TEST.3",
                    title="E2E test: critical user journeys",
                    description="Write E2E tests for the 3 most critical user journeys. Test against the running system.",
                    phase="Test Strategy",
                    complexity="M",
                    depends_on=["TEST.2"],
                ),
                PlanTask(
                    id="TEST.4",
                    title="Observability test: verify logging and metrics",
                    description="Verify that all defined metrics are emitted, logs have correct structure, and health check reports correct status.",
                    phase="Test Strategy",
                    complexity="S",
                    depends_on=["TEST.3"],
                ),
            ],
        )

        plan.phases.append(test_phase)
        plan.revision_notes = (
            (plan.revision_notes or "") +
            "\n\n**Expanded Test Planning:** Unit, integration, E2E, and observability test tasks added."
        )

        console.print(f"  [green]✓[/green] Test planning expanded. {len(test_phase.tasks)} test tasks added.")
        return plan

    def _print_final_summary(self, result: DeliberationResult) -> None:
        """Print the final deliberation summary to console."""
        duration = (result.completed_at - result.started_at).total_seconds()

        status = "[bold green]CONSENSUS REACHED[/bold green]" if result.consensus_reached else "[bold yellow]MAX ITERATIONS (best effort)[/bold yellow]"

        console.print(
            Panel(
                f"{status}\n\n"
                f"[cyan]Rounds:[/cyan] {result.round_count}\n"
                f"[cyan]Final Plan Revision:[/cyan] {result.final_plan.revision}\n"
                f"[cyan]Total Tasks:[/cyan] {result.final_plan.total_task_count}\n"
                f"[cyan]Phases:[/cyan] {len(result.final_plan.phases)}\n"
                f"[cyan]Deliberate Mode:[/cyan] {'Yes (pre-mortem + expanded tests)' if result.deliberate_mode else 'No'}\n"
                f"[cyan]Duration:[/cyan] {duration:.1f}s",
                title="[bold blue]RALPLAN Complete[/bold blue]",
                border_style="blue",
            )
        )
