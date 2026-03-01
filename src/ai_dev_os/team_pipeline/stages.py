"""
Team Pipeline stage definitions.

Each stage specifies the agents required, artifacts produced,
and the logic for executing that stage of the pipeline.

Stage execution invokes the Claude CLI via subprocess, passing
structured prompts to specialized agent roles. If the Claude CLI
is not available, stages fall back to template output with clear
markers indicating where agent output would appear.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from rich.console import Console

console = Console(stderr=True)


def _claude_available() -> bool:
    """Check if the Claude CLI is available on PATH."""
    return shutil.which("claude") is not None


def _invoke_claude(prompt: str, model: str = "sonnet", system: str = "") -> str:
    """
    Invoke the Claude CLI with a prompt and return the response.

    Uses `claude -p` for non-interactive single-prompt mode.
    Strips CLAUDECODE env vars to avoid nesting detection when
    running inside an active Claude Code session.

    Args:
        prompt: The user prompt to send.
        model: Model tier — "haiku", "sonnet", or "opus".
        system: Optional system prompt for role specialization.

    Returns:
        The model's text response, or a fallback message on failure.
    """
    import os

    # Build sanitized environment (strip nesting-detection vars)
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("CLAUDE_CODE_") and k != "CLAUDECODE"
    }

    cmd = ["claude", "-p", prompt, "--model", model]
    if system:
        cmd.extend(["--system-prompt", system])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            error_detail = result.stderr.strip() or "No output produced"
            return f"[Claude CLI returned non-zero or empty output: {error_detail}]"
    except subprocess.TimeoutExpired:
        return "[Claude CLI timed out after 300s]"
    except FileNotFoundError:
        return "[Claude CLI not found on PATH — install with: npm install -g @anthropic-ai/claude-code]"
    except Exception as e:
        return f"[Claude CLI invocation failed: {e}]"


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
        cwd = context.get("working_directory", ".")

        console.print(f"[dim]PLAN: Running exploration for:[/dim] {task}")
        exploration = self._run_exploration(task, context)
        result.add_artifact(
            "exploration-report.md",
            exploration,
            produced_by="explore (haiku)",
        )

        console.print("[dim]PLAN: Running task planning...[/dim]")
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
        system = (
            "You are an expert codebase explorer. Your job is to quickly scan "
            "a codebase and produce a structured exploration report identifying: "
            "project structure, entry points, relevant modules, dependency graph, "
            "and integration points. Be concise and specific — list actual file "
            "paths, not abstract descriptions."
        )
        prompt = (
            f"Explore the codebase and produce an exploration report for this task:\n\n"
            f"**Task:** {task}\n\n"
            f"List:\n"
            f"1. Project structure (key directories and their purpose)\n"
            f"2. Entry points (main files, CLI commands, API routes)\n"
            f"3. Modules relevant to the task\n"
            f"4. Dependencies (external packages used)\n"
            f"5. Integration points (APIs, databases, external services)\n\n"
            f"Format as a markdown report with ## headings."
        )
        return _invoke_claude(prompt, model="haiku", system=system)

    def _run_planning(self, task: str, exploration: str) -> str:
        """Run the planner agent to create an implementation plan."""
        system = (
            "You are a senior technical planner. Given a task and codebase "
            "exploration report, produce a phased implementation plan with "
            "numbered tasks, complexity estimates (S/M/L/XL), dependencies, "
            "and risk assessment. Be specific — reference actual files and "
            "modules from the exploration report."
        )
        prompt = (
            f"Create an implementation plan for this task:\n\n"
            f"**Task:** {task}\n\n"
            f"## Codebase Context\n\n{exploration}\n\n"
            f"Produce:\n"
            f"1. Phased task breakdown (Phase 1: Foundation, Phase 2: Core, etc.)\n"
            f"2. Each task: ID, description, complexity (S/M/L/XL), dependencies\n"
            f"3. Risk assessment with mitigation strategies\n"
            f"4. Verification criteria for each phase\n\n"
            f"Format as a markdown plan."
        )
        return _invoke_claude(prompt, model="opus", system=system)


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

        console.print("[dim]PRD: Generating requirements and acceptance criteria...[/dim]")
        prd = self._run_analyst(task, plan)
        result.add_artifact("prd.md", prd, produced_by="analyst (opus)")

        result.completed_at = datetime.utcnow()
        return result

    def _run_analyst(self, task: str, plan: str) -> str:
        """Run the analyst agent to create a PRD."""
        system = (
            "You are a senior product analyst. Given a task and implementation "
            "plan, produce a Product Requirements Document with: specific goal, "
            "acceptance criteria in Given/When/Then format, constraints, scope "
            "boundaries, and non-functional requirements. Challenge assumptions "
            "and identify missing requirements."
        )
        prompt = (
            f"Write a PRD for this task:\n\n"
            f"**Task:** {task}\n\n"
            f"## Implementation Plan\n\n{plan}\n\n"
            f"Produce:\n"
            f"1. Goal — one sentence, specific\n"
            f"2. Acceptance criteria — Given/When/Then format, numbered\n"
            f"3. Constraints — technical and business\n"
            f"4. Out of scope — explicit boundaries\n"
            f"5. Non-functional requirements — performance, security, etc.\n\n"
            f"Format as a markdown PRD."
        )
        return _invoke_claude(prompt, model="opus", system=system)


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

        console.print(f"[dim]EXEC: Dispatching to {specialist}...[/dim]")
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
        prd = next(
            (a.content for a in context.get("prd_artifacts", []) if "prd" in a.name),
            "",
        )
        model = "opus" if specialist == "deep-executor" else ("haiku" if specialist == "writer" else "sonnet")
        system = (
            f"You are a {specialist} agent. Implement the given task according to "
            f"the requirements. Report exactly what you changed: files modified, "
            f"functions added/changed, build status, and any issues encountered. "
            f"Be specific with file paths and line numbers."
        )
        prompt = (
            f"Implement this task:\n\n"
            f"**Task:** {task}\n\n"
            f"## Requirements\n\n{prd}\n\n"
            f"Produce an implementation report with:\n"
            f"1. Changes made (files, functions, line counts)\n"
            f"2. Build status (PASS/FAIL)\n"
            f"3. Evidence (test output, screenshots described, API responses)\n"
            f"4. Any follow-up items or concerns"
        )
        return _invoke_claude(prompt, model=model, system=system)


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
        console.print("[dim]VERIFY: Running verification...[/dim]")
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
        impl_report = next(
            (a.content for a in context.get("exec_artifacts", []) if "implementation" in a.name),
            "",
        )
        prd = next(
            (a.content for a in context.get("prd_artifacts", []) if "prd" in a.name),
            "",
        )
        system = (
            "You are a verification agent. Your job is to check whether "
            "the implementation satisfies the acceptance criteria. For each "
            "criterion, state PASS or FAIL with specific evidence. End with "
            "a verdict line: [VERDICT: PASS] or [VERDICT: FAIL]. "
            "Be ruthlessly honest — do not pass work that has gaps."
        )
        prompt = (
            f"Verify completion of this task:\n\n"
            f"**Task:** {task}\n\n"
            f"## Acceptance Criteria\n\n{prd}\n\n"
            f"## Implementation Report\n\n{impl_report}\n\n"
            f"For each acceptance criterion:\n"
            f"1. State the criterion\n"
            f"2. State PASS or FAIL\n"
            f"3. Cite specific evidence (file paths, build output, test results)\n\n"
            f"End with: [VERDICT: PASS] or [VERDICT: FAIL]"
        )
        return _invoke_claude(prompt, model="sonnet", system=system)

    def _extract_findings(self, report: str) -> list[str]:
        """Extract specific findings (FAIL items) from verification report."""
        findings = []
        for line in report.split("\n"):
            line_stripped = line.strip()
            if "FAIL" in line_stripped and "VERDICT" not in line_stripped:
                findings.append(line_stripped)
        return findings


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

        console.print(f"[dim]FIX: Dispatching to {fix_agent}...[/dim]")
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
        """Run the fix agent to resolve verification findings."""
        findings_text = "\n".join(f"- {f}" for f in findings) if findings else "- No specific findings"
        system = (
            f"You are a {agent} agent. You are fixing specific defects found "
            f"during verification. For each finding, describe the root cause, "
            f"the fix applied, and evidence that the fix works. Be precise "
            f"with file paths and changes."
        )
        prompt = (
            f"Fix these verification failures:\n\n"
            f"**Task:** {task}\n\n"
            f"## Findings to Fix\n\n{findings_text}\n\n"
            f"For each finding:\n"
            f"1. Root cause analysis\n"
            f"2. Fix description (files changed, lines modified)\n"
            f"3. Verification that the fix works\n\n"
            f"End with: Re-run VERIFY stage to confirm all findings resolved."
        )
        return _invoke_claude(prompt, model="sonnet", system=system)
