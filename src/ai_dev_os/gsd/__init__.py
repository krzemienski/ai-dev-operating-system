"""
GSD (Get Stuff Done) — 10-phase project management lifecycle.

A structured methodology for taking projects from idea to production
with explicit phase gates, assumption tracking, and evidence collection.
"""

from ai_dev_os.gsd.phases import GSDProject, ProjectPhase, PhaseStatus
from ai_dev_os.gsd.assumptions import AssumptionTracker, Assumption
from ai_dev_os.gsd.evidence import EvidenceCollector, Evidence, EvidenceType

__all__ = [
    "GSDProject",
    "ProjectPhase",
    "PhaseStatus",
    "AssumptionTracker",
    "Assumption",
    "EvidenceCollector",
    "Evidence",
    "EvidenceType",
]
