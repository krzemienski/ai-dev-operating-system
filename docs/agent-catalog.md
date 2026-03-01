# OMC Agent Catalog Reference

Complete reference for all 25 agents in the OMC (Oh My Claude Code) orchestration layer.

---

## Quick Reference Table

| Name | Lane | Model | When to Use |
|------|------|-------|-------------|
| explore | build | haiku | Finding files, mapping symbols, tracing imports |
| analyst | build | opus | Unclear requirements, hidden constraints, acceptance criteria |
| planner | build | opus | Complex multi-step features, risk-heavy work |
| architect | build | opus | System design, API contracts, architectural decisions |
| debugger | build | sonnet | Root cause analysis, regression isolation |
| executor | build | sonnet | Standard implementation, refactoring, feature work |
| deep-executor | build | opus | Complex autonomous tasks spanning many files |
| verifier | build | sonnet | Confirming work is actually done with evidence |
| quality-reviewer | review | sonnet | Logic bugs, SOLID violations, performance hotspots |
| security-reviewer | review | sonnet | OWASP Top 10, auth flows, injection vectors |
| code-reviewer | review | opus | Pre-release comprehensive review, API contracts |
| test-engineer | domain | sonnet | Test strategy, TDD, flaky test diagnosis |
| build-fixer | domain | sonnet | Compilation errors, type failures, dependency conflicts |
| designer | domain | sonnet | UX/UI architecture, accessibility, component APIs |
| writer | domain | haiku | Documentation, READMEs, changelogs, migration guides |
| qa-tester | domain | sonnet | Runtime validation, exploratory testing, bug reproduction |
| scientist | domain | sonnet | A/B tests, statistical analysis, experiment design |
| document-specialist | domain | sonnet | Official docs research, API reference, SDK validation |
| critic | coordination | opus | Plan/design adversarial review before implementation |

---

## BUILD LANE

### `explore` — Haiku
**When:** Start of any task where you need to understand the codebase first.

**Use explore when:**
- "Where is X defined?"
- "Which files handle Y?"
- "What does this module's API look like?"
- Starting a new feature and need to understand the landscape

**Do NOT use explore for:** Implementation, review, or analysis. Explore is read-only discovery.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:explore", model="haiku",
     prompt="Map all files related to authentication in this codebase. Find entry points, middleware, token handling, and session management.")
```

---

### `analyst` — Opus
**When:** Requirements are ambiguous, vague, or potentially conflict with constraints.

**Use analyst when:**
- "Build me a dashboard" (too vague)
- "Improve the performance" (needs specific targets)
- "Make it production-ready" (needs definition of done)
- Before writing a plan — analyst defines what success looks like

**Do NOT use analyst for:** Implementation or code review.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:analyst", model="opus",
     prompt="Clarify requirements for: 'Add real-time notifications'. Produce acceptance criteria, scope boundaries, and open questions.")
```

---

### `planner` — Opus
**When:** You have clear requirements and need an ordered implementation plan.

**Use planner when:**
- Building a new feature with 3+ components
- Refactoring a complex system
- Any work where ordering matters (dependency chains)

**Do NOT use planner for:** Tasks that are already well-defined at the task level. Don't plan a plan.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:planner", model="opus",
     prompt="Create an implementation plan for: JWT authentication with refresh tokens. Requirements: [paste requirements.md content]")
```

---

### `architect` — Opus
**When:** Making decisions that will be hard to undo — database choices, API designs, module boundaries.

**Use architect when:**
- Designing a new service or system
- Choosing between architectural patterns (CQRS vs CRUD, REST vs GraphQL)
- Reviewing an existing architecture for scalability or maintainability

**Do NOT use architect for:** Task-level decisions. Architecture is about the overall structure, not individual function implementations.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:architect", model="opus",
     prompt="Design the data model and API for a multi-tenant SaaS billing system. Output: Mermaid diagrams, schema definitions, API contract.")
```

---

### `debugger` — Sonnet
**When:** Something is broken and you need root cause, not just a workaround.

**Use debugger when:**
- "This test started failing but I didn't change anything"
- "Production is returning 500s intermittently"
- "The output is wrong but I can't figure out why"

**Do NOT use debugger for:** Finding bugs proactively (that's quality-reviewer). Debugger investigates known failures.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:debugger", model="sonnet",
     prompt="Investigate why the payment webhook handler fails silently when Stripe sends retries. Here's the error log: [logs]. Here's the handler code: [code].")
```

---

### `executor` — Sonnet
**When:** You have a clear, well-scoped task that needs to be implemented.

**Use executor when:**
- "Implement the user settings endpoint per this API contract"
- "Refactor this module to use the new error handling pattern"
- "Add pagination to the list endpoints"

**Do NOT use executor for:** Vague tasks ("improve the codebase"), architecture decisions, or tasks requiring deep research.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:executor", model="sonnet",
     prompt="Implement the POST /api/v1/users endpoint per this contract: [contract]. Follow the existing handler patterns in src/handlers/.")
```

---

### `deep-executor` — Opus
**When:** A task is too complex for executor — spans many files, requires sustained autonomous reasoning, or has many interdependencies.

**Use deep-executor when:**
- "Refactor the entire authentication system to use the new token model"
- "Migrate all API endpoints from v1 to v2 schema"
- Tasks estimated at >4 hours of focused implementation

