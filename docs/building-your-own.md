# Building Your Own AI Development Operating System

This guide shows how to incrementally adopt the patterns from this repo
in your own projects. Each step is independently valuable — you don't need
to implement all five to get significant productivity gains.

---

## Step 1: Agent Specialization

**The insight:** A single "do everything" AI agent is like a developer who switches
context between debugging, architecture, and documentation 20 times a day.
Specialization improves quality dramatically.

**What to do:** Define 3-5 agent types with distinct system prompts.

```python
# agents.py
AGENT_DEFINITIONS = {
    "planner": {
        "model": "claude-opus-4-6",
        "system_prompt": """You are a technical project planner.
        Break goals into ordered, atomic tasks with explicit dependencies.
        Every task must have: description, inputs, outputs, complexity (S/M/L).
        Every phase must have a verification criterion.
        Identify top 3 risks before listing tasks."""
    },
    "executor": {
        "model": "claude-sonnet-4-6",
        "system_prompt": """You are an implementation engineer.
        Execute the assigned task with minimal scope creep.
        Follow existing code patterns. Make one change, verify it, continue.
        Report: what changed, why, and confirm the build passes."""
    },
    "verifier": {
        "model": "claude-sonnet-4-6",
        "system_prompt": """You are an evidence-based verifier.
        Check if claimed work actually exists and meets acceptance criteria.
        Issue PASS or FAIL with specific evidence citations.
        'It should work' is not evidence."""
    },
    "critic": {
        "model": "claude-opus-4-6",
        "system_prompt": """You review plans adversarially.
        Find fatal flaws before implementation begins.
        Issue APPROVE or REJECT with specific findings.
        You do NOT suggest improvements — only identify failures."""
    },
    "writer": {
        "model": "claude-haiku-4-5-20251001",
        "system_prompt": """You write technical documentation.
        Lead with outcomes, show don't tell, structure for scanning.
        Every concept needs a code example."""
    }
}
```

**Why this works:** Specialized prompts produce dramatically better outputs.
The planner doesn't try to write code. The verifier doesn't try to fix things.
The executor doesn't architect. Each does one thing well.

**When to use each agent:**

| Task | Agent | Why |
|------|-------|-----|
| "Figure out what to build" | planner | Needs deep reasoning about sequencing |
| "Write the code" | executor | Needs discipline, not creativity |
| "Is it actually done?" | verifier | Needs skepticism, not helpfulness |
| "Is this plan good?" | critic | Needs adversarial thinking |
| "Write the README" | writer | Needs communication skill, not engineering |

---

## Step 2: Add Persistence

**The insight:** AI sessions end. Work doesn't. Persistence lets you resume
from where you left off without re-explaining context.

**What to do:** Write progress to a JSON file after every task.

```python
# persistence.py
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class Task:
    id: str
    title: str
    status: str = "pending"  # pending, in_progress, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output: Optional[str] = None

@dataclass
class WorkSession:
    goal: str
    iteration: int = 0
    max_iterations: int = 100
    tasks: list[Task] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "running"  # running, complete, failed

    def save(self, path: Path = Path(".work-state.json")) -> None:
        """Write current state to disk."""
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path = Path(".work-state.json")) -> "WorkSession":
        """Load state from disk."""
        data = json.loads(path.read_text())
        data["tasks"] = [Task(**t) for t in data["tasks"]]
        return cls(**data)

    def next_pending(self) -> Optional[Task]:
        """Return the next task that needs to be worked on."""
        return next((t for t in self.tasks if t.status == "pending"), None)

    def is_complete(self) -> bool:
        """All tasks done?"""
        return all(t.status == "completed" for t in self.tasks)
```

**The iteration loop:**

```python
def run_with_persistence(goal: str, max_iterations: int = 100) -> None:
    state_path = Path(".work-state.json")

    # Resume or start fresh
    if state_path.exists():
        session = WorkSession.load(state_path)
        print(f"Resuming: iteration {session.iteration}, "
              f"{sum(1 for t in session.tasks if t.status == 'completed')} tasks done")
    else:
        session = WorkSession(goal=goal, max_iterations=max_iterations)
        # Use planner agent to populate tasks
        session.tasks = plan_tasks(goal)
        session.save(state_path)

    # Iterate until done or max reached
    while not session.is_complete() and session.iteration < session.max_iterations:
        session.iteration += 1
        print(f"[ITERATION {session.iteration}/{session.max_iterations}]")

        task = session.next_pending()
        if task:
            task.status = "in_progress"
            task.started_at = datetime.utcnow().isoformat()
            session.save(state_path)

            # Execute task with executor agent
            result = execute_task(task, session.goal)
            task.status = "completed" if result.success else "failed"
            task.output = result.output
            task.completed_at = datetime.utcnow().isoformat()

        session.save(state_path)

    if session.is_complete():
        print("All tasks complete!")
        session.status = "complete"
        session.save(state_path)
```

