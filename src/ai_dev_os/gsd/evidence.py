"""
GSD evidence collection.

Collects and verifies evidence for each GSD phase transition.
Evidence gates prevent phases from being "claimed" without proof.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """Types of evidence that can be collected."""

    BUILD_LOG = "build_log"
    SCREENSHOT = "screenshot"
    API_RESPONSE = "api_response"
    TEST_OUTPUT = "test_output"
    MANUAL_VERIFICATION = "manual_verification"
    DOCUMENT = "document"
    METRIC = "metric"
    LOG_OUTPUT = "log_output"
    BENCHMARK_RESULT = "benchmark_result"


class Evidence(BaseModel):
    """A single piece of evidence for a phase transition."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    phase: str = Field(description="Phase this evidence belongs to")
    evidence_type: EvidenceType
    title: str = Field(description="Brief title describing what this evidence shows")
    data: Any = Field(description="The evidence content (text, path, dict, etc.)")
    file_path: Optional[str] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    verified: bool = Field(default=False)
    notes: Optional[str] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class EvidenceStore(BaseModel):
    """Persisted store of all evidence for a project."""

    project_name: str
    evidence_items: list[Evidence] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class EvidenceCollector:
    """
    Collects and manages evidence for GSD phase transitions.

    Evidence is the mechanism that makes GSD's phase gates enforceable.
    Without concrete evidence, a phase cannot be marked complete.

    Evidence is stored in .omc/evidence/ and referenced by ID in phase records.

    Example:
        collector = EvidenceCollector("payment-system")

        # Collect build output as evidence
        evidence = collector.collect(
            phase="execute_phase",
            evidence_type=EvidenceType.BUILD_LOG,
            title="iOS build succeeded",
            data="BUILD SUCCEEDED (0 warnings, 0 errors)"
        )

        # Later, verify the phase is evidenced
        if collector.verify_phase_complete("execute_phase"):
            project.advance_phase(evidence_ids=[evidence.id])
    """

    def __init__(self, project_name: str, evidence_dir: Optional[Path] = None) -> None:
        """
        Initialize the evidence collector.

        Args:
            project_name: Name of the GSD project.
            evidence_dir: Directory to store evidence files. Defaults to .omc/evidence/.
        """
        self._project_name = project_name
        self._evidence_dir = evidence_dir or Path(".omc/evidence") / project_name
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        self._store: Optional[EvidenceStore] = None

    @property
    def store(self) -> EvidenceStore:
        """Return the evidence store, loading from disk if needed."""
        if self._store is None:
            self._store = self._load()
        return self._store

    def collect(
        self,
        phase: str,
        evidence_type: EvidenceType,
        title: str,
        data: Any,
        notes: Optional[str] = None,
    ) -> Evidence:
        """
        Collect a new piece of evidence.

        Args:
            phase: The GSD phase this evidence belongs to.
            evidence_type: Type of evidence being collected.
            title: Brief description of what this evidence shows.
            data: The evidence content (log output, API response, etc.)
            notes: Optional notes about the evidence.

        Returns:
            The created Evidence object.
        """
        evidence = Evidence(
            phase=phase,
            evidence_type=evidence_type,
            title=title,
            data=data,
            notes=notes,
        )

        # If data is a string and long, write to file
        if isinstance(data, str) and len(data) > 500:
            file_path = self._evidence_dir / f"{evidence.id}-{evidence_type.value}.txt"
            file_path.write_text(data, encoding="utf-8")
            evidence.file_path = str(file_path)

        self.store.evidence_items.append(evidence)
        self._save()
        return evidence

    def verify_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """
        Mark an evidence item as manually verified.

        Args:
            evidence_id: The ID of the evidence to verify.

        Returns:
            The updated Evidence, or None if not found.
        """
        evidence = self._find(evidence_id)
        if evidence:
            evidence.verified = True
            self._save()
        return evidence

    def list_by_phase(self, phase: str) -> list[Evidence]:
        """
        Return all evidence collected for a specific phase.

        Args:
            phase: The phase name to filter by.

        Returns:
            List of Evidence objects for that phase.
        """
        return [e for e in self.store.evidence_items if e.phase == phase]

    def verify_phase_complete(self, phase: str) -> bool:
        """
        Check if a phase has sufficient evidence to be considered complete.

        A phase is considered evidenced if it has at least one piece of
        evidence collected. For stricter verification, check that the
        required evidence types are all present.

        Args:
            phase: The phase name to verify.

        Returns:
            True if the phase has collected evidence, False otherwise.
        """
        phase_evidence = self.list_by_phase(phase)
        return len(phase_evidence) > 0

    def phase_evidence_summary(self) -> dict[str, int]:
        """
        Return a count of evidence items per phase.

        Returns:
            Dict mapping phase names to evidence counts.
        """
        summary: dict[str, int] = {}
        for evidence in self.store.evidence_items:
            summary[evidence.phase] = summary.get(evidence.phase, 0) + 1
        return summary

    def export_phase_evidence(self, phase: str) -> dict[str, Any]:
        """
        Export all evidence for a phase as a structured dict.

        Args:
            phase: The phase to export evidence for.

        Returns:
            Dict with evidence items and metadata.
        """
        items = self.list_by_phase(phase)
        return {
            "phase": phase,
            "project": self._project_name,
            "evidence_count": len(items),
            "evidence": [
                {
                    "id": e.id,
                    "type": e.evidence_type.value,
                    "title": e.title,
                    "collected_at": e.collected_at.isoformat(),
                    "verified": e.verified,
                    "file_path": e.file_path,
                    "notes": e.notes,
                }
                for e in items
            ],
        }

    def _find(self, evidence_id: str) -> Optional[Evidence]:
        """Find evidence by ID."""
        for evidence in self.store.evidence_items:
            if evidence.id == evidence_id:
                return evidence
        return None

    def _load(self) -> EvidenceStore:
        """Load store from disk or create empty."""
        path = self._store_path()
        if path.exists():
            with open(path) as f:
                raw = json.load(f)
            return EvidenceStore(**raw)
        return EvidenceStore(project_name=self._project_name)

    def _save(self) -> None:
        """Persist store to disk."""
        if self._store:
            self._store.last_updated = datetime.utcnow()
            with open(self._store_path(), "w") as f:
                json.dump(self._store.model_dump(mode="json"), f, indent=2, default=str)

    def _store_path(self) -> Path:
        """Return the path to the evidence store JSON file."""
        return self._evidence_dir / "evidence-store.json"
