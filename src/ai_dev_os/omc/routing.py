"""
Model routing logic for OMC agent orchestration.

Provides intelligent model selection based on task complexity,
cost estimation, and latency guidance.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ModelTier(str, Enum):
    """Available Claude model tiers."""

    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


@dataclass
class ModelSpec:
    """Specification for a Claude model including cost and latency characteristics."""

    tier: ModelTier
    model_id: str
    cost_per_million_input_tokens: float
    cost_per_million_output_tokens: float
    typical_latency_seconds: float
    context_window_tokens: int
    description: str
    best_for: list[str] = field(default_factory=list)


@dataclass
class RoutingDecision:
    """Result of a routing decision including rationale."""

    recommended_tier: ModelTier
    model_id: str
    rationale: str
    complexity_score: float
    estimated_cost_usd: Optional[float] = None
    estimated_latency_seconds: Optional[float] = None
    alternatives: list[ModelTier] = field(default_factory=list)


# Model registry with cost and performance characteristics
MODEL_REGISTRY: dict[ModelTier, ModelSpec] = {
    ModelTier.HAIKU: ModelSpec(
        tier=ModelTier.HAIKU,
        model_id="claude-haiku-4-5-20251001",
        cost_per_million_input_tokens=0.80,
        cost_per_million_output_tokens=4.00,
        typical_latency_seconds=1.5,
        context_window_tokens=200_000,
        description="Fastest and most cost-effective. Ideal for high-frequency tasks.",
        best_for=[
            "File search and discovery",
            "Simple code generation",
            "Documentation writing",
            "Status summaries",
            "Lightweight scans",
        ],
    ),
    ModelTier.SONNET: ModelSpec(
        tier=ModelTier.SONNET,
        model_id="claude-sonnet-4-6",
        cost_per_million_input_tokens=3.00,
        cost_per_million_output_tokens=15.00,
        typical_latency_seconds=4.0,
        context_window_tokens=200_000,
        description="Best coding model. Primary implementation and review agent.",
        best_for=[
            "Code implementation",
            "Debugging and root-cause analysis",
            "Code review",
            "Security analysis",
            "Test strategy",
            "Multi-file refactoring",
        ],
    ),
    ModelTier.OPUS: ModelSpec(
        tier=ModelTier.OPUS,
        model_id="claude-opus-4-6",
        cost_per_million_input_tokens=15.00,
        cost_per_million_output_tokens=75.00,
        typical_latency_seconds=10.0,
        context_window_tokens=200_000,
        description="Maximum reasoning. For architecture, planning, and complex analysis.",
        best_for=[
            "System architecture design",
            "Complex requirements analysis",
            "Long-horizon planning",
            "Adversarial design critique",
            "Cross-cutting concern analysis",
        ],
    ),
}

# Agent-to-model mapping (canonical routing table)
AGENT_MODEL_MAP: dict[str, ModelTier] = {
    # Build lane
    "explore": ModelTier.HAIKU,
    "analyst": ModelTier.OPUS,
    "planner": ModelTier.OPUS,
    "architect": ModelTier.OPUS,
    "debugger": ModelTier.SONNET,
    "executor": ModelTier.SONNET,
    "deep-executor": ModelTier.OPUS,
    "verifier": ModelTier.SONNET,
    # Review lane
    "quality-reviewer": ModelTier.SONNET,
    "security-reviewer": ModelTier.SONNET,
    "code-reviewer": ModelTier.OPUS,
    # Domain lane
    "test-engineer": ModelTier.SONNET,
    "build-fixer": ModelTier.SONNET,
    "designer": ModelTier.SONNET,
    "writer": ModelTier.HAIKU,
    "qa-tester": ModelTier.SONNET,
    "scientist": ModelTier.SONNET,
    "document-specialist": ModelTier.SONNET,
    # Coordination lane
    "critic": ModelTier.OPUS,
}

# Complexity score thresholds
COMPLEXITY_THRESHOLDS = {
    "haiku": (0.0, 0.35),    # Low complexity
    "sonnet": (0.35, 0.70),  # Medium complexity
    "opus": (0.70, 1.0),     # High complexity
}

# Keywords that increase complexity score
COMPLEXITY_SIGNALS = {
    "high": [
        "architecture", "design", "system", "distributed", "scalab",
        "security", "critical", "production", "migrate", "refactor entire",
        "adversarial", "deep analysis", "comprehensive", "cross-cutting",
    ],
    "medium": [
        "implement", "debug", "review", "test", "fix", "build",
        "integrate", "api", "database", "async", "concurrent",
    ],
    "low": [
        "search", "find", "list", "summarize", "document", "format",
        "check", "scan", "quick", "simple", "lookup",
    ],
}


class ModelRouter:
    """
    Routes tasks to appropriate Claude model tiers.

    Uses agent name lookup, keyword analysis, and complexity scoring
    to recommend the optimal model for each task.
    """

    def route(self, agent_name: str) -> ModelTier:
        """
        Route by agent name using the canonical routing table.

        Args:
            agent_name: The OMC agent name (e.g., 'executor', 'architect')

        Returns:
            The recommended ModelTier for this agent.
        """
        return AGENT_MODEL_MAP.get(agent_name, ModelTier.SONNET)

    def estimate_cost(self, model: ModelTier, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate the cost in USD for a model invocation.

        Args:
            model: The model tier to use
            input_tokens: Estimated input token count
            output_tokens: Estimated output token count

        Returns:
            Estimated cost in USD.
        """
        spec = MODEL_REGISTRY[model]
        input_cost = (input_tokens / 1_000_000) * spec.cost_per_million_input_tokens
        output_cost = (output_tokens / 1_000_000) * spec.cost_per_million_output_tokens
        return round(input_cost + output_cost, 6)

    def suggest_model(self, complexity_score: float) -> ModelTier:
        """
        Suggest a model tier based on a complexity score from 0.0 to 1.0.

        Args:
            complexity_score: Float between 0.0 (trivial) and 1.0 (maximum complexity)

        Returns:
            Recommended ModelTier.
        """
        if complexity_score < COMPLEXITY_THRESHOLDS["haiku"][1]:
            return ModelTier.HAIKU
        elif complexity_score < COMPLEXITY_THRESHOLDS["sonnet"][1]:
            return ModelTier.SONNET
        else:
            return ModelTier.OPUS

    def score_complexity(self, task_description: str) -> float:
        """
        Score the complexity of a task description from 0.0 to 1.0.

        Args:
            task_description: Natural language description of the task

        Returns:
            Complexity score between 0.0 and 1.0.
        """
        description_lower = task_description.lower()
        score = 0.35  # Default to medium

        # High complexity signals
        for signal in COMPLEXITY_SIGNALS["high"]:
            if signal in description_lower:
                score = min(1.0, score + 0.15)

        # Medium complexity signals
        for signal in COMPLEXITY_SIGNALS["medium"]:
            if signal in description_lower:
                score = min(1.0, score + 0.05)

        # Low complexity signals
        for signal in COMPLEXITY_SIGNALS["low"]:
            if signal in description_lower:
                score = max(0.0, score - 0.10)

        return round(score, 2)

    def full_routing_decision(
        self,
        task_description: str,
        agent_name: Optional[str] = None,
        input_tokens: int = 2000,
        output_tokens: int = 1000,
    ) -> RoutingDecision:
        """
        Make a full routing decision with rationale, cost, and latency estimates.

        Args:
            task_description: Natural language description of the task
            agent_name: Optional agent name to use canonical routing
            input_tokens: Estimated input token count for cost calculation
            output_tokens: Estimated output token count for cost calculation

        Returns:
            RoutingDecision with all metadata.
        """
        if agent_name and agent_name in AGENT_MODEL_MAP:
            tier = AGENT_MODEL_MAP[agent_name]
            rationale = f"Canonical routing: {agent_name} → {tier.value}"
        else:
            complexity = self.score_complexity(task_description)
            tier = self.suggest_model(complexity)
            rationale = f"Complexity score {complexity:.2f} → {tier.value}"

        spec = MODEL_REGISTRY[tier]
        cost = self.estimate_cost(tier, input_tokens, output_tokens)

        # Build alternatives list
        alternatives = [t for t in ModelTier if t != tier]

        return RoutingDecision(
            recommended_tier=tier,
            model_id=spec.model_id,
            rationale=rationale,
            complexity_score=self.score_complexity(task_description),
            estimated_cost_usd=cost,
            estimated_latency_seconds=spec.typical_latency_seconds,
            alternatives=alternatives,
        )

    def get_model_spec(self, tier: ModelTier) -> ModelSpec:
        """Get the full specification for a model tier."""
        return MODEL_REGISTRY[tier]

    def cost_comparison(self, input_tokens: int = 10_000, output_tokens: int = 2_000) -> dict[str, float]:
        """
        Compare costs across all model tiers for a given token count.

        Args:
            input_tokens: Token count for input
            output_tokens: Token count for output

        Returns:
            Dict mapping model tier names to costs in USD.
        """
        return {
            tier.value: self.estimate_cost(tier, input_tokens, output_tokens)
            for tier in ModelTier
        }
