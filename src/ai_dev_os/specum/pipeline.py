"""
Specum pipeline — staged specification-to-implementation workflow.

Enforces the discipline of specifying before implementing.
State is persisted between stages so work survives interruptions.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich import box

console = Console()

DEFAULT_STATE_PATH = Path(".omc/state/specum-state.json")
DEFAULT_ARTIFACTS_DIR = Path(".omc/specum")


class PipelineStage(str, Enum):
    """The stages of the Specum pipeline in order."""

    NEW = "new"
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    TASKS = "tasks"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    COMPLETE = "complete"


class PipelineStatus(str, Enum):
    """Overall pipeline execution status."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"


# Ordered stage progression
STAGE_ORDER = [
    PipelineStage.NEW,
    PipelineStage.REQUIREMENTS,
    PipelineStage.DESIGN,
    PipelineStage.TASKS,
    PipelineStage.IMPLEMENT,
    PipelineStage.VERIFY,
    PipelineStage.COMPLETE,
]

STAGE_DESCRIPTIONS = {
    PipelineStage.NEW: "Pipeline initialized, ready to begin",
    PipelineStage.REQUIREMENTS: "Gathering user stories and acceptance criteria",
    PipelineStage.DESIGN: "Creating schema definitions and API contracts",
    PipelineStage.TASKS: "Breaking design into ordered implementation tasks",
    PipelineStage.IMPLEMENT: "Executing tasks with Ralph Loop persistence",
    PipelineStage.VERIFY: "Validating completion with evidence collection",
    PipelineStage.COMPLETE: "Pipeline complete — all stages verified",
}

STAGE_ARTIFACTS = {
    PipelineStage.REQUIREMENTS: "requirements.md",
    PipelineStage.DESIGN: "design.md",
    PipelineStage.TASKS: "tasks.md",
    PipelineStage.IMPLEMENT: "implementation-report.md",
    PipelineStage.VERIFY: "verification-report.md",
}


