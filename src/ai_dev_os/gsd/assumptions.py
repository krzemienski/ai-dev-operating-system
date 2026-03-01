"""
GSD assumption tracking.

Records assumptions made during planning and tracks their validation.
Unvalidated assumptions in early phases that reach later phases are a
primary cause of project failure — this tracker makes them visible.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Assumption(BaseModel):
    """A single recorded assumption with validation tracking."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str = Field(description="The assumption being made")
    source: str = Field(description="Who or what made this assumption")
    phase: str = Field(description="Phase when assumption was recorded")
    validated: bool = Field(default=False)
    validation_result: Optional[str] = None
    validated_at: Optional[datetime] = None
    impact: str = Field(
        default="medium",
        description="Impact if wrong: critical, high, medium, low",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    def validate(self, result: str, is_valid: bool) -> None:
        """
        Record the validation result for this assumption.

        Args:
            result: Description of what was found when validating.
            is_valid: Whether the assumption turned out to be correct.
        """
        self.validated = True
        self.validation_result = f"{'CONFIRMED' if is_valid else 'INVALIDATED'}: {result}"
        self.validated_at = datetime.utcnow()


class AssumptionStore(BaseModel):
    """Persisted store of all assumptions for a project."""

    project_name: str
    assumptions: list[Assumption] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class AssumptionTracker:
    """
    Tracks assumptions made during GSD project phases.

    Assumptions that are never validated represent hidden risks.
    This tracker surfaces unvalidated assumptions at phase gates,
    preventing projects from proceeding with invalid foundations.

    Example:
        tracker = AssumptionTracker("payment-system")
        tracker.record(
            "Stripe API supports idempotency keys",
            source="architect",
            phase="research",
            impact="critical"
        )
        # Later, after validation:
        tracker.validate(assumption_id, "Confirmed in Stripe docs", is_valid=True)
    """

    def __init__(self, project_name: str, state_dir: Optional[Path] = None) -> None:
        """
        Initialize the assumption tracker.

        Args:
            project_name: Name of the GSD project.
            state_dir: Directory for state files. Defaults to .omc/state/.
        """
        self._project_name = project_name
        self._state_dir = state_dir or Path(".omc/state")
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._store: Optional[AssumptionStore] = None

    @property
    def store(self) -> AssumptionStore:
        """Return the assumption store, loading from disk if needed."""
        if self._store is None:
            self._store = self._load()
        return self._store

    def record(
        self,
        assumption: str,
        source: str,
        phase: str,
        impact: str = "medium",
    ) -> Assumption:
        """
        Record a new assumption.

        Args:
            assumption: The assumption being made (as a factual statement).
            source: Who made the assumption (e.g., 'architect', 'planner', 'analyst').
            phase: Which GSD phase this assumption was made in.
            impact: Risk level if the assumption is wrong: critical/high/medium/low.

        Returns:
            The created Assumption.
        """
        entry = Assumption(
            text=assumption,
            source=source,
            phase=phase,
            impact=impact,
        )
        self.store.assumptions.append(entry)
        self._save()
        return entry

    def validate(
        self,
        assumption_id: str,
        result: str,
        is_valid: bool,
    ) -> Optional[Assumption]:
        """
        Record validation result for an assumption.

        Args:
            assumption_id: The ID of the assumption to validate.
            result: Description of what was found during validation.
            is_valid: Whether the assumption was confirmed correct.

        Returns:
            The updated Assumption, or None if not found.
        """
        assumption = self._find(assumption_id)
        if assumption:
            assumption.validate(result, is_valid)
            self._save()
        return assumption

    def list_unvalidated(self) -> list[Assumption]:
        """
        Return all assumptions that have not yet been validated.

        Returns:
            List of unvalidated Assumption objects, sorted by impact.
        """
        impact_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        unvalidated = [a for a in self.store.assumptions if not a.validated]
        return sorted(unvalidated, key=lambda a: impact_order.get(a.impact, 99))

    def list_by_phase(self, phase: str) -> list[Assumption]:
        """
        Return all assumptions recorded in a specific phase.

        Args:
            phase: The phase name to filter by.

        Returns:
            List of Assumption objects from that phase.
        """
        return [a for a in self.store.assumptions if a.phase == phase]

    def list_invalidated(self) -> list[Assumption]:
        """
        Return assumptions that were validated and found to be WRONG.

        These represent the highest risk items — assumptions that were
        made and then proven false. Design decisions based on these
        assumptions need to be revisited.

        Returns:
            List of invalidated Assumption objects.
        """
        return [
            a for a in self.store.assumptions
            if a.validated and a.validation_result and "INVALIDATED" in a.validation_result
        ]

    def critical_unvalidated(self) -> list[Assumption]:
        """
        Return unvalidated assumptions with critical or high impact.

        These should block phase gate transitions until validated.

        Returns:
            List of high-risk unvalidated Assumption objects.
        """
        return [
            a for a in self.list_unvalidated()
            if a.impact in ("critical", "high")
        ]

    def _find(self, assumption_id: str) -> Optional[Assumption]:
        """Find an assumption by ID."""
        for assumption in self.store.assumptions:
            if assumption.id == assumption_id:
                return assumption
        return None

    def _load(self) -> AssumptionStore:
        """Load store from disk or create empty."""
        path = self._store_path()
        if path.exists():
            with open(path) as f:
                raw = json.load(f)
            return AssumptionStore(**raw)
        return AssumptionStore(project_name=self._project_name)

    def _save(self) -> None:
        """Persist store to disk."""
        if self._store:
            self._store.last_updated = datetime.utcnow()
            with open(self._store_path(), "w") as f:
                json.dump(self._store.model_dump(mode="json"), f, indent=2, default=str)

    def _store_path(self) -> Path:
        """Return the path to the assumption store JSON file."""
        return self._state_dir / f"assumptions-{self._project_name}.json"
