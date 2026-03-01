"""
OMC state management for notepad and project memory.

Provides persistent storage for session notes and project-wide
memory structures, stored as JSON files in .omc/state/.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class NotePriority(str):
    """Priority level for notepad entries."""
    PRIORITY = "priority"
    WORKING = "working"
    MANUAL = "manual"


class NotepadEntry(BaseModel):
    """A single notepad entry with TTL for working entries."""

    content: str
    section: str  # priority, working, or manual
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class NotepadData(BaseModel):
    """Full notepad data structure."""

    priority: list[NotepadEntry] = Field(default_factory=list)
    working: list[NotepadEntry] = Field(default_factory=list)
    manual: list[NotepadEntry] = Field(default_factory=list)

    def prune_expired(self) -> int:
        """Remove expired working entries. Returns count of pruned entries."""
        original = len(self.working)
        self.working = [e for e in self.working if not e.is_expired]
        return original - len(self.working)


class ProjectMemory(BaseModel):
    """Project-wide persistent memory structure."""

    tech_stack: dict[str, Any] = Field(default_factory=dict)
    build: dict[str, Any] = Field(default_factory=dict)
    conventions: dict[str, Any] = Field(default_factory=dict)
    structure: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    directives: list[str] = Field(default_factory=list)
    last_updated: Optional[datetime] = None

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    def merge(self, updates: dict[str, Any]) -> None:
        """Merge updates into the project memory structure."""
        for key, value in updates.items():
            if hasattr(self, key):
                existing = getattr(self, key)
                if isinstance(existing, dict) and isinstance(value, dict):
                    existing.update(value)
                elif isinstance(existing, list) and isinstance(value, list):
                    existing.extend(v for v in value if v not in existing)
                else:
                    setattr(self, key, value)
        self.last_updated = datetime.utcnow()


class StateManager:
    """
    Manages OMC state files for notepad and project memory.

    State is stored in {worktree}/.omc/state/ as JSON files.
    The StateManager handles reading, writing, and merging state
    for both session notepad and persistent project memory.
    """

    DEFAULT_WORKING_TTL_DAYS = 7

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """
        Initialize StateManager.

        Args:
            base_path: Root path for state files. Defaults to .omc/state/ in cwd.
        """
        self._base_path = base_path or Path.cwd() / ".omc" / "state"
        self._base_path.mkdir(parents=True, exist_ok=True)

    @property
    def notepad_path(self) -> Path:
        """Path to the notepad JSON file."""
        return self._base_path / "notepad.json"

    @property
    def project_memory_path(self) -> Path:
        """Path to the project memory JSON file."""
        return self._base_path / "project-memory.json"

    def read_notepad(self, section: Optional[str] = None) -> NotepadData:
        """
        Read the current notepad state.

        Args:
            section: Optional section to filter (priority/working/manual/all).
                     Returns all sections if None.

        Returns:
            NotepadData with current entries.
        """
        if not self.notepad_path.exists():
            return NotepadData()

        with open(self.notepad_path) as f:
            raw = json.load(f)

        data = NotepadData(**raw)
        data.prune_expired()

        if section and section != "all":
            filtered = NotepadData()
            setattr(filtered, section, getattr(data, section, []))
            return filtered

        return data

    def write_notepad(
        self,
        content: str,
        section: str,
        ttl_days: Optional[int] = None,
    ) -> NotepadEntry:
        """
        Write a new entry to the notepad.

        Args:
            content: The note content to store.
            section: Which section: priority, working, or manual.
            ttl_days: Days until expiry for working entries. Defaults to 7.

        Returns:
            The created NotepadEntry.
        """
        data = self.read_notepad()

        expires_at = None
        if section == "working":
            days = ttl_days or self.DEFAULT_WORKING_TTL_DAYS
            expires_at = datetime.utcnow() + timedelta(days=days)

        entry = NotepadEntry(
            content=content,
            section=section,
            expires_at=expires_at,
        )

        section_list = getattr(data, section, None)
        if section_list is not None:
            section_list.append(entry)

        self._write_notepad_data(data)
        return entry

    def _write_notepad_data(self, data: NotepadData) -> None:
        """Serialize and write notepad data to disk."""
        with open(self.notepad_path, "w") as f:
            json.dump(data.model_dump(mode="json"), f, indent=2, default=str)

    def read_project_memory(self, section: Optional[str] = None) -> ProjectMemory:
        """
        Read the project memory.

        Args:
            section: Optional section to retrieve (tech_stack/build/conventions/etc.)

        Returns:
            Full ProjectMemory object (section filtering done by caller).
        """
        if not self.project_memory_path.exists():
            return ProjectMemory()

        with open(self.project_memory_path) as f:
            raw = json.load(f)

        return ProjectMemory(**raw)

    def write_project_memory(self, memory: ProjectMemory) -> None:
        """
        Write project memory to disk (full overwrite).

        Args:
            memory: The ProjectMemory object to persist.
        """
        memory.last_updated = datetime.utcnow()
        with open(self.project_memory_path, "w") as f:
            json.dump(memory.model_dump(mode="json"), f, indent=2, default=str)

    def merge_project_memory(self, updates: dict[str, Any]) -> ProjectMemory:
        """
        Merge updates into the existing project memory.

        Args:
            updates: Dict with keys matching ProjectMemory fields.

        Returns:
            Updated ProjectMemory after merge.
        """
        memory = self.read_project_memory()
        memory.merge(updates)
        self.write_project_memory(memory)
        return memory

    def add_note(self, note: str) -> ProjectMemory:
        """Add a note to project memory notes list."""
        return self.merge_project_memory({"notes": [note]})

    def add_directive(self, directive: str) -> ProjectMemory:
        """Add a directive to project memory directives list."""
        return self.merge_project_memory({"directives": [directive]})

    def clear_state(self, state_file: str) -> None:
        """
        Clear a specific state file.

        Args:
            state_file: Which state to clear: 'notepad' or 'project-memory'.
        """
        path_map = {
            "notepad": self.notepad_path,
            "project-memory": self.project_memory_path,
        }
        path = path_map.get(state_file)
        if path and path.exists():
            path.unlink()
