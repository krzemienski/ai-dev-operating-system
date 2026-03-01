"""
Agent catalog loader and query interface.

Loads agent definitions from catalog.yaml and provides
typed access to agent metadata for orchestration decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

CATALOG_PATH = Path(__file__).parent / "catalog.yaml"


class AgentDefinition(BaseModel):
    """A single agent definition from the catalog."""

    name: str = Field(description="Unique agent identifier")
    lane: str = Field(description="Organizational lane: build, review, domain, coordination")
    model_tier: str = Field(description="Preferred model tier: haiku, sonnet, opus")
    description: str = Field(description="Brief one-line description")
    capabilities: list[str] = Field(default_factory=list, description="List of capability strings")
    system_prompt: str = Field(description="Full system prompt for this agent")

    @property
    def model_id(self) -> str:
        """Return the full Claude model ID for this agent's tier."""
        tier_map = {
            "haiku": "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4-6",
            "opus": "claude-opus-4-6",
        }
        return tier_map.get(self.model_tier, "claude-sonnet-4-6")

    def to_rich_panel(self) -> Panel:
        """Render this agent as a rich Panel for CLI display."""
        content = Text()
        content.append(f"Lane: ", style="bold cyan")
        content.append(f"{self.lane}\n")
        content.append(f"Model Tier: ", style="bold cyan")
        content.append(f"{self.model_tier} ({self.model_id})\n")
        content.append(f"Description: ", style="bold cyan")
        content.append(f"{self.description}\n\n")
        content.append("Capabilities:\n", style="bold cyan")
        for cap in self.capabilities:
            content.append(f"  • {cap}\n", style="green")
        content.append("\nSystem Prompt (excerpt):\n", style="bold cyan")
        excerpt = self.system_prompt[:500].rstrip() + ("..." if len(self.system_prompt) > 500 else "")
        content.append(excerpt, style="dim")
        return Panel(content, title=f"[bold magenta]{self.name}[/bold magenta]", border_style="magenta")


class CatalogData(BaseModel):
    """Root catalog YAML structure."""

    version: str
    description: str
    agents: list[AgentDefinition]


class AgentCatalog:
    """
    Loads and queries the OMC agent catalog.

    The catalog is stored in catalog.yaml alongside this module.
    All agents have full system prompts, capabilities, and model tier assignments.
    """

    def __init__(self, catalog_path: Optional[Path] = None) -> None:
        """Initialize the catalog from YAML file."""
        self._path = catalog_path or CATALOG_PATH
        self._data = self._load()

    def _load(self) -> CatalogData:
        """Load and parse the catalog YAML file."""
        if not self._path.exists():
            raise FileNotFoundError(f"Catalog not found at {self._path}")
        with open(self._path) as f:
            raw = yaml.safe_load(f)
        return CatalogData(**raw)

    def list_agents(self) -> list[AgentDefinition]:
        """Return all agents in the catalog."""
        return self._data.agents

    def get_agent(self, name: str) -> Optional[AgentDefinition]:
        """Get a specific agent by name. Returns None if not found."""
        for agent in self._data.agents:
            if agent.name == name:
                return agent
        return None

    def get_agents_by_lane(self, lane: str) -> list[AgentDefinition]:
        """Get all agents in a specific lane."""
        return [a for a in self._data.agents if a.lane == lane]

    def get_agents_by_model(self, model_tier: str) -> list[AgentDefinition]:
        """Get all agents at a specific model tier."""
        return [a for a in self._data.agents if a.model_tier == model_tier]

    def lanes(self) -> list[str]:
        """Return all unique lane names."""
        return sorted(set(a.lane for a in self._data.agents))

    def render_table(self) -> Table:
        """Render the full catalog as a rich Table."""
        table = Table(
            title=f"OMC Agent Catalog v{self._data.version}",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Lane", style="yellow")
        table.add_column("Model", style="green")
        table.add_column("Description", style="white")

        current_lane = ""
        for agent in sorted(self._data.agents, key=lambda a: (a.lane, a.name)):
            if agent.lane != current_lane:
                current_lane = agent.lane
                table.add_row("", "", "", "", style="dim")
            table.add_row(
                agent.name,
                agent.lane,
                agent.model_tier,
                agent.description,
            )
        return table

    def render_lane_tree(self) -> None:
        """Render agents organized by lane using rich tree."""
        from rich.tree import Tree

        tree = Tree("[bold magenta]OMC Agent Catalog[/bold magenta]")
        for lane in self.lanes():
            lane_branch = tree.add(f"[bold yellow]{lane.upper()} LANE[/bold yellow]")
            for agent in self.get_agents_by_lane(lane):
                tier_color = {"haiku": "green", "sonnet": "cyan", "opus": "red"}.get(
                    agent.model_tier, "white"
                )
                lane_branch.add(
                    f"[{tier_color}]{agent.name}[/{tier_color}] — {agent.description}"
                )
        console.print(tree)
