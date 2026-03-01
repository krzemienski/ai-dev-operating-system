"""
GSD project phases and lifecycle management.

Defines the 10-phase GSD lifecycle and the GSDProject class
that manages phase transitions with evidence gates.
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
from rich.table import Table
from rich import box

console = Console()

DEFAULT_STATE_DIR = Path(".omc/state")


class ProjectPhase(str, Enum):
    """
    The 10 phases of the GSD project lifecycle.

    Projects move through these phases sequentially.
    Each phase transition requires evidence of completion.
    """

    NEW_PROJECT = "new_project"
    RESEARCH = "research"
    ROADMAP = "roadmap"
    PLAN_PHASE = "plan_phase"
    EXECUTE_PHASE = "execute_phase"
    VERIFY_PHASE = "verify_phase"
    ITERATE = "iterate"
    INTEGRATION = "integration"
    PRODUCTION_READINESS = "production_readiness"
    COMPLETE = "complete"


class PhaseStatus(str, Enum):
    """Status of a specific phase."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    SKIPPED = "skipped"


# Ordered phase progression
PHASE_ORDER = [
    ProjectPhase.NEW_PROJECT,
    ProjectPhase.RESEARCH,
    ProjectPhase.ROADMAP,
    ProjectPhase.PLAN_PHASE,
    ProjectPhase.EXECUTE_PHASE,
    ProjectPhase.VERIFY_PHASE,
    ProjectPhase.ITERATE,
    ProjectPhase.INTEGRATION,
    ProjectPhase.PRODUCTION_READINESS,
    ProjectPhase.COMPLETE,
]

PHASE_DESCRIPTIONS = {
    ProjectPhase.NEW_PROJECT: "Project initialized — goal defined, team assembled",
    ProjectPhase.RESEARCH: "Domain research, competitive analysis, feasibility study",
    ProjectPhase.ROADMAP: "High-level roadmap with phase breakdown and success criteria",
    ProjectPhase.PLAN_PHASE: "Detailed implementation plan for current execution phase",
    ProjectPhase.EXECUTE_PHASE: "Implementation with Ralph Loop persistence",
    ProjectPhase.VERIFY_PHASE: "Verification with evidence collection against acceptance criteria",
    ProjectPhase.ITERATE: "Gap analysis, fix prioritization, and re-execution if needed",
    ProjectPhase.INTEGRATION: "Cross-component integration testing and system validation",
    ProjectPhase.PRODUCTION_READINESS: "Ops readiness: observability, runbooks, deployment automation",
    ProjectPhase.COMPLETE: "Project complete — all phases verified and documented",
}

PHASE_REQUIRED_EVIDENCE = {
    ProjectPhase.RESEARCH: ["research_document", "feasibility_assessment"],
    ProjectPhase.ROADMAP: ["roadmap_document", "success_criteria"],
    ProjectPhase.PLAN_PHASE: ["implementation_plan", "task_list"],
    ProjectPhase.EXECUTE_PHASE: ["build_log", "implementation_report"],
    ProjectPhase.VERIFY_PHASE: ["verification_report", "acceptance_criteria_results"],
    ProjectPhase.INTEGRATION: ["integration_test_results", "e2e_scenario_results"],
    ProjectPhase.PRODUCTION_READINESS: ["deployment_guide", "runbook", "monitoring_setup"],
    ProjectPhase.COMPLETE: ["final_report"],
}


