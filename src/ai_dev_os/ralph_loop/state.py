"""
Ralph Loop state persistence.

Defines the data model for Ralph Loop execution state,
including task lists, iteration tracking, and completion status.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of an individual task in the Ralph Loop."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class LoopStatus(str, Enum):
    """Overall status of the Ralph Loop execution."""

    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class RalphTask(BaseModel):
    """A single task tracked within the Ralph Loop."""

    id: str = Field(description="Unique task identifier")
    title: str = Field(description="Short task title")
    description: str = Field(default="", description="Full task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    phase: Optional[str] = Field(default=None, description="Phase this task belongs to")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempts: int = Field(default=0, description="Number of execution attempts")
    error: Optional[str] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    def mark_started(self) -> None:
        """Mark this task as in progress."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.attempts += 1

    def mark_completed(self) -> None:
        """Mark this task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        """Mark this task as failed with an error message."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.utcnow()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Return task duration in seconds, or None if not complete."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class RalphState(BaseModel):
    """
    Complete state for a Ralph Loop execution session.

    Persisted to .omc/state/ralph-state.json between iterations.
    """

    iteration: int = Field(default=0, description="Current iteration number")
    max_iterations: int = Field(default=100, description="Maximum iterations before forced stop")
    task_list: list[RalphTask] = Field(default_factory=list, description="All tasks being tracked")
    goal: str = Field(default="", description="High-level goal being pursued")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    status: LoopStatus = Field(default=LoopStatus.RUNNING)
    linked_team: Optional[str] = Field(default=None, description="Linked team name if running with Team mode")
    stop_reason: Optional[str] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    def is_complete(self) -> bool:
        """
        Check if all tasks are complete.

        Returns True when every task has status COMPLETED.
        """
        if not self.task_list:
            return False
        return all(t.status == TaskStatus.COMPLETED for t in self.task_list)

    def should_stop(self) -> bool:
        """Check if the loop should stop (complete OR max iterations reached)."""
        return self.is_complete() or self.iteration >= self.max_iterations

    def progress_summary(self) -> dict[str, int]:
        """
        Return a count of tasks in each status.

        Returns:
            Dict with keys: total, pending, in_progress, completed, failed, blocked.
        """
        counts: dict[str, int] = {
            "total": len(self.task_list),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "blocked": 0,
        }
        for task in self.task_list:
            counts[task.status.value] += 1
        return counts

    def completion_percentage(self) -> float:
        """Return the percentage of tasks completed (0.0 to 100.0)."""
        if not self.task_list:
            return 0.0
        completed = sum(1 for t in self.task_list if t.status == TaskStatus.COMPLETED)
        return round((completed / len(self.task_list)) * 100, 1)

    def pending_tasks(self) -> list[RalphTask]:
        """Return all tasks with PENDING status."""
        return [t for t in self.task_list if t.status == TaskStatus.PENDING]

    def failed_tasks(self) -> list[RalphTask]:
        """Return all tasks with FAILED status."""
        return [t for t in self.task_list if t.status == TaskStatus.FAILED]

    def to_file(self, path: Path) -> None:
        """
        Serialize state to a JSON file.

        Args:
            path: File path to write to (will be created/overwritten).
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated = datetime.utcnow()
        with open(path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2, default=str)

    @classmethod
    def from_file(cls, path: Path) -> "RalphState":
        """
        Load state from a JSON file.

        Args:
            path: File path to read from.

        Returns:
            RalphState loaded from file.

        Raises:
            FileNotFoundError: If the state file doesn't exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Ralph state file not found: {path}")
        with open(path) as f:
            raw = json.load(f)
        return cls(**raw)