**Why this works:** The "boulder never stops" principle. If the AI gets interrupted,
crashes, or hits a context limit, you restart from the last saved state — not from scratch.

---

## Step 3: Add Specification Stages

**The insight:** Implementation without specification is how you build the wrong thing
perfectly. Forcing a specification stage before implementation prevents this.

**What to do:** Add a mandatory requirements → design phase before any implementation.

```python
# pipeline.py
from enum import Enum

class Stage(str, Enum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    TASKS = "tasks"
    IMPLEMENT = "implement"
    VERIFY = "verify"

STAGE_PROGRESSION = {
    Stage.REQUIREMENTS: Stage.DESIGN,
    Stage.DESIGN: Stage.TASKS,
    Stage.TASKS: Stage.IMPLEMENT,
    Stage.IMPLEMENT: Stage.VERIFY,
}

STAGE_AGENTS = {
    Stage.REQUIREMENTS: "analyst",    # opus — deep reasoning about what to build
    Stage.DESIGN: "architect",        # opus — system design decisions
    Stage.TASKS: "planner",           # opus — ordered task breakdown
    Stage.IMPLEMENT: "executor",      # sonnet — focused implementation
    Stage.VERIFY: "verifier",         # sonnet — evidence-based completion check
}

def run_stage(stage: Stage, goal: str, previous_artifact: str | None) -> str:
    """Run a pipeline stage with the appropriate agent."""
    agent = STAGE_AGENTS[stage]

    prompts = {
        Stage.REQUIREMENTS: f"""
        Goal: {goal}

        Produce a requirements.md with:
        1. Acceptance criteria (Given/When/Then, testable)
        2. Explicit scope boundaries (in-scope AND out-of-scope)
        3. Constraints (technical, business, security)
        4. Open questions that must be answered before design
        """,
        Stage.DESIGN: f"""
        Requirements:
        {previous_artifact}

        Produce a design.md with:
        1. Component architecture (Mermaid diagram)
        2. Data model (ER diagram or schema definitions)
        3. API contract (request/response examples)
        4. Technology decisions with rationale
        """,
        # ... etc for other stages
    }

    return call_agent(agent, prompts[stage])
```

**The gate:** Each stage produces a markdown artifact. The next stage
consumes that artifact as input. You literally cannot start implementing
without a design. You literally cannot design without requirements.

**Why this works:** Specifications are cheap. Wrong implementations are expensive.
A 2-hour requirements session prevents a 2-week implementation mistake.

---

## Step 4: Add Model Routing

**The insight:** Using opus for everything is like hiring a staff engineer to
write boilerplate. Using haiku for everything is like asking a junior dev
to make architectural decisions. Match the model to the task complexity.

**What to do:** Add a routing table that maps task types to model tiers.

```python
# routing.py
from enum import Enum

class ModelTier(str, Enum):
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"

MODEL_IDS = {
    ModelTier.HAIKU: "claude-haiku-4-5-20251001",   # Fast, cheap
    ModelTier.SONNET: "claude-sonnet-4-6",            # Best for coding
    ModelTier.OPUS: "claude-opus-4-6",                # Deep reasoning
}

# Cost per million tokens (approximate)
MODEL_COSTS = {
    ModelTier.HAIKU:  {"input": 0.80,  "output": 4.00},
    ModelTier.SONNET: {"input": 3.00,  "output": 15.00},
    ModelTier.OPUS:   {"input": 15.00, "output": 75.00},
}

# Routing table: task type → recommended model tier
ROUTING_TABLE = {
    # Opus: deep reasoning, architecture, planning
    "architect":      ModelTier.OPUS,
    "planner":        ModelTier.OPUS,
    "analyst":        ModelTier.OPUS,
    "critic":         ModelTier.OPUS,
    "deep-executor":  ModelTier.OPUS,
    "code-reviewer":  ModelTier.OPUS,

    # Sonnet: implementation, debugging, review
    "executor":          ModelTier.SONNET,
    "debugger":          ModelTier.SONNET,
    "verifier":          ModelTier.SONNET,
    "quality-reviewer":  ModelTier.SONNET,
    "security-reviewer": ModelTier.SONNET,
    "test-engineer":     ModelTier.SONNET,

    # Haiku: fast scans, simple writes
    "explore":  ModelTier.HAIKU,
    "writer":   ModelTier.HAIKU,
}

def route(agent_name: str) -> str:
    """Return the model ID for a given agent type."""
    tier = ROUTING_TABLE.get(agent_name, ModelTier.SONNET)
    return MODEL_IDS[tier]

def estimate_cost(agent: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for an agent invocation."""
    tier = ROUTING_TABLE.get(agent, ModelTier.SONNET)
    costs = MODEL_COSTS[tier]
    return (input_tokens / 1e6 * costs["input"]) + (output_tokens / 1e6 * costs["output"])
```

