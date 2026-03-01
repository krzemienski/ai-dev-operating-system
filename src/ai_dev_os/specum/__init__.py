"""
Specum — Specification-driven development pipeline.

A staged pipeline that enforces specification before implementation:
NEW → REQUIREMENTS → DESIGN → TASKS → IMPLEMENT → VERIFY

Each stage produces a markdown artifact consumed by the next stage,
ensuring implementation is always grounded in explicit specifications.
"""

from ai_dev_os.specum.pipeline import SpecumPipeline, PipelineStage, PipelineStatus

__all__ = [
    "SpecumPipeline",
    "PipelineStage",
    "PipelineStatus",
]
