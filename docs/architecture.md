# System Architecture

The AI Development Operating System is a layered meta-framework where each layer
builds on the one below it. This document describes the architecture of each component
and how they compose into a complete system.

---

## Full System Architecture

```mermaid
graph TB
    subgraph "AI Development Operating System"
        subgraph "CLI Layer"
            CLI["ai-dev-os CLI\n(Click + Rich)"]
        end

        subgraph "Orchestration Layer (OMC)"
            Catalog["Agent Catalog\n25+ Agents"]
            Router["Model Router\nhaiku/sonnet/opus"]
            State["State Manager\nNotepad + Memory"]
        end

        subgraph "Persistence Layer"
            RalphLoop["Ralph Loop\nIterative Executor"]
            StopHook["Stop Hook\n'boulder never stops'"]
        end

        subgraph "Specification Layer"
            Specum["Specum Pipeline\nREQ → DESIGN → TASKS → IMPL → VERIFY"]
            RALPLAN["RALPLAN\nPlanner + Critic Dialogue"]
        end

        subgraph "Project Management Layer"
            GSD["GSD Lifecycle\n10-Phase Gates"]
            Assumptions["Assumption Tracker"]
            Evidence["Evidence Collector"]
        end

        subgraph "Multi-Agent Execution Layer"
            TeamPipeline["Team Pipeline\nPLAN → PRD → EXEC → VERIFY → FIX"]
        end
    end

    subgraph "Claude API"
        Haiku["claude-haiku-4-5"]
        Sonnet["claude-sonnet-4-6"]
        Opus["claude-opus-4-6"]
    end

    CLI --> Catalog
    CLI --> RalphLoop
    CLI --> Specum
    CLI --> RALPLAN
    CLI --> GSD
    CLI --> TeamPipeline

    Catalog --> Router
    Router --> Haiku & Sonnet & Opus
    RalphLoop --> StopHook

    Specum --> RALPLAN
    Specum --> RalphLoop
    GSD --> Evidence
    GSD --> Assumptions
    TeamPipeline --> RalphLoop

    style CLI fill:#4a4,stroke:#333
    style Catalog fill:#44a,stroke:#333
    style RalphLoop fill:#a44,stroke:#333
    style Specum fill:#a4a,stroke:#333
    style RALPLAN fill:#4aa,stroke:#333
    style GSD fill:#aa4,stroke:#333
    style TeamPipeline fill:#a84,stroke:#333
```

---

## OMC Orchestration Layer

The OMC layer is the kernel of the system — it provides agent definitions,
routing logic, and state management that all other layers depend on.

```mermaid
graph LR
    subgraph "OMC Kernel"
        Catalog["catalog.yaml\n25 Agent Definitions"]
        CatalogPy["AgentCatalog\nload, list, filter"]
        Router["ModelRouter\nroute, estimate_cost"]
        StateManager["StateManager\nNotepad + ProjectMemory"]
    end

    subgraph "Agent Lanes"
        Build["Build Lane\nexplore/analyst/planner\narchitect/executor/verifier"]
        Review["Review Lane\nquality/security/code reviewers"]
        Domain["Domain Lane\ntest/build-fixer/designer\nwriter/qa/scientist/docs"]
        Coord["Coordination Lane\ncritic"]
    end

    Catalog --> CatalogPy
    CatalogPy --> Build & Review & Domain & Coord
    CatalogPy --> Router
    Router --> |"haiku: explore, writer"| Build
    Router --> |"sonnet: executor, reviewers"| Build & Review & Domain
    Router --> |"opus: architect, planner, critic"| Build & Coord
```

**Key design decisions:**

1. **YAML catalog, not code:** Agent definitions live in `catalog.yaml` — readable, editable, and version-controllable without touching Python.

2. **Routing is a table, not an algorithm:** The model routing table is deterministic. `get_agent("architect") → opus`. No heuristics needed.

3. **State is file-based:** `.omc/state/` contains JSON files readable by any tool. No database dependency.

---

## Ralph Loop — Persistence Engine

The Ralph Loop solves the fundamental AI agent problem: sessions end, work doesn't.

```mermaid
stateDiagram-v2
    [*] --> RUNNING: start(goal, tasks)
    RUNNING --> RUNNING: iterate() - tasks remain
    RUNNING --> COMPLETE: all tasks completed
    RUNNING --> FAILED: max_iterations reached
    RUNNING --> CANCELLED: user cancels
    COMPLETE --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

**How persistence works:**

```mermaid
sequenceDiagram
    participant User
    participant RalphLoop
    participant StateFile as .omc/state/ralph-state.json
    participant StopHook as stop_hook.sh

    User->>RalphLoop: start(goal, tasks)
    RalphLoop->>StateFile: write initial state
    loop Each Iteration
        RalphLoop->>RalphLoop: iterate()
        RalphLoop->>StateFile: persist progress
        StopHook->>StateFile: read state
        alt tasks remain
            StopHook-->>RalphLoop: "The boulder never stops"
        else all complete
            StopHook-->>RalphLoop: allow exit
        end
    end
    RalphLoop->>User: complete
