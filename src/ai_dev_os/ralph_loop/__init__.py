"""
Ralph Loop — persistent iterative execution engine.

The Ralph Loop enforces completion through iteration.
"The boulder never stops" — work continues until done or max iterations reached.
"""

from ai_dev_os.ralph_loop.loop import RalphLoop
from ai_dev_os.ralph_loop.state import RalphState, RalphTask, TaskStatus, LoopStatus

__all__ = [
    "RalphLoop",
    "RalphState",
    "RalphTask",
    "TaskStatus",
    "LoopStatus",
]
