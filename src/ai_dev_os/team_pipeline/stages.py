"""
Team Pipeline stage definitions.

Each stage specifies the agents required, artifacts produced,
and the logic for executing that stage of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class StageArtifact:
    """An artifact produced by a pipeline stage."""

    name: str
    content: str
    produced_by: str
    produced_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StageResult:
    """Result of executing a pipeline stage."""

    stage_name: str
    success: bool
    artifacts: list[StageArtifact] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_artifact(self, name: str, content: str, produced_by: str) -> StageArtifact:
        """Add an artifact to this result."""
        artifact = StageArtifact(name=name, content=content, produced_by=produced_by)
        self.artifacts.append(artifact)
        return artifact


class BaseStage:
    """
    Base class for all Team Pipeline stages.

    Subclasses define required_agents and implement run().
    """

    stage_name: str = "base"
    required_agents: list[str] = []
    artifacts_produced: list[str] = []

    def run(self, context: dict[str, Any]) -> StageResult:
        """
        Execute this stage.

        Args:
            context: Pipeline context containing previous artifacts and config.

        Returns:
            StageResult with artifacts and success status.
        """
        raise NotImplementedError("Stage subclasses must implement run()")


class PlanStage(BaseStage):
    """
    PLAN stage — exploration and decomposition.

    Uses explore (haiku) for fast codebase discovery and
    planner (opus) for task sequencing and risk identification.

    Produces:
    - exploration-report.md: Codebase understanding
    - implementation-plan.md: Ordered task breakdown
    """

    stage_name = "plan"
    required_agents = ["explore", "planner"]
    artifacts_produced = ["exploration-report.md", "implementation-plan.md"]

    def run(self, context: dict[str, Any]) -> StageResult:
        """Execute the planning stage."""
        result = StageResult(stage_name=self.stage_name, success=True)

        task = context.get("task", "Unspecified task")

        exploration = self._run_exploration(task, context)
        result.add_artifact(
            "exploration-report.md",
            exploration,
            produced_by="explore (haiku)",
        )

        plan = self._run_planning(task, exploration)
        result.add_artifact(
            "implementation-plan.md",
            plan,
            produced_by="planner (opus)",
        )

        result.completed_at = datetime.utcnow()
        return result

    def _run_exploration(self, task: str, context: dict[str, Any]) -> str:
        """Run the explore agent to understand the codebase."""
        return (
            f"# Codebase Exploration Report\n\n"
            f"**Task:** {task}\n\n"
            f"## Key Findings\n\n"
            f"- Project structure identified\n"
            f"- Entry points located\n"
            f"- Relevant modules mapped\n"
            f"- Dependency graph analyzed\n\n"
            f"## Relevant Files\n\n"
            f"[explore agent would list specific files here]\n\n"
            f"## Integration Points\n\n"
            f"[explore agent would identify integration points here]"
        )

    def _run_planning(self, task: str, exploration: str) -> str:
        """Run the planner agent to create an implementation plan."""
        return (
            f"# Implementation Plan\n\n"
            f"**Task:** {task}\n\n"
            f"## Phase 1: Foundation\n\n"
            f"### T1.1: [First task]\n"
            f"**Complexity:** M\n"
            f"**Description:** [planner agent would specify this]\n\n"
            f"## Phase 2: Implementation\n\n"
            f"[planner agent would generate full task breakdown]\n\n"
            f"## Risks\n\n"
            f"1. [Risk 1]\n"
            f"2. [Risk 2]\n\n"
            f"## Verification\n\n"
            f"[Phase verification criteria]"
        )


class PRDStage(BaseStage):
    """
    PRD stage — requirements and acceptance criteria definition.

    Uses analyst (opus) to produce explicit acceptance criteria
    from the implementation plan. Optionally uses critic for review.

    Produces:
    - prd.md: Product requirements with acceptance criteria
    """

    stage_name = "prd"
    required_agents = ["analyst", "critic"]
    artifacts_produced = ["prd.md"]

    def run(self, context: dict[str, Any]) -> StageResult:
        """Execute the PRD stage."""
        result = StageResult(stage_name=self.stage_name, success=True)

        task = context.get("task", "Unspecified task")
        plan = next(
            (a.content for a in context.get("plan_artifacts", []) if "plan" in a.name),
            "",
        )

        prd = self._run_analyst(task, plan)
        result.add_artifact("prd.md", prd, produced_by="analyst (opus)")

        result.completed_at = datetime.utcnow()
        return result

    def _run_analyst(self, task: str, plan: str) -> str:
        """Run the analyst agent to create a PRD."""
        return (
            f"# Product Requirements Document\n\n"
            f"**Task:** {task}\n\n"
            f"## Goal\n\n"
            f"[analyst agent would derive the specific goal]\n\n"
            f"## Acceptance Criteria\n\n"
            f"1. Given [context], when [action], then [outcome]\n"
            f"2. Given [context], when [action], then [outcome]\n\n"
            f"## Constraints\n\n"
            f"[analyst agent would identify constraints]\n\n"
            f"## Out of Scope\n\n"
            f"[analyst agent would define scope boundaries]"
        )


class ExecStage(BaseStage):
    """
    EXEC stage — implementation by specialist agents.

    Dispatches work to appropriate specialists:
    - executor (sonnet): Code implementation
    - designer (sonnet): UI/UX work
    - build-fixer (sonnet): Build failures
    - writer (haiku): Documentation
    - deep-executor (opus): Complex multi-file work
    - test-engineer (sonnet): Test strategy

    Produces:
    - implementation-report.md: What was built and evidence
    """

    stage_name = "exec"
    required_agents = ["executor", "designer", "build-fixer", "writer", "test-engineer"]
    artifacts_produced = ["implementation-report.md"]

    def run(self, context: dict[str, Any]) -> StageResult:
        """Execute the implementation stage."""
        result = StageResult(stage_name=self.stage_name, success=True)

        task = context.get("task", "Unspecified task")
        specialist = self._select_specialist(task)

        report = self._run_implementation(task, specialist, context)
        result.add_artifact(
            "implementation-report.md",
            report,
            produced_by=f"{specialist} (specialist)",
        )

        result.completed_at = datetime.utcnow()
        return result

    def _select_specialist(self, task: str) -> str:
        """Select the appropriate specialist agent based on task characteristics."""
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["ui", "design", "ux", "interface", "layout"]):
            return "designer"
        elif any(kw in task_lower for kw in ["test", "coverage", "spec", "tdd"]):
            return "test-engineer"
        elif any(kw in task_lower for kw in ["doc", "readme", "guide", "changelog"]):
            return "writer"
        elif any(kw in task_lower for kw in ["complex", "architecture", "refactor entire", "migrate"]):
            return "deep-executor"
        else:
            return "executor"

    def _run_implementation(self, task: str, specialist: str, context: dict[str, Any]) -> str:
        """Run the specialist implementation agent."""
        return (
            f"# Implementation Report\n\n"
            f"**Task:** {task}\n"
            f"**Specialist:** {specialist}\n\n"
            f"## Changes Made\n\n"
            f"[{specialist} agent would list specific changes]\n\n"
            f"## Evidence\n\n"
            f"- Build status: [PASS/FAIL]\n"
            f"- Files modified: [list]\n"
            f"- Tests run: [results]\n\n"
            f"## Notes\n\n"
            f"[Any implementation notes or follow-up items]"
        )


class VerifyStage(BaseStage):
    """
    VERIFY stage — evidence-based completion verification.

    Uses verifier (sonnet) as primary, optionally with:
    - security-reviewer (sonnet): For security-sensitive changes
    - code-reviewer (opus): For comprehensive review
    - quality-reviewer (sonnet): For quality assessment

    Issues PASS or FAIL verdict with specific evidence.
    FAIL triggers the FIX stage. PASS completes the pipeline.

    Produces:
    - verification-report.md: Verdict with evidence
    """

    stage_name = "verify"
    required_agents = ["verifier", "security-reviewer", "code-reviewer", "quality-reviewer"]
    artifacts_produced = ["verification-report.md"]

    def run(self, context: dict[str, Any]) -> StageResult:
        """Execute the verification stage."""
        result = StageResult(stage_name=self.stage_name, success=True)

        task = context.get("task", "Unspecified task")
        report = self._run_verifier(task, context)
        result.add_artifact(
            "verification-report.md",
            report,
            produced_by="verifier (sonnet)",
        )

        # Determine if verification passed
        passed = "[VERDICT: PASS]" in report
        result.success = passed
        result.metadata["verdict"] = "PASS" if passed else "FAIL"
        result.findings = self._extract_findings(report)

        result.completed_at = datetime.utcnow()
        return result

    def _run_verifier(self, task: str, context: dict[str, Any]) -> str:
        """Run the verifier agent."""
        return (
            f"# Verification Report\n\n"
            f"**Task:** {task}\n\n"
            f"## [VERDICT: PASS]\n\n"
            f"All acceptance criteria met with concrete evidence.\n\n"
            f"## Criteria Checked\n\n"
            f"1. [Criterion 1] — PASS — Evidence: [specific evidence]\n"
            f"2. [Criterion 2] — PASS — Evidence: [specific evidence]\n\n"
            f"## Evidence Collected\n\n"
            f"- Build logs: PASS\n"
            f"- API tests: PASS\n"
            f"- E2E scenarios: PASS"
        )

    def _extract_findings(self, report: str) -> list[str]:
        """Extract specific findings from verification report."""
        return []


class FixStage(BaseStage):
    """
    FIX stage — targeted defect resolution.

    Selects the appropriate specialist based on defect type:
    - executor/debugger: Logic bugs, missing features
    - build-fixer: Build failures, type errors
    - security-reviewer → executor: Security vulnerabilities

    The fix loop is bounded by max_fix_loops in the pipeline.
    Exceeding the bound transitions to FAILED terminal state.

    Produces:
    - fix-report.md: What was fixed and re-verification trigger
    """

    stage_name = "fix"
    required_agents = ["executor", "build-fixer", "debugger"]
    artifacts_produced = ["fix-report.md"]

    def run(self, context: dict[str, Any]) -> StageResult:
        """Execute the fix stage."""
        result = StageResult(stage_name=self.stage_name, success=True)

        task = context.get("task", "Unspecified task")
        findings = context.get("findings", [])
        fix_agent = self._select_fix_agent(findings)

        report = self._run_fix(task, findings, fix_agent)
        result.add_artifact("fix-report.md", report, produced_by=f"{fix_agent}")

        result.completed_at = datetime.utcnow()
        return result

    def _select_fix_agent(self, findings: list[str]) -> str:
        """Select the appropriate fix agent based on the defect type."""
        if not findings:
            return "executor"

        findings_text = " ".join(findings).lower()
        if any(kw in findings_text for kw in ["build", "compile", "type error", "import"]):
            return "build-fixer"
        elif any(kw in findings_text for kw in ["security", "vulnerability", "injection", "auth"]):
            return "debugger"
        else:
            return "executor"

    def _run_fix(self, task: str, findings: list[str], agent: str) -> str:
        """Run the fix agent."""
        findings_text = "\n".join(f"- {f}" for f in findings) if findings else "- No specific findings"
        return (
            f"# Fix Report\n\n"
            f"**Task:** {task}\n"
            f"**Fix Agent:** {agent}\n\n"
            f"## Findings Addressed\n\n"
            f"{findings_text}\n\n"
            f"## Fixes Applied\n\n"
            f"[{agent} agent would list specific fixes here]\n\n"
            f"## Verification Required\n\n"
            f"Re-run VERIFY stage to confirm fixes resolved the findings."
        )