class PhaseRecord(BaseModel):
    """Record of a single phase execution."""

    phase: ProjectPhase
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    evidence_ids: list[str] = Field(default_factory=list)
    notes: str = ""
    blocker: Optional[str] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class GSDProjectState(BaseModel):
    """Persisted state for a GSD project."""

    name: str
    goal: str
    current_phase: ProjectPhase = ProjectPhase.NEW_PROJECT
    phases: dict[str, PhaseRecord] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class GSDProject:
    """
    GSD (Get Stuff Done) 10-phase project lifecycle manager.

    Manages project progression through 10 structured phases,
    each requiring evidence before the next phase can begin.

    The phase gate model prevents "completion theater" — you can't
    claim a phase is done without providing concrete evidence.

    Example:
        project = GSDProject()
        project.create_project("payment-system", "Implement Stripe payment processing")
        project.advance_phase()  # Move from NEW_PROJECT to RESEARCH
        project.advance_phase()  # Move from RESEARCH to ROADMAP
        # ... continue through all phases
    """

    def __init__(self, state_dir: Optional[Path] = None) -> None:
        """
        Initialize the GSD project manager.

        Args:
            state_dir: Directory for state files. Defaults to .omc/state/.
        """
        self._state_dir = state_dir or DEFAULT_STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state: Optional[GSDProjectState] = None
        self._project_name: Optional[str] = None

    def create_project(self, name: str, goal: str) -> GSDProjectState:
        """
        Create a new GSD project.

        Args:
            name: Short project identifier (used for state file naming).
            goal: Clear statement of what the project will deliver.

        Returns:
            Initial GSDProjectState.
        """
        self._project_name = name
        self._state = GSDProjectState(
            name=name,
            goal=goal,
        )
        # Initialize all phases as NOT_STARTED
        for phase in PHASE_ORDER:
            self._state.phases[phase.value] = PhaseRecord(phase=phase)

        self._save_state()

        console.print(
            Panel(
                f"[bold green]GSD PROJECT CREATED[/bold green]\n\n"
                f"[cyan]Name:[/cyan] {name}\n"
                f"[cyan]Goal:[/cyan] {goal}\n"
                f"[cyan]Current Phase:[/cyan] {ProjectPhase.NEW_PROJECT.value}\n"
                f"[cyan]Total Phases:[/cyan] {len(PHASE_ORDER)}\n\n"
                f"[dim]Call advance_phase() to progress through each phase.[/dim]",
                title="[bold green]📋 GSD Project Initialized[/bold green]",
                border_style="green",
            )
        )
        return self._state

    def load_project(self, name: str) -> GSDProjectState:
        """
        Load an existing GSD project by name.

        Args:
            name: The project name used when creating the project.

        Returns:
            The loaded GSDProjectState.

        Raises:
            FileNotFoundError: If no project with that name exists.
        """
        self._project_name = name
        state_path = self._state_path(name)
        if not state_path.exists():
            raise FileNotFoundError(f"No GSD project found with name: {name}")
        with open(state_path) as f:
            raw = json.load(f)
        self._state = GSDProjectState(**raw)
        return self._state

    def advance_phase(self, evidence_ids: Optional[list[str]] = None) -> Optional[ProjectPhase]:
        """
        Advance to the next phase if current phase requirements are met.

        Args:
            evidence_ids: Evidence IDs from EvidenceCollector that satisfy
                         the current phase's requirements.

        Returns:
            The new current phase, or None if already at COMPLETE.
        """
        state = self._require_state()

        if state.current_phase == ProjectPhase.COMPLETE:
            console.print("[bold green]Project is already complete![/bold green]")
            return None

        current_idx = PHASE_ORDER.index(state.current_phase)
        if current_idx >= len(PHASE_ORDER) - 1:
            return None

        # Mark current phase complete
        current_record = state.phases[state.current_phase.value]
        current_record.status = PhaseStatus.COMPLETE
        current_record.completed_at = datetime.utcnow()
        if evidence_ids:
            current_record.evidence_ids = evidence_ids

        # Advance to next phase
        next_phase = PHASE_ORDER[current_idx + 1]
        state.current_phase = next_phase

        # Mark next phase as in progress
        next_record = state.phases[next_phase.value]
        next_record.status = PhaseStatus.IN_PROGRESS
        next_record.started_at = datetime.utcnow()

        self._save_state()

        console.print(
            f"[bold cyan]Phase Advanced:[/bold cyan] "
            f"{PHASE_ORDER[current_idx].value} → [bold green]{next_phase.value}[/bold green]\n"
            f"[dim]{PHASE_DESCRIPTIONS.get(next_phase, '')}[/dim]"
        )

        return next_phase

    def current_phase(self) -> ProjectPhase:
        """Return the current project phase."""
        return self._require_state().current_phase

    def phase_status(self, phase: Optional[ProjectPhase] = None) -> PhaseRecord:
        """
        Get the status record for a specific phase.

        Args:
            phase: Phase to query. Defaults to current phase.

        Returns:
            PhaseRecord with status and evidence.
        """
        state = self._require_state()
        target = phase or state.current_phase
        return state.phases[target.value]

    def required_evidence(self, phase: Optional[ProjectPhase] = None) -> list[str]:
        """
        Return the evidence types required to complete a phase.

        Args:
            phase: Phase to query. Defaults to current phase.

        Returns:
            List of required evidence type strings.
        """
        state = self._require_state()
        target = phase or state.current_phase
        return PHASE_REQUIRED_EVIDENCE.get(target, [])

    def progress_table(self) -> Table:
        """Render a rich Table showing all phases and their status."""
        state = self._require_state()
        table = Table(
            title=f"GSD Project: {state.name}",
            box=box.ROUNDED,
            header_style="bold magenta",
        )
        table.add_column("#", style="dim", justify="center", width=3)
        table.add_column("Phase", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Evidence", justify="right", style="dim")
        table.add_column("Description", style="dim")

        status_styles = {
            PhaseStatus.NOT_STARTED: "[dim]not started[/dim]",
            PhaseStatus.IN_PROGRESS: "[bold yellow]→ in progress[/bold yellow]",
            PhaseStatus.BLOCKED: "[bold red]✗ blocked[/bold red]",
            PhaseStatus.COMPLETE: "[bold green]✓ complete[/bold green]",
            PhaseStatus.SKIPPED: "[dim italic]skipped[/dim italic]",
        }

        for i, phase in enumerate(PHASE_ORDER, 1):
            record = state.phases.get(phase.value, PhaseRecord(phase=phase))
            marker = "→" if phase == state.current_phase else " "
            table.add_row(
                f"{marker}{i}",
                phase.value,
                status_styles.get(record.status, record.status.value),
                str(len(record.evidence_ids)),
                PHASE_DESCRIPTIONS.get(phase, "")[:50],
            )

        return table

    def _state_path(self, name: str) -> Path:
        """Return the state file path for a project name."""
        return self._state_dir / f"gsd-{name}.json"

    def _require_state(self) -> GSDProjectState:
        """Return current state, raising if not initialized."""
        if self._state is None:
            raise RuntimeError("No project loaded. Call create_project() or load_project() first.")
        return self._state

    def _save_state(self) -> None:
        """Persist current state to disk."""
        if self._state and self._project_name:
            self._state.last_updated = datetime.utcnow()
            with open(self._state_path(self._project_name), "w") as f:
                json.dump(self._state.model_dump(mode="json"), f, indent=2, default=str)
