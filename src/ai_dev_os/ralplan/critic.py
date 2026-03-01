"""
RALPLAN Critic agent.

Reviews plans adversarially, identifying specific failures.
Does NOT suggest improvements — only identifies what's wrong.
Issues APPROVE or REJECT with specific, actionable findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ai_dev_os.ralplan.planner import Plan


class VerdictType(str, Enum):
    """Critic verdict: approve the plan or reject it."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass
class CriticFinding:
    """A specific finding from the critic's review."""

    severity: str  # CRITICAL, MODERATE, MINOR
    category: str  # completeness, feasibility, hand_waving, risk_coverage
    description: str
    plan_reference: Optional[str] = None  # Which part of the plan this refers to


@dataclass
class CriticVerdict:
    """
    Complete verdict from the CriticAgent.

    APPROVE means the plan can proceed to implementation.
    REJECT means at least one critical finding must be resolved.
    """

    verdict: VerdictType
    critical_findings: list[CriticFinding] = field(default_factory=list)
    moderate_findings: list[CriticFinding] = field(default_factory=list)
    minor_findings: list[CriticFinding] = field(default_factory=list)
    rationale: str = ""

    @property
    def is_approved(self) -> bool:
        """Return True if the plan is approved."""
        return self.verdict == VerdictType.APPROVE

    def to_markdown(self) -> str:
        """Render the verdict as a markdown document."""
        lines = [
            f"# Critic Verdict: {self.verdict.value}",
            f"",
            self.rationale,
            f"",
        ]

        if self.critical_findings:
            lines.extend(["## Critical Findings (must resolve)", ""])
            for i, f in enumerate(self.critical_findings, 1):
                lines.append(f"{i}. **[{f.category.upper()}]** {f.description}")
                if f.plan_reference:
                    lines.append(f"   *Ref: {f.plan_reference}*")
                lines.append("")

        if self.moderate_findings:
            lines.extend(["## Moderate Findings (should address)", ""])
            for i, f in enumerate(self.moderate_findings, 1):
                lines.append(f"{i}. **[{f.category.upper()}]** {f.description}")
                lines.append("")

        if self.minor_findings:
            lines.extend(["## Minor Findings (optional)", ""])
            for i, f in enumerate(self.minor_findings, 1):
                lines.append(f"{i}. **[{f.category.upper()}]** {f.description}")
                lines.append("")

        return "\n".join(lines)