```

**The stop hook mechanism:** When Claude Code tries to end a session, the stop hook reads
the Ralph state file. If tasks remain, it outputs "The boulder never stops" — the OMC signal
to continue working. This creates a self-enforcing persistence loop.

---

## Specum — Specification Pipeline

Specum enforces the discipline of specifying before implementing.
Each stage produces a markdown artifact consumed by the next.

```mermaid
graph LR
    Goal["Goal String"]

    subgraph "Stage 1: Requirements"
        Analyst["ProductManagerAgent\n(analyst/opus)"]
        ReqMD["requirements.md\n- User stories\n- Acceptance criteria\n- Constraints\n- Open questions"]
    end

    subgraph "Stage 2: Design"
        Architect["ArchitectAgent\n(architect/opus)"]
        DesignMD["design.md\n- Component diagram\n- Data model\n- API contract\n- Tech decisions"]
    end

    subgraph "Stage 3: Tasks"
        Planner["TaskPlannerAgent\n(planner/opus)"]
        TasksMD["tasks.md\n- Phased task list\n- Dependencies\n- Verification gates"]
    end

    subgraph "Stage 4: Implement"
        Executor["ExecutorAgent\n(executor/sonnet)\n+ RalphLoop"]
        ImplReport["implementation-report.md\n- Task status\n- Evidence\n- Build logs"]
    end

    subgraph "Stage 5: Verify"
        Verifier["VerifierAgent\n(verifier/sonnet)"]
        VerifyReport["verification-report.md\n- PASS/FAIL verdict\n- Criteria checked\n- Gaps found"]
    end

    Goal --> Analyst --> ReqMD
    ReqMD --> Architect --> DesignMD
    DesignMD --> Planner --> TasksMD
    TasksMD --> Executor --> ImplReport
    ImplReport --> Verifier --> VerifyReport
```

**The gate principle:** Each stage can only start when the previous stage's artifact exists.
You cannot design without requirements. You cannot implement without a task list.
Stages cannot be skipped — each one is a checkpoint.

---

## RALPLAN — Adversarial Deliberation

RALPLAN prevents bad plans from reaching execution through adversarial iteration.

```mermaid
sequenceDiagram
    participant User
    participant Planner as PlannerAgent (opus)
    participant Critic as CriticAgent (opus)

    User->>Planner: start(task)

    loop Up to 3 rounds
        Planner->>Planner: create/revise plan
        Planner->>Critic: submit plan for review
        Critic->>Critic: check completeness, feasibility,\nhand-waving, risk coverage
        alt APPROVE
            Critic-->>User: APPROVED plan
            Note over Critic: Zero critical findings
        else REJECT
            Critic-->>Planner: specific critical findings
            Note over Critic: Must resolve before proceeding
        end
    end

    alt --deliberate mode
        Planner->>Planner: pre-mortem analysis
        Planner->>Planner: expand test planning\n(unit + integration + e2e + observability)
    end

    Planner-->>User: final plan (approved or best-effort)
```

**Critic rules:**
- The critic issues APPROVE or REJECT — nothing in between
- REJECT means at least one CRITICAL finding must be resolved
- The critic does NOT suggest improvements — only identifies failures
- Three iterations maximum — prevents infinite deliberation loops

---

## GSD — 10-Phase Project Lifecycle

GSD provides a complete project management framework from idea to production.

```mermaid
graph TB
    subgraph "Phase 1-3: Discovery"
        P1["1. NEW_PROJECT\nGoal + team defined"]
        P2["2. RESEARCH\nDomain + feasibility"]
        P3["3. ROADMAP\nPhase breakdown + success criteria"]
    end

    subgraph "Phase 4-6: Execution Loop"
        P4["4. PLAN_PHASE\nDetailed implementation plan"]
        P5["5. EXECUTE_PHASE\nRalph Loop implementation"]
        P6["6. VERIFY_PHASE\nEvidence against criteria"]
    end

    subgraph "Phase 7-9: Hardening"
        P7["7. ITERATE\nGap analysis + fixes"]
        P8["8. INTEGRATION\nCross-component E2E testing"]
        P9["9. PRODUCTION_READINESS\nOps: runbooks, monitoring, deployment"]
    end

    P10["10. COMPLETE\nAll phases verified"]

    P1 --> P2 --> P3
    P3 --> P4 --> P5 --> P6
    P6 --> |"PASS"| P7
    P6 --> |"FAIL"| P5
    P7 --> P8 --> P9 --> P10

    style P5 fill:#a44,stroke:#333
    style P6 fill:#44a,stroke:#333
    style P10 fill:#4a4,stroke:#333