**The economics:** If you run 100 haiku calls instead of 100 opus calls,
you spend 95% less. For tasks like file scanning, documentation generation,
and simple code checks, haiku is nearly as good and 20x cheaper.

**Why this works:** Cost discipline enables scale. When you're not worried
about burning your entire API budget on a single session, you can run
more agents, more iterations, and more verification cycles.

---

## Step 5: Add State Management

**The insight:** Every agent call costs tokens to re-establish context.
Structured state management makes context cheap to transmit and resume.

**What to do:** Add a project memory structure that persists architectural
decisions, conventions, and key facts across sessions.

```python
# state.py
import json
from pathlib import Path
from typing import Any

class ProjectMemory:
    """
    Persistent project memory that survives session boundaries.

    Stores tech stack, conventions, and key decisions so agents
    don't need to rediscover them on every invocation.
    """

    DEFAULT_STRUCTURE = {
        "tech_stack": {},       # Language, framework, key dependencies
        "build": {},            # Build commands, test commands, CI setup
        "conventions": {},      # Naming, file structure, coding standards
        "structure": {},        # Key directories and their purposes
        "notes": [],            # Important one-off notes
        "directives": [],       # Rules that all agents must follow
    }

    def __init__(self, path: Path = Path(".project-memory.json")) -> None:
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return dict(self.DEFAULT_STRUCTURE)

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def update(self, section: str, updates: dict | list) -> None:
        """Merge updates into a memory section."""
        if isinstance(self._data.get(section), dict) and isinstance(updates, dict):
            self._data[section].update(updates)
        elif isinstance(self._data.get(section), list) and isinstance(updates, list):
            self._data[section].extend(u for u in updates if u not in self._data[section])
        self._save()

    def add_directive(self, directive: str) -> None:
        """Add a rule that all agents must follow."""
        if directive not in self._data["directives"]:
            self._data["directives"].append(directive)
        self._save()

    def to_context(self) -> str:
        """Format memory as a context block for agent prompts."""
        return f"""
## Project Context

**Tech Stack:** {self._data.get('tech_stack', {})}
**Build:** {self._data.get('build', {})}
**Conventions:** {self._data.get('conventions', {})}
**Key Notes:** {chr(10).join('- ' + n for n in self._data.get('notes', []))}
**Directives (MUST follow):** {chr(10).join('- ' + d for d in self._data.get('directives', []))}
"""

# Usage:
memory = ProjectMemory()
memory.update("tech_stack", {"language": "Python 3.12", "framework": "FastAPI"})
memory.update("build", {"test_command": "pytest", "lint_command": "ruff check ."})
memory.add_directive("Never use bare except: — always catch specific exceptions")
memory.add_directive("All API endpoints must have authentication")

# In every agent prompt:
prompt = f"""
{memory.to_context()}

Your task: ...
"""
```

**The payoff:** With project memory, every agent starts with the same
understanding of the codebase conventions, tech stack, and key decisions.
You stop re-explaining the same context 20 times per session.

---

## Putting It All Together

After implementing all 5 steps, your workflow becomes:

```
1. PROJECT MEMORY initialized → agents know the conventions
2. REQUIREMENTS stage → analyst produces acceptance criteria
3. DESIGN stage → architect produces component design
4. TASKS stage → planner produces ordered task list
5. IMPLEMENT (ralph loop) → executor persists through iterations
6. VERIFY → verifier checks evidence against criteria
7. If FAIL → executor fixes → re-verify
8. DONE → all criteria met with evidence
```

The key insight: **this isn't about having an AI write more code faster.
It's about having an AI system that produces correct, verifiable outcomes
because every step has explicit inputs, explicit outputs, and explicit verification.**

That's the AI Development Operating System.

---

## Further Reading

- [Agent Catalog](./agent-catalog.md) — all 25 agents with routing guidance
- [Architecture](./architecture.md) — system architecture with Mermaid diagrams
- [GitHub Repository](https://github.com/krzemienski/ai-dev-operating-system) — source code