**Do NOT use deep-executor for:** Routine implementation (use executor). The cost is ~5x executor.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:deep-executor", model="opus",
     prompt="Migrate all 47 API endpoints from the legacy response format to the new APIResponse wrapper. Maintain backward compatibility. Here's the migration guide: [guide].")
```

---

### `verifier` — Sonnet
**When:** After claiming work is done. The verifier's skepticism is the last line of defense.

**Use verifier when:**
- After any implementation to confirm it actually works
- Before marking a PR ready for review
- When the executor claims a task is complete

**Do NOT use verifier for:** Finding bugs (that's debugger/quality-reviewer). Verifier checks that claimed behavior is real.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:verifier", model="sonnet",
     prompt="Verify that the JWT authentication implementation meets these acceptance criteria: [criteria]. Evidence collected so far: [build logs, test output].")
```

---

## REVIEW LANE

### `quality-reviewer` — Sonnet
**When:** Proactive code quality review — finding bugs and anti-patterns before they reach production.

**Use quality-reviewer when:**
- After writing a significant amount of new code
- Before a PR merge
- When you suspect performance issues

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:quality-reviewer", model="sonnet",
     prompt="Review src/services/billing.py for logic bugs, SOLID violations, and performance issues. Focus on the charge() and refund() methods.")
```

---

### `security-reviewer` — Sonnet
**When:** Any code that handles user input, authentication, authorization, or sensitive data.

**Use security-reviewer when:**
- Adding new API endpoints
- Implementing authentication or authorization
- Handling file uploads, user-generated content, or external data

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:security-reviewer", model="sonnet",
     prompt="Security review of the new file upload endpoint in src/handlers/upload.py. Check for path traversal, file type validation, size limits, and authentication.")
```

---

### `code-reviewer` — Opus
**When:** High-stakes reviews — pre-release, architectural changes, public API changes.

**Use code-reviewer when:**
- Major feature releases
- Changes to public APIs (backward compatibility)
- Architectural refactors
- Security-critical components

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:code-reviewer", model="opus",
     prompt="Comprehensive review of the authentication system overhaul. PR diff: [diff]. Pay special attention to: token lifecycle, refresh handling, and backward compatibility with v1 clients.")
```

---

## DOMAIN LANE

### `test-engineer` — Sonnet
**When:** Designing test strategy, implementing TDD, or diagnosing flaky tests.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:test-engineer", model="sonnet",
     prompt="Design the test strategy for the billing module. Include: unit tests for domain logic, integration tests for the payment gateway, and E2E tests for the checkout flow.")
```

---

### `build-fixer` — Sonnet
**When:** The build is broken and you need it fixed fast with minimal changes.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:build-fixer", model="sonnet",
     prompt="Fix these TypeScript errors: [error output]. Make the minimum change to get the build green. Do not refactor.")
```

---

### `designer` — Sonnet
**When:** Designing user interfaces, interaction flows, or component APIs.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:designer", model="sonnet",
     prompt="Design the UX for the settings dashboard. Requirements: [requirements]. Consider: information hierarchy, progressive disclosure, and accessibility.")
```

---

### `writer` — Haiku
**When:** Writing documentation, READMEs, migration guides, or changelogs.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:writer", model="haiku",
     prompt="Write the API reference documentation for the /api/v1/users endpoints. Contract: [contract]. Style: clear, concise, with curl examples.")
```

---

### `qa-tester` — Sonnet
**When:** Interactive runtime validation of a running system.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:qa-tester", model="sonnet",
     prompt="Validate the checkout flow in the staging environment. Test: happy path, invalid credit card, concurrent checkout attempts, and session expiry mid-checkout.")
```

---

### `scientist` — Sonnet
**When:** Analyzing data, designing experiments, or interpreting A/B test results.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:scientist", model="sonnet",
     prompt="Analyze the A/B test results for the new checkout flow. Data: [CSV]. Determine if the difference is statistically significant and calculate the effect size.")
```

---

### `document-specialist` — Sonnet
**When:** You need accurate information from official documentation before implementing.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:document-specialist", model="sonnet",
     prompt="Research the Stripe API's idempotency key behavior. Find: how keys work, their scope, expiry, and retry behavior. Cite official docs only.")
```

---

## COORDINATION LANE

### `critic` — Opus
**When:** Before committing to a plan or design — adversarial review to find fatal flaws.

**Use critic when:**
- After planner produces a plan (before executor starts implementing)
- After architect produces a design (before any coding)
- When a plan seems too optimistic

**Do NOT use critic for:** Code review (that's code-reviewer/quality-reviewer). Critic reviews plans and designs, not implementations.

**Example invocation:**
```
Task(subagent_type="oh-my-claudecode:critic", model="opus",
     prompt="Adversarial review of this implementation plan: [plan.md]. Find fatal flaws, hand-waving, unvalidated assumptions, and feasibility issues. Issue APPROVE or REJECT.")
```

---

## Team Compositions

### Feature Development
```
analyst → planner → [critic if high-risk] → executor → test-engineer → quality-reviewer → verifier
```

### Bug Investigation
```
explore + debugger (parallel) → executor → verifier
```

### Architecture Review
```
explore → architect → critic → [plan revision if rejected] → architect
```

### Pre-Release Review
```
quality-reviewer + security-reviewer + code-reviewer (parallel) → verifier
```

### Documentation Sprint
```
explore → writer → [quality-reviewer for accuracy]
```
