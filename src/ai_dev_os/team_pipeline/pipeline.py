"""
Team Pipeline — staged multi-agent execution engine.

Implements the canonical OMC staged pipeline:
PLAN → PRD → EXEC → VERIFY → FIX (loop, bounded)

Terminal states: COMPLETE, FAILED, CANCELLED
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from ai_dev_os.team_pipeline.stages import (
    BaseStage,
    ExecStage,
    FixStage,
    PRDStage,
    PlanStage,
    StageResult,
    VerifyStage,
)

console = Console()

DEFAULT_STATE_PATH = Path(".omc/state/team-state.json")


class PipelineStage(str, Enum):
    """Stages of the Team Pipeline."""

    PLAN = "team-plan"
    PRD = "team-prd"
    EXEC = "team-exec"
    VERIFY = "team-verify"
    FIX = "team-fix"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStatus(str, Enum):
    """Overall pipeline status."""

    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Ordered progression (fix loops back to verify)
PIPELINE_PROGRESSION = {
    PipelineStage.PLAN: PipelineStage.PRD,
    PipelineStage.PRD: PipelineStage.EXEC,
    PipelineStage.EXEC: PipelineStage.VERIFY,
    PipelineStage.VERIFY: PipelineStage.COMPLETE,  # on pass
    PipelineStage.FIX: PipelineStage.VERIFY,  # fix feeds back to verify
}

STAGE_CLASSES: dict[PipelineStage, type[BaseStage]] = {
    PipelineStage.PLAN: PlanStage,
    PipelineStage.PRD: PRDStage,
    PipelineStage.EXEC: ExecStage,
    PipelineStage.VERIFY: VerifyStage,
    PipelineStage.FIX: FixStage,
}


class StageHistory(BaseModel):
    """Record of a completed stage run."""

    stage: str
    success: bool
    artifact_names: list[str] = Field(default_factory=list)
    findings_count: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class TeamPipelineState(BaseModel):
    """Persisted state for a Team Pipeline execution."""

    task: str
    current_stage: PipelineStage = PipelineStage.PLAN
    status: PipelineStatus = PipelineStatus.ACTIVE
    fix_loop_count: int = 0
    max_fix_loops: int = 3
    stage_history: list[StageHistory] = Field(default_factory=list)
    all_artifacts: dict[str, str] = Field(default_factory=dict)
    all_findings: list[str] = Field(default_factory=list)
    linked_ralph: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    @property
    def is_terminal(self) -> bool:
        """Return True if pipeline is in a terminal state."""
        return self.status in (PipelineStatus.COMPLETE, PipelineStatus.FAILED, PipelineStatus.CANCELLED)


class TeamPipeline:
    """
    Team Pipeline — canonical OMC staged multi-agent execution.

    Runs a structured PLAN → PRD → EXEC → VERIFY → FIX pipeline
    where each stage uses specialized agents.

    The FIX stage loops back to VERIFY until all findings are resolved
    or the maximum fix loop count is exceeded (→ FAILED).

    State is persisted after each stage transition so the pipeline
    can be resumed after interruption.

    Example:
        pipeline = TeamPipeline()
        pipeline.start("Implement Stripe payment processing")

        while not pipeline.state.is_terminal:
            pipeline.advance_stage()

        print(f"Pipeline {pipeline.state.status.value}")
    """

    def __init__(self, state_path: Optional[Path] = None) -> None:
        """
        Initialize the Team Pipeline.

        Args:
            state_path: Path to state JSON file. Defaults to .omc/state/team-state.json.
        """
        self._state_path = state_path or DEFAULT_STATE_PATH
        self._state: Optional[TeamPipelineState] = None

    @property
    def state(self) -> TeamPipelineState:
        """Return current state, loading from disk if needed."""
        if self._state is None:
            self._state = self._load_state()
        return self._state

    def start(
        self,
        task: str,
        max_fix_loops: int = 3,
        linked_ralph: Optional[str] = None,
    ) -> TeamPipelineState:
        """
        Start a new Team Pipeline execution.

        Args:
            task: The task or goal to execute.
            max_fix_loops: Maximum FIX stage iterations before failing. Default: 3.
            linked_ralph: Optional Ralph Loop session to link with.

        Returns:
            Initial pipeline state.
        """
        self._state = TeamPipelineState(
            task=task,
            max_fix_loops=max_fix_loops,
            linked_ralph=linked_ralph,
        )
        self._save_state()

        console.print(
            Panel(
                f"[bold green]TEAM PIPELINE STARTED[/bold green]\n\n"
                f"[cyan]Task:[/cyan] {task}\n"
                f"[cyan]Pipeline:[/cyan] PLAN → PRD → EXEC → VERIFY → FIX (max {max_fix_loops}x)\n"
                f"[cyan]First Stage:[/cyan] {PipelineStage.PLAN.value}",
                title="[bold magenta]🚀 Team Pipeline[/bold magenta]",
                border_style="magenta",
            )
        )
        return self._state

    def advance_stage(self) -> Optional[StageResult]:
        """
        Execute the current stage and advance to the next.

        Returns:
            StageResult for the completed stage, or None if in terminal state.
        """
        state = self.state
        if state.is_terminal:
            console.print(f"[bold yellow]Pipeline is in terminal state: {state.status.value}[/bold yellow]")
            return None

        current = state.current_stage
        console.print(f"\n[bold magenta]━━━ STAGE: {current.value.upper()} ━━━[/bold magenta]")

        # Run the current stage
        stage_class = STAGE_CLASSES.get(current)
        if stage_class is None:
            console.print(f"[red]No stage class for {current}[/red]")
            return None

        stage_instance = stage_class()
        context = self._build_context()
        result = stage_instance.run(context)

        # Record history
        history = StageHistory(
            stage=current.value,
            success=result.success,
            artifact_names=[a.name for a in result.artifacts],
            findings_count=len(result.findings),
            completed_at=datetime.utcnow(),
        )
        state.stage_history.append(history)

        # Store artifacts
        for artifact in result.artifacts:
            state.all_artifacts[artifact.name] = artifact.content

        # Store findings
        state.all_findings.extend(result.findings)

        # Determine next stage
        self._transition(current, result)
        self._save_state()

        return result

    def current_stage(self) -> PipelineStage:
        """Return the current pipeline stage."""
        return self.state.current_stage

    def status(self) -> Table:
        """Render pipeline status as a rich Table."""
        state = self.state
        table = Table(
            title=f"Team Pipeline — {state.task[:60]}",
            box=box.ROUNDED,
            header_style="bold magenta",
        )
        table.add_column("Stage", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Artifacts", justify="right", style="dim")
        table.add_column("Findings", justify="right", style="dim")

        all_stages = [
            PipelineStage.PLAN,
            PipelineStage.PRD,
            PipelineStage.EXEC,
            PipelineStage.VERIFY,
            PipelineStage.FIX,
        ]

        completed = {h.stage for h in state.stage_history if h.success}
        failed = {h.stage for h in state.stage_history if not h.success}

        for stage in all_stages:
            if stage.value in completed:
                status_cell = "[bold green]✓ complete[/bold green]"
            elif stage.value in failed:
                status_cell = "[bold red]✗ failed[/bold red]"
            elif stage == state.current_stage and not state.is_terminal:
                status_cell = "[bold yellow]→ current[/bold yellow]"
            else:
                status_cell = "[dim]pending[/dim]"

            runs = [h for h in state.stage_history if h.stage == stage.value]
            artifact_count = sum(len(r.artifact_names) for r in runs)
            findings_count = sum(r.findings_count for r in runs)

            table.add_row(
                stage.value,
                status_cell,
                str(artifact_count) if artifact_count else "—",
                str(findings_count) if findings_count else "—",
            )

        return table

    def cancel(self) -> None:
        """Cancel the pipeline."""
        state = self.state
        state.status = PipelineStatus.CANCELLED
        state.current_stage = PipelineStage.CANCELLED
        self._save_state()
        console.print("[bold yellow]Pipeline cancelled.[/bold yellow]")

    def _transition(self, current: PipelineStage, result: StageResult) -> None:
        """Determine and apply the next stage transition."""
        state = self.state

        if current == PipelineStage.VERIFY:
            if result.success:
                # Verification passed — pipeline complete!
                state.current_stage = PipelineStage.COMPLETE
                state.status = PipelineStatus.COMPLETE
                console.print(
                    Panel(
                        "[bold green]PIPELINE COMPLETE![/bold green]\n\n"
                        "All stages passed verification. Work is done.",
                        border_style="green",
                    )
                )
            else:
                # Verification failed — enter fix loop
                if state.fix_loop_count >= state.max_fix_loops:
                    state.current_stage = PipelineStage.FAILED
                    state.status = PipelineStatus.FAILED
                    console.print(
                        Panel(
                            f"[bold red]PIPELINE FAILED[/bold red]\n\n"
                            f"Max fix loops ({state.max_fix_loops}) exceeded.\n"
                            f"Remaining findings: {len(result.findings)}",
                            border_style="red",
                        )
                    )
                else:
                    state.fix_loop_count += 1
                    state.current_stage = PipelineStage.FIX
                    console.print(
                        f"[bold yellow]Verification FAIL → FIX stage "
                        f"(attempt {state.fix_loop_count}/{state.max_fix_loops})[/bold yellow]"
                    )

        elif current == PipelineStage.FIX:
            # Fix feeds back to verify
            state.current_stage = PipelineStage.VERIFY
            console.print("[cyan]Fix complete → re-running VERIFY[/cyan]")

        else:
            # Normal progression
            next_stage = PIPELINE_PROGRESSION.get(current)
            if next_stage:
                state.current_stage = next_stage
                console.print(f"[green]✓ {current.value} → {next_stage.value}[/green]")

    def _build_context(self) -> dict[str, Any]:
        """Build context dict for the current stage."""
        state = self.state
        return {
            "task": state.task,
            "artifacts": state.all_artifacts,
            "findings": state.all_findings,
            "fix_loop_count": state.fix_loop_count,
            "stage_history": state.stage_history,
        }

    def _load_state(self) -> TeamPipelineState:
        """Load state from disk or return fresh state."""
        if self._state_path.exists():
            with open(self._state_path) as f:
                raw = json.load(f)
            return TeamPipelineState(**raw)
        return TeamPipelineState(task="")

    def _save_state(self) -> None:
        """Persist current state to disk."""
        if self._state:
            self._state.last_updated = datetime.utcnow()
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(self._state.model_dump(mode="json"), f, indent=2, default=str)