class StageResult(BaseModel):
    """Result of running a single pipeline stage."""

    stage: PipelineStage
    status: str  # success, failed, skipped
    artifact_path: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class SpecumPipelineState(BaseModel):
    """Persisted state for a Specum pipeline run."""

    goal: str
    current_stage: PipelineStage = PipelineStage.NEW
    status: PipelineStatus = PipelineStatus.ACTIVE
    stage_results: list[StageResult] = Field(default_factory=list)
    artifacts_dir: str = str(DEFAULT_ARTIFACTS_DIR)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class SpecumPipeline:
    """
    Specum specification pipeline.

    Drives development through a mandatory specification sequence:
    Requirements → Design → Tasks → Implement → Verify

    Each stage produces a markdown artifact that the next stage consumes.
    State is persisted between stages so pipelines survive interruptions.

    Example:
        pipeline = SpecumPipeline()
        pipeline.start("Build user authentication with JWT")
        pipeline.advance()  # Run requirements stage
        pipeline.advance()  # Run design stage
        # ... continue until complete
    """

    def __init__(
        self,
        state_path: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize the Specum pipeline.

        Args:
            state_path: Path to state JSON file. Defaults to .omc/state/specum-state.json.
            artifacts_dir: Directory for stage artifacts. Defaults to .omc/specum/.
        """
        self._state_path = state_path or DEFAULT_STATE_PATH
        self._artifacts_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._state: Optional[SpecumPipelineState] = None

    @property
    def state(self) -> SpecumPipelineState:
        """Return current pipeline state, loading from disk if needed."""
        if self._state is None:
            self._state = self._load_state()
        return self._state

    def start(self, goal: str) -> SpecumPipelineState:
        """
        Start a new Specum pipeline.

        Args:
            goal: The goal to build toward. Should be specific and actionable.

        Returns:
            Initial pipeline state.
        """
        self._state = SpecumPipelineState(
            goal=goal,
            artifacts_dir=str(self._artifacts_dir),
        )
        self._save_state()

        console.print(
            Panel(
                f"[bold green]SPECUM PIPELINE STARTED[/bold green]\n\n"
                f"[cyan]Goal:[/cyan] {goal}\n"
                f"[cyan]Stages:[/cyan] requirements → design → tasks → implement → verify\n"
                f"[cyan]Artifacts:[/cyan] {self._artifacts_dir}\n\n"
                f"[dim]Run advance() to progress through each stage[/dim]",
                title="[bold blue]📋 Specum Pipeline[/bold blue]",
                border_style="blue",
            )
        )
        return self._state

    def advance(self) -> Optional[StageResult]:
        """
        Advance the pipeline to the next stage and run it.

        Returns:
            StageResult for the completed stage, or None if already complete.
        """
        state = self.state
        if state.current_stage == PipelineStage.COMPLETE:
            console.print("[bold green]Pipeline is already complete![/bold green]")
            return None

        # Determine next stage
        current_idx = STAGE_ORDER.index(state.current_stage)
        if current_idx >= len(STAGE_ORDER) - 1:
            return None

        next_stage = STAGE_ORDER[current_idx + 1]
        result = self.run_stage(next_stage)

        state.current_stage = next_stage
        if next_stage == PipelineStage.COMPLETE:
            state.status = PipelineStatus.COMPLETE

        state.stage_results.append(result)
        self._save_state()
        return result

    def run_stage(self, stage: PipelineStage) -> StageResult:
        """
        Run a specific pipeline stage.

        Args:
            stage: The stage to execute.

        Returns:
            StageResult with artifact path and status.
        """
        console.print(
            f"\n[bold cyan]━━━ STAGE: {stage.value.upper()} ━━━[/bold cyan]\n"
            f"[dim]{STAGE_DESCRIPTIONS.get(stage, '')}[/dim]\n"
        )

        # Import and run the appropriate stage class
        try:
            artifact_content = self._dispatch_stage(stage)
            artifact_path = self._write_artifact(stage, artifact_content)

            result = StageResult(
                stage=stage,
                status="success",
                artifact_path=str(artifact_path) if artifact_path else None,
                completed_at=datetime.utcnow(),
            )
            console.print(f"[bold green]✓ Stage '{stage.value}' complete[/bold green]")
            if artifact_path:
                console.print(f"[dim]  Artifact: {artifact_path}[/dim]")
            return result

        except Exception as e:
            result = StageResult(
                stage=stage,
                status="failed",
                error=str(e),
                completed_at=datetime.utcnow(),
            )
            console.print(f"[bold red]✗ Stage '{stage.value}' failed: {e}[/bold red]")
            self.state.status = PipelineStatus.FAILED
            return result

    def _dispatch_stage(self, stage: PipelineStage) -> str:
        """
        Dispatch to the appropriate stage class.

        Args:
            stage: The stage to run.

        Returns:
            Artifact content as a markdown string.
        """
        from ai_dev_os.specum.stages import (
            RequirementsStage,
            DesignStage,
            TaskStage,
            ImplementStage,
            VerifyStage,
        )

        goal = self.state.goal
        previous_artifact = self._get_latest_artifact()

        stage_map = {
            PipelineStage.REQUIREMENTS: lambda: RequirementsStage(goal).generate(),
            PipelineStage.DESIGN: lambda: DesignStage(goal, previous_artifact).generate(),
            PipelineStage.TASKS: lambda: TaskStage(goal, previous_artifact).generate(),
            PipelineStage.IMPLEMENT: lambda: ImplementStage(goal, previous_artifact).generate(),
            PipelineStage.VERIFY: lambda: VerifyStage(goal, previous_artifact).generate(),
            PipelineStage.COMPLETE: lambda: "# Pipeline Complete\n\nAll stages finished successfully.",
        }

        runner = stage_map.get(stage)
        if runner is None:
            raise ValueError(f"No stage runner for stage: {stage}")
        return runner()

    def _write_artifact(self, stage: PipelineStage, content: str) -> Optional[Path]:
        """Write stage artifact to disk."""
        filename = STAGE_ARTIFACTS.get(stage)
        if not filename:
            return None
        path = self._artifacts_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def _get_latest_artifact(self) -> Optional[str]:
        """Read the most recently produced artifact."""
        for stage in reversed(STAGE_ORDER):
            filename = STAGE_ARTIFACTS.get(stage)
            if filename:
                path = self._artifacts_dir / filename
                if path.exists():
                    return path.read_text(encoding="utf-8")
        return None

    def current_stage(self) -> PipelineStage:
        """Return the current pipeline stage."""
        return self.state.current_stage

    def status(self) -> Table:
        """Render pipeline status as a rich Table."""
        state = self.state
        table = Table(
            title=f"Specum Pipeline — {state.goal[:60]}",
            box=box.ROUNDED,
            header_style="bold magenta",
        )
        table.add_column("Stage", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Artifact")
        table.add_column("Description", style="dim")

        completed_stages = {r.stage for r in state.stage_results if r.status == "success"}

        for stage in STAGE_ORDER[1:]:  # Skip NEW
            if stage in completed_stages:
                status_cell = "[bold green]✓ complete[/bold green]"
            elif stage == state.current_stage:
                status_cell = "[bold yellow]→ current[/bold yellow]"
            else:
                status_cell = "[dim]pending[/dim]"

            artifact = STAGE_ARTIFACTS.get(stage, "—")
            desc = STAGE_DESCRIPTIONS.get(stage, "")
            table.add_row(stage.value, status_cell, artifact, desc[:50])

        return table

    def _load_state(self) -> SpecumPipelineState:
        """Load state from disk or return fresh state."""
        if self._state_path.exists():
            with open(self._state_path) as f:
                raw = json.load(f)
            return SpecumPipelineState(**raw)
        return SpecumPipelineState(goal="")

    def _save_state(self) -> None:
        """Persist current state to disk."""
        if self._state:
            self._state.last_updated = datetime.utcnow()
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(self._state.model_dump(mode="json"), f, indent=2, default=str)
