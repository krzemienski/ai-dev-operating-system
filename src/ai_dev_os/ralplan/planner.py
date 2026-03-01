"""
RALPLAN Planner agent.

Creates structured implementation plans and revises them
based on critic feedback until the critic approves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PlanTask:
    """A single task within a plan."""

    id: str
    title: str
    description: str
    phase: str
    complexity: str  # S, M, L
    depends_on: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class PlanPhase:
    """A phase grouping related tasks."""

    name: str
    goal: str
    verification: str
    tasks: list[PlanTask] = field(default_factory=list)


@dataclass
class Plan:
    """
    A complete implementation plan produced by the PlannerAgent.

    Contains phases, tasks, risk assessment, and metadata.
    """

    goal: str
    phases: list[PlanPhase]
    top_risks: list[str]
    total_complexity: str  # estimated effort summary
    revision: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    revision_notes: Optional[str] = None

    @property
    def total_task_count(self) -> int:
        """Return total number of tasks across all phases."""
        return sum(len(p.tasks) for p in self.phases)

    def to_markdown(self) -> str:
        """Render the plan as a markdown document."""
        lines = [
            f"# Implementation Plan",
            f"",
            f"**Goal:** {self.goal}",
            f"**Revision:** {self.revision}",
            f"**Total Tasks:** {self.total_task_count}",
            f"**Complexity:** {self.total_complexity}",
            f"",
            f"---",
            f"",
            f"## Top Risks",
            f"",
        ]
        for i, risk in enumerate(self.top_risks, 1):
            lines.append(f"{i}. {risk}")
        lines.append("")

        for phase in self.phases:
            lines.extend([
                f"---",
                f"",
                f"## Phase: {phase.name}",
                f"**Goal:** {phase.goal}",
                f"**Verification:** {phase.verification}",
                f"",
            ])
            for task in phase.tasks:
                deps = f" *(depends on: {', '.join(task.depends_on)})*" if task.depends_on else ""
                lines.extend([
                    f"### {task.id}: {task.title} [{task.complexity}]{deps}",
                    f"{task.description}",
                    f"",
                ])
                if task.risks:
                    lines.append("**Risks:** " + "; ".join(task.risks))
                    lines.append("")

        if self.revision_notes:
            lines.extend([
                f"---",
                f"",
                f"## Revision Notes",
                f"",
                self.revision_notes,
            ])

        return "\n".join(lines)


class PlannerAgent:
    """
    Creates and revises implementation plans.

    Uses a structured approach to decompose goals into ordered,
    atomic tasks with explicit dependencies and risk flags.
    """

    def create_plan(self, task: str, feedback: Optional[str] = None) -> Plan:
        """
        Create a new implementation plan for the given task.

        Args:
            task: The goal or task to plan for.
            feedback: Optional critic feedback from a previous iteration.

        Returns:
            A structured Plan object.
        """
        # Build a generic but well-structured plan template
        # In production, this would use a Claude API call with the planner system prompt
        phases = self._generate_phases(task, feedback)
        risks = self._identify_risks(task)

        return Plan(
            goal=task,
            phases=phases,
            top_risks=risks,
            total_complexity=self._estimate_complexity(phases),
            revision=0,
        )

    def revise_plan(self, plan: Plan, criticism: str) -> Plan:
        """
        Revise a plan based on critic feedback.

        Args:
            plan: The previously created plan to revise.
            criticism: Specific criticism from the CriticAgent.

        Returns:
            A revised Plan with incremented revision number.
        """
        revised = Plan(
            goal=plan.goal,
            phases=list(plan.phases),  # deep copy in production
            top_risks=list(plan.top_risks),
            total_complexity=plan.total_complexity,
            revision=plan.revision + 1,
            revision_notes=f"Revised in response to critic feedback:\n\n{criticism}",
        )
        return revised

    def _generate_phases(self, task: str, feedback: Optional[str]) -> list[PlanPhase]:
        """Generate a phased task breakdown for the goal."""
        return [
            PlanPhase(
                name="Proof of Concept",
                goal="Validate critical unknowns before committing to implementation",
                verification="Spike result documented, PROCEED/PIVOT decision made",
                tasks=[
                    PlanTask(
                        id="T1.1",
                        title="Spike: validate critical assumptions",
                        description=(
                            f"Before committing to implementation of '{task}', validate "
                            "the highest-risk assumption. Build the smallest possible "
                            "prototype that tests feasibility."
                        ),
                        phase="Proof of Concept",
                        complexity="M",
                        risks=["External API may not support required features"],
                    ),
                ],
            ),
            PlanPhase(
                name="Foundation",
                goal="Establish project structure, data model, and core infrastructure",
                verification="Project builds, schema migrated, repository layer tested",
                tasks=[
                    PlanTask(
                        id="T2.1",
                        title="Project scaffolding and build configuration",
                        description="Create project structure, configure build system, set up CI.",
                        phase="Foundation",
                        complexity="S",
                        depends_on=["T1.1"],
                    ),
                    PlanTask(
                        id="T2.2",
                        title="Data model and schema migration",
                        description="Implement database schema. Create backward-compatible migration.",
                        phase="Foundation",
                        complexity="M",
                        depends_on=["T2.1"],
                    ),
                    PlanTask(
                        id="T2.3",
                        title="Repository layer (data access)",
                        description="Implement CRUD operations, pagination, and query patterns.",
                        phase="Foundation",
                        complexity="M",
                        depends_on=["T2.2"],
                    ),
                ],
            ),
            PlanPhase(
                name="Core Logic",
                goal="Implement business domain and service orchestration",
                verification="Business rules enforced, service layer handles all scenarios",
                tasks=[
                    PlanTask(
                        id="T3.1",
                        title="Domain model and business rules",
                        description="Implement domain entities and business invariants. Pure domain logic only.",
                        phase="Core Logic",
                        complexity="M",
                        depends_on=["T2.1"],
                    ),
                    PlanTask(
                        id="T3.2",
                        title="Service layer",
                        description="Orchestrate domain logic, repository calls, and external integrations.",
                        phase="Core Logic",
                        complexity="M",
                        depends_on=["T2.3", "T3.1"],
                    ),
                ],
            ),
            PlanPhase(
                name="Integration and Validation",
                goal="Connect all layers, add observability, validate end-to-end",
                verification="E2E scenario passes, performance meets targets, docs complete",
                tasks=[
                    PlanTask(
                        id="T4.1",
                        title="End-to-end integration",
                        description="Connect all layers and run complete user journey scenario.",
                        phase="Integration and Validation",
                        complexity="M",
                        depends_on=["T3.2"],
                    ),
                    PlanTask(
                        id="T4.2",
                        title="Observability and documentation",
                        description="Add structured logging, health check, metrics, and API docs.",
                        phase="Integration and Validation",
                        complexity="S",
                        depends_on=["T4.1"],
                    ),
                ],
            ),
        ]

    def _identify_risks(self, task: str) -> list[str]:
        """Identify top risks for the given task."""
        return [
            "External dependency may not support required features (validate in spike)",
            "Performance requirements may not be achievable without infrastructure changes",
            "Existing data migration may be more complex than anticipated",
        ]

    def _estimate_complexity(self, phases: list[PlanPhase]) -> str:
        """Estimate overall complexity from phase tasks."""
        total_tasks = sum(len(p.tasks) for p in phases)
        large = sum(1 for p in phases for t in p.tasks if t.complexity == "L")
        medium = sum(1 for p in phases for t in p.tasks if t.complexity == "M")
        small = sum(1 for p in phases for t in p.tasks if t.complexity == "S")
        return f"{total_tasks} tasks ({large}L + {medium}M + {small}S)"
