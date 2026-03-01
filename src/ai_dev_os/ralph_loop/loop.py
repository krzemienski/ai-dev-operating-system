"""
Ralph Loop — persistent iterative execution engine.

The boulder never stops. Work continues until all tasks are complete
or the maximum iteration count is reached.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text
from rich import box

from ai_dev_os.ralph_loop.state import (
    LoopStatus,
    RalphState,
    RalphTask,
    TaskStatus,
)

console = Console()

DEFAULT_STATE_PATH = Path(".omc/state/ralph-state.json")


class RalphLoop:
    """
    The Ralph Loop execution engine.

    Manages iterative task execution with persistence across iterations.
    Each call to iterate() processes one iteration of the loop, logs
    progress to the console with rich formatting, and persists state.

    The loop enforces completion: it will keep running until all tasks
    are complete or max_iterations is reached.

    Example:
        loop = RalphLoop()
        loop.start("Build the authentication system", max_iterations=50)
        while not loop.state.should_stop():
            loop.iterate()
    """

    def __init__(self, state_path: Optional[Path] = None) -> None:
        """
        Initialize the Ralph Loop.

        Args:
            state_path: Path to the state JSON file. Defaults to .omc/state/ralph-state.json.
        """
        self._state_path = state_path or DEFAULT_STATE_PATH
        self._state: Optional[RalphState] = None

    @property
    def state(self) -> RalphState:
        """Return current state, loading from disk if needed."""
        if self._state is None:
            self._state = self.load_state()
        return self._state

    def start(
        self,
        goal: str,
        tasks: Optional[list[dict]] = None,
        max_iterations: int = 100,
    ) -> RalphState:
        """
        Start a new Ralph Loop session.

        Args:
            goal: High-level goal describing what the loop is working toward.
            tasks: Optional list of initial tasks as dicts with 'id', 'title', 'description'.
            max_iterations: Maximum iterations before forced stop. Default: 100.

        Returns:
            The initialized RalphState.
        """
        ralph_tasks = []
        if tasks:
            for i, task_dict in enumerate(tasks):
                ralph_tasks.append(
                    RalphTask(
                        id=task_dict.get("id", f"task-{i+1}"),
                        title=task_dict.get("title", f"Task {i+1}"),
                        description=task_dict.get("description", ""),
                        phase=task_dict.get("phase"),
                    )
                )

        self._state = RalphState(
            goal=goal,
            max_iterations=max_iterations,
            task_list=ralph_tasks,
            status=LoopStatus.RUNNING,
        )
        self.persist_state()

        console.print(
            Panel(
                f"[bold green]RALPH LOOP STARTED[/bold green]\n\n"
                f"[cyan]Goal:[/cyan] {goal}\n"
                f"[cyan]Max Iterations:[/cyan] {max_iterations}\n"
                f"[cyan]Initial Tasks:[/cyan] {len(ralph_tasks)}\n"
                f"[cyan]State:[/cyan] {self._state_path}",
                title="[bold red]🪨 The Boulder Starts Rolling[/bold red]",
                border_style="red",
            )
        )
        return self._state

    def iterate(
        self,
        task_runner: Optional[Callable[[RalphTask], bool]] = None,
    ) -> bool:
        """
        Execute one iteration of the Ralph Loop.

        Args:
            task_runner: Optional callable that takes a RalphTask and returns
                         True if completed, False if failed. If None, simulates
                         iteration with logging.

        Returns:
            True if the loop should continue, False if it should stop.
        """
        state = self.state
        state.iteration += 1

        summary = state.progress_summary()
        pct = state.completion_percentage()

        # Print iteration header
        console.print(
            Panel(
                f"[bold cyan]RALPH LOOP — ITERATION {state.iteration}/{state.max_iterations}[/bold cyan]\n\n"
                f"[green]Completed:[/green] {summary['completed']}/{summary['total']} ({pct}%)\n"
                f"[yellow]Pending:[/yellow] {summary['pending']}\n"
                f"[blue]In Progress:[/blue] {summary['in_progress']}\n"
                f"[red]Failed:[/red] {summary['failed']}\n"
                f"[dim]Blocked:[/dim] {summary['blocked']}",
                border_style="cyan",
            )
        )

        # Check completion
        if self.check_completion():
            return False

        # Process next pending task
        pending = state.pending_tasks()
        if pending and task_runner:
            next_task = pending[0]
            next_task.mark_started()
            console.print(f"[bold yellow]→ Executing:[/bold yellow] {next_task.title}")

            success = task_runner(next_task)
            if success:
                next_task.mark_completed()
                console.print(f"[bold green]✓ Completed:[/bold green] {next_task.title}")
            else:
                next_task.mark_failed("Task runner returned False")
                console.print(f"[bold red]✗ Failed:[/bold red] {next_task.title}")
        elif pending:
            console.print(
                f"[dim]Iteration {state.iteration}: {len(pending)} tasks pending, "
                f"no task runner provided[/dim]"
            )

        # Check max iterations
        if state.iteration >= state.max_iterations:
            state.status = LoopStatus.FAILED
            state.stop_reason = f"Max iterations ({state.max_iterations}) reached"
            console.print(
                Panel(
                    f"[bold red]MAX ITERATIONS REACHED[/bold red]\n"
                    f"Stopped after {state.max_iterations} iterations.\n"
                    f"Progress: {pct}% complete",
                    border_style="red",
                )
            )
            self.persist_state()
            return False

        self.persist_state()
        return True

    def check_completion(self) -> bool:
        """
        Check if all tasks are complete. Updates state if complete.

        Returns:
            True if loop is done (all tasks complete), False otherwise.
        """
        state = self.state
        if state.is_complete():
            state.status = LoopStatus.COMPLETE
            state.stop_reason = "All tasks completed"
            self.persist_state()
            console.print(
                Panel(
                    f"[bold green]ALL TASKS COMPLETE![/bold green]\n\n"
                    f"Completed in {state.iteration} iterations.\n"
                    f"Total tasks: {len(state.task_list)}\n"
                    f"Duration: {self._duration_str()}",
                    title="[bold green]🎯 Mission Accomplished[/bold green]",
                    border_style="green",
                )
            )
            return True
        return False

    def persist_state(self) -> None:
        """Write current state to disk."""
        if self._state:
            self._state.to_file(self._state_path)

    def load_state(self) -> RalphState:
        """
        Load state from disk, or return a new empty state.

        Returns:
            RalphState from disk, or fresh RalphState if no file exists.
        """
        if self._state_path.exists():
            return RalphState.from_file(self._state_path)
        return RalphState()

    def status_table(self) -> Table:
        """Render current state as a rich Table."""
        state = self.state
        table = Table(
            title=f"Ralph Loop Status — Iteration {state.iteration}/{state.max_iterations}",
            box=box.ROUNDED,
            header_style="bold magenta",
        )
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Task", style="white")
        table.add_column("Phase", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Attempts", justify="right", style="dim")

        status_styles = {
            TaskStatus.PENDING: "[dim]pending[/dim]",
            TaskStatus.IN_PROGRESS: "[bold yellow]in_progress[/bold yellow]",
            TaskStatus.COMPLETED: "[bold green]✓ completed[/bold green]",
            TaskStatus.FAILED: "[bold red]✗ failed[/bold red]",
            TaskStatus.BLOCKED: "[bold orange1]blocked[/bold orange1]",
        }

        for task in state.task_list:
            table.add_row(
                task.id,
                task.title,
                task.phase or "—",
                status_styles.get(task.status, task.status.value),
                str(task.attempts),
            )
        return table

    def add_task(self, task_id: str, title: str, description: str = "", phase: Optional[str] = None) -> RalphTask:
        """
        Add a new task to the loop at runtime.

        Args:
            task_id: Unique identifier for the task.
            title: Short task title.
            description: Full task description.
            phase: Optional phase name.

        Returns:
            The created RalphTask.
        """
        task = RalphTask(id=task_id, title=title, description=description, phase=phase)
        self.state.task_list.append(task)
        self.persist_state()
        return task

    def _duration_str(self) -> str:
        """Format the elapsed duration as a human-readable string."""
        if not self._state:
            return "unknown"
        delta = datetime.utcnow() - self._state.started_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
