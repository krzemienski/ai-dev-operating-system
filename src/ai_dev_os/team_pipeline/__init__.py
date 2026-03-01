"""
Team Pipeline — staged multi-agent execution engine.

Implements the canonical OMC staged pipeline:
PLAN → PRD → EXEC → VERIFY → FIX (loop)

Each stage uses specialized agents appropriate for the work.
The fix loop is bounded to prevent infinite cycling.
"""

from ai_dev_os.team_pipeline.pipeline import TeamPipeline, PipelineStage, PipelineStatus
from ai_dev_os.team_pipeline.stages import (
    PlanStage,
    PRDStage,
    ExecStage,
    VerifyStage,
    FixStage,
)

__all__ = [
    "TeamPipeline",
    "PipelineStage",
    "PipelineStatus",
    "PlanStage",
    "PRDStage",
    "ExecStage",
    "VerifyStage",
    "FixStage",
]