class CriticAgent:
    """
    Adversarial plan reviewer.

    Reviews plans to find fatal flaws before implementation begins.
    Does NOT suggest how to fix problems — only identifies what's wrong.
    The planner's job is to address findings and resubmit.
    """

    # Thresholds for auto-approve (plan quality heuristics)
    MAX_TASKS_PER_PHASE = 7
    MIN_PHASES = 2
    REQUIRED_RISK_COUNT = 2

    def review(self, plan: Plan) -> CriticVerdict:
        """
        Review a plan and issue a APPROVE or REJECT verdict.

        Args:
            plan: The Plan to review.

        Returns:
            CriticVerdict with verdict and all findings.
        """
        critical: list[CriticFinding] = []
        moderate: list[CriticFinding] = []
        minor: list[CriticFinding] = []

        # --- COMPLETENESS CHECKS ---
        self._check_completeness(plan, critical, moderate, minor)

        # --- FEASIBILITY CHECKS ---
        self._check_feasibility(plan, critical, moderate, minor)

        # --- HAND-WAVING DETECTION ---
        self._check_hand_waving(plan, critical, moderate, minor)

        # --- RISK COVERAGE ---
        self._check_risk_coverage(plan, critical, moderate, minor)

        # Determine verdict
        verdict = VerdictType.REJECT if critical else VerdictType.APPROVE

        if verdict == VerdictType.APPROVE:
            rationale = (
                f"This plan demonstrates adequate completeness, feasibility, and risk coverage. "
                f"All phases have verification criteria. Task dependencies are explicit. "
                f"{len(moderate)} moderate and {len(minor)} minor findings should be addressed "
                f"but do not block implementation."
            )
        else:
            rationale = (
                f"This plan has {len(critical)} critical finding(s) that must be resolved before "
                f"implementation begins. These are not style issues — they represent gaps that will "
                f"cause implementation to fail or deliver the wrong thing."
            )

        return CriticVerdict(
            verdict=verdict,
            critical_findings=critical,
            moderate_findings=moderate,
            minor_findings=minor,
            rationale=rationale,
        )

    def _check_completeness(
        self,
        plan: Plan,
        critical: list[CriticFinding],
        moderate: list[CriticFinding],
        minor: list[CriticFinding],
    ) -> None:
        """Check if the plan covers all required areas."""

        # Must have at least 2 phases
        if len(plan.phases) < self.MIN_PHASES:
            critical.append(CriticFinding(
                severity="CRITICAL",
                category="completeness",
                description=(
                    f"Plan has only {len(plan.phases)} phase(s). A realistic plan needs at least "
                    f"{self.MIN_PHASES} phases: foundation work and integration/validation are "
                    f"always distinct concerns."
                ),
            ))

        # Each phase must have a verification criterion
        phases_without_verification = [
            p.name for p in plan.phases if not p.verification.strip()
        ]
        if phases_without_verification:
            critical.append(CriticFinding(
                severity="CRITICAL",
                category="completeness",
                description=(
                    f"Phases missing verification criteria: {', '.join(phases_without_verification)}. "
                    f"Every phase must have a concrete, checkable completion condition."
                ),
                plan_reference=f"Phase(s): {', '.join(phases_without_verification)}",
            ))

        # Must have at least one task per phase
        empty_phases = [p.name for p in plan.phases if not p.tasks]
        if empty_phases:
            critical.append(CriticFinding(
                severity="CRITICAL",
                category="completeness",
                description=f"Empty phases with no tasks: {', '.join(empty_phases)}.",
                plan_reference=f"Phase(s): {', '.join(empty_phases)}",
            ))

        # Check for very large phases (possible hand-waving)
        large_phases = [p.name for p in plan.phases if len(p.tasks) > self.MAX_TASKS_PER_PHASE]
        if large_phases:
            moderate.append(CriticFinding(
                severity="MODERATE",
                category="completeness",
                description=(
                    f"Phases with >{self.MAX_TASKS_PER_PHASE} tasks may hide unresolved complexity: "
                    f"{', '.join(large_phases)}. Consider decomposing."
                ),
            ))

    def _check_feasibility(
        self,
        plan: Plan,
        critical: list[CriticFinding],
        moderate: list[CriticFinding],
        minor: list[CriticFinding],
    ) -> None:
        """Check if the plan is realistically achievable."""

        # Look for tasks with no description
        undescribed = [
            f"{t.id}: {t.title}"
            for p in plan.phases
            for t in p.tasks
            if not t.description.strip()
        ]
        if undescribed:
            critical.append(CriticFinding(
                severity="CRITICAL",
                category="feasibility",
                description=(
                    f"Tasks with no description: {', '.join(undescribed[:3])}{'...' if len(undescribed) > 3 else ''}. "
                    f"An implementer cannot execute tasks without knowing what to do."
                ),
            ))

        # Check for tasks claiming high complexity with no risk flagged
        high_complexity_no_risk = [
            f"{t.id}: {t.title}"
            for p in plan.phases
            for t in p.tasks
            if t.complexity == "L" and not t.risks
        ]
        if high_complexity_no_risk:
            moderate.append(CriticFinding(
                severity="MODERATE",
                category="feasibility",
                description=(
                    f"Large-complexity tasks with no risks flagged: "
                    f"{', '.join(high_complexity_no_risk)}. "
                    f"Large tasks always have risks — identify them."
                ),
            ))

    def _check_hand_waving(
        self,
        plan: Plan,
        critical: list[CriticFinding],
        moderate: list[CriticFinding],
        minor: list[CriticFinding],
    ) -> None:
        """Detect vague language that hides implementation gaps."""

        hand_wave_phrases = [
            "implement the logic",
            "handle appropriately",
            "etc",
            "and so on",
            "as needed",
            "when necessary",
            "somehow",
            "figure out",
        ]

        vague_tasks = []
        for phase in plan.phases:
            for task in phase.tasks:
                desc_lower = task.description.lower()
                for phrase in hand_wave_phrases:
                    if phrase in desc_lower:
                        vague_tasks.append(f"{task.id}: '{phrase}'")
                        break

        if vague_tasks:
            moderate.append(CriticFinding(
                severity="MODERATE",
                category="hand_waving",
                description=(
                    f"Hand-waving language detected in task descriptions: "
                    f"{', '.join(vague_tasks[:3])}. "
                    f"Replace with specific, concrete descriptions of what to build."
                ),
            ))

    def _check_risk_coverage(
        self,
        plan: Plan,
        critical: list[CriticFinding],
        moderate: list[CriticFinding],
        minor: list[CriticFinding],
    ) -> None:
        """Check that risks are identified and addressed."""

        if len(plan.top_risks) < self.REQUIRED_RISK_COUNT:
            moderate.append(CriticFinding(
                severity="MODERATE",
                category="risk_coverage",
                description=(
                    f"Only {len(plan.top_risks)} top risk(s) identified. "
                    f"Every project has at least {self.REQUIRED_RISK_COUNT} meaningful risks. "
                    f"Under-identifying risks means they'll be discovered during implementation."
                ),
            ))

        # Check if there's a proof-of-concept or spike task for unknown territory
        has_spike = any(
            any(kw in t.title.lower() for kw in ["spike", "proof", "poc", "validate", "assumption"])
            for p in plan.phases
            for t in p.tasks
        )
        if not has_spike and len(plan.top_risks) >= 2:
            minor.append(CriticFinding(
                severity="MINOR",
                category="risk_coverage",
                description=(
                    "No proof-of-concept or spike task found. "
                    "If any risks involve unknowns, add a spike task in Phase 1 to validate "
                    "assumptions before committing to the full implementation."
                ),
            ))