```

**Phase gates:** Each phase requires evidence before transition.
The `EvidenceCollector` stores proof (build logs, screenshots, test output).
The `AssumptionTracker` surfaces unvalidated assumptions that could block phases.

**The evidence requirement by phase:**

| Phase | Required Evidence |
|-------|------------------|
| RESEARCH | research_document, feasibility_assessment |
| ROADMAP | roadmap_document, success_criteria |
| PLAN_PHASE | implementation_plan, task_list |
| EXECUTE_PHASE | build_log, implementation_report |
| VERIFY_PHASE | verification_report, acceptance_criteria_results |
| INTEGRATION | integration_test_results, e2e_scenario_results |
| PRODUCTION_READINESS | deployment_guide, runbook, monitoring_setup |

---

## Team Pipeline — Multi-Agent Execution

The Team Pipeline coordinates multiple specialized agents through a bounded, verifiable pipeline.

```mermaid
stateDiagram-v2
    [*] --> team-plan: start(task)

    team-plan --> team-prd: exploration + plan complete
    team-prd --> team-exec: acceptance criteria defined
    team-exec --> team-verify: implementation complete

    team-verify --> complete: PASS (all criteria met)
    team-verify --> team-fix: FAIL (findings remain)

    team-fix --> team-verify: fixes applied

    team-fix --> failed: max_fix_loops exceeded
    complete --> [*]
    failed --> [*]
    cancelled --> [*]
```

**Stage agent assignments:**

| Stage | Primary Agents | Model |
|-------|---------------|-------|
| team-plan | explore + planner | haiku + opus |
| team-prd | analyst | opus |
| team-exec | executor, designer, build-fixer, writer | sonnet (or haiku for writer) |
| team-verify | verifier + security-reviewer | sonnet |
| team-fix | executor, build-fixer, or debugger (by defect type) | sonnet |

**Fix loop bound:** The fix loop is bounded by `max_fix_loops` (default: 3).
Exceeding the bound transitions to FAILED terminal state, preventing infinite cycling.

---

## Context Window Economics

This architecture is designed to minimize context window consumption while maximizing output quality.

```mermaid
graph LR
    subgraph "Without OMC"
        Single["Single Session\n653K tokens/session\nEverything in one context"]
    end

    subgraph "With OMC"
        Explore2["explore agent\n~2K tokens\nJust the relevant files"]
        Plan2["planner agent\n~5K tokens\nGoal + exploration output"]
        Exec2["executor agent\n~8K tokens\nTask + plan + context"]
        Verify2["verifier agent\n~4K tokens\nArtifacts + criteria"]
    end

    Single -.->|"compress to"| Explore2
    Single -.->|"compress to"| Plan2
    Single -.->|"compress to"| Exec2
    Single -.->|"compress to"| Verify2
```

**Real session economics (8,481 sessions, 90 days):**
- Average session: 653K tokens without compression
- With OMC agent isolation: ~20K tokens per specialized agent
- **Compression ratio: 97% reduction in per-agent context**

**Why this works:**
1. Specialized agents only see what they need (explore doesn't need the full codebase history)
2. Artifacts are the interface — not raw conversation context
3. State files persist decisions without re-deriving them in every agent call
4. Model routing means cheap agents handle cheap tasks (haiku for file scans)

---

## Composition Patterns

These components compose naturally into higher-order workflows:

### specum + ralph
```
Specum drives the spec pipeline → IMPLEMENT stage spawns RalphLoop
→ tasks persist across iterations → Specum advances to VERIFY when complete
```

### gsd + team_pipeline
```
GSD provides the project lifecycle → EXECUTE_PHASE spawns TeamPipeline
→ TeamPipeline runs PLAN→EXEC→VERIFY → evidence feeds GSD phase gate
→ GSD advances to VERIFY_PHASE when TeamPipeline completes
```

### ralplan + specum
```
RALPLAN deliberates on the approach → approved plan feeds into Specum
→ Specum starts at DESIGN (plan satisfies REQUIREMENTS gate)
→ Specum runs remaining stages to completion
```

### team_pipeline + ralph
```
Team Ralph mode: TeamPipeline orchestrates stages
→ RalphLoop wraps the entire pipeline for persistence
→ If TeamPipeline is interrupted, RalphLoop resumes from last stage
→ Stop hook prevents exit until pipeline reaches terminal state
```
