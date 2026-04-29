# Architecture

This document describes the high-level architecture of `code-review-agent`.

## Overview

`code-review-agent` is an AI-powered code review tool integrated with Azure DevOps, built on top of LangGraph for orchestration and supports multiple LLM providers. It features **parallel execution** at both the checker level and file level for optimal performance.

## System Architecture

```mermaid
flowchart TD
    subgraph Entry["CLI Entry"]
        A0[__main__.py] --> A1[agent.py]
    end

    A1 -->|1. Fetch PR changes| B1[AzureDevOpsClient<br/>• Get pull request<br/>• Get iterations<br/>• Get changes<br/>• Extract diffs]

    B1 --> B2["CodeChange[]<br/>file_path + diff + language"]

    A1 -->|2. Run review| B3[CodeReviewGraph<br/>LangGraph State Machine]

    B3 --> C1[START]

    C1 --> C2[check_all<br/>LLM Checkers]

    C2 -->|concurrent| D1[UniversalChecker]
    C2 -->|concurrent| D2[BackendChecker]
    C2 -->|concurrent| D3[FrontendChecker]

    D1 --> D4["Findings[]"]
    D2 --> D5["Findings[]"]
    D3 --> D6["Findings[]"]

    C2 --> C3[run_static_analysis<br/>Static Analysis]

    C3 --> E1[ruff<br/>Python linting]
    C3 --> E2[bandit<br/>Python security]
    C3 --> E3[eslint<br/>JS/TS]

    E1 --> E4["StaticFindings[]"]
    E2 --> E4
    E3 --> E4

    C3 --> C4[run_impact_analysis<br/>Impact Analysis]

    C4 --> F1[ImpactAnalyzer<br/>AST call chains]
    C4 --> F2[PatternImpactAnalyzer<br/>Breaking changes]

    F1 --> F3["ImpactFindings[]"]
    F2 --> F3

    C4 --> C5[generate_summary<br/>Aggregate + Summarize]

    C5 --> G1["PRSummary<br/>• Count by severity<br/>• Overall risk<br/>• LLM summary"]

    C5 --> C6[END]

    G1 --> H1[CodeReviewResult]

    A1 -->|3. Post results| I1[post_review_comments<br/>• Inline comments<br/>• Summary comment]

    I1 --> I2[Azure DevOps PR]

    H1 -.->|Return| A1
```

## Parallel Execution

The system uses `ThreadPoolExecutor` for two levels of parallelism:

### 1. Checker-level Parallelism

All 3 checkers run concurrently in the `_check_all_parallel` node:

```python
# graph.py
with ThreadPoolExecutor(max_workers=3) as pool:
    universal_future = pool.submit(run_checker, self.universal_checker, changes)
    backend_future = pool.submit(run_checker, self.backend_checker, changes)
    frontend_future = pool.submit(run_checker, self.frontend_checker, changes)
```

### 2. File-level Parallelism

Each checker processes multiple files in parallel using `check_batch`:

```python
# base_checker.py
def check_batch(self, changes: List[CodeChange]) -> List[ReviewFinding]:
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(self.check, changes))
```

## LangGraph State

The entire review pipeline shares a single state object:

```python
class ReviewState(TypedDict):
    pr_id: str                       # Pull request ID
    repository: str                  # Repository ID
    changes: List[CodeChange]        # Changed files with diff content
    universal_findings: List[ReviewFinding]  # Findings from UniversalChecker
    backend_findings: List[ReviewFinding]   # Findings from BackendChecker
    frontend_findings: List[ReviewFinding]  # Findings from FrontendChecker
    static_findings: List[ReviewFinding]     # Findings from Static Analysis
    impact_findings: List[ReviewFinding]     # Findings from Impact Analysis
    summary: Optional[PRSummary]     # Final summary generated at the end
    completed: bool                  # Completion flag
```

## Checker Responsibilities

| Checker | Scope | What it checks |
|---------|-------|----------------|
| `UniversalChecker` | All code | Correctness, logic errors, missing error handling, security issues, complexity, naming, duplication, exposed secrets |
| `BackendChecker` | Backend code (.py, .java, .go, .js, .ts, .rb, .php, .cs, .cpp) | API contract consistency, N+1 queries, missing indexes, transaction issues, performance blocking calls, observability gaps, retries/timeouts |
| `FrontendChecker` | Frontend code (.js, .jsx, .ts, .tsx, .vue, .svelte, .html, .css, .scss, .less, .astro) | State race conditions, unnecessary re-renders, accessibility, XSS vulnerabilities, bundle size issues |

Each checker runs independently, can add zero or more findings, and findings are accumulated through the graph pipeline.

## Data Models

| Model | Purpose |
|-------|---------|
| `CodeChange` | Holds file path, diff content, detected language, change type (new/deleted/modified) |
| `ReviewFinding` | Single finding: title, description, severity, category, file_path, line numbers, suggestion |
| `PRSummary` | Aggregated summary: overall risk, count by severity, key concerns, natural language summary |
| `CodeReviewResult` | Final result container: PR ID + all changes + all findings + summary |

## Azure DevOps SDK Compatibility

This project uses `azure-devops 7.1.0b4` (beta preview). The SDK has breaking changes compared to stable versions:

- `change.item` is now stored in `change.additional_properties['item']`
- `change.change_type` renamed to `change.additional_properties['changeType']`
- `git_client.create_pull_request_thread()` renamed to `git_client.create_thread()`
- Inline comments use `CommentThreadContext` and `CommentPosition` SDK objects

All adaptations are handled in `src/code_review_agent/integrations/azure_devops.py`.

## Entry Flow

1. **CLI**: `python -m code_review_agent --project <project> --repository <repo> --pr-id <id>`
2. **CodeReviewAgent.review_pull_request()**
   - Creates AzureDevOpsClient, fetches all changes
   - Initializes LangGraph and runs pipeline
   - Posts comments back to Azure DevOps
   - Returns result
3. Done.

## Sequence Diagram

```mermaid
sequenceDiagram
    participant CLI
    participant Agent as CodeReviewAgent
    participant ADO as AzureDevOpsClient
    participant Graph as CodeReviewGraph
    participant LLM

    CLI->>Agent: run review
    Agent->>ADO: get_pull_request_changes
    ADO-->>Agent: CodeChange[]

    Agent->>Graph: run(CodeChange[])

    par 1. LLM Checkers (Parallel)
        par UniversalChecker
            Graph->>UniversalChecker: check_batch(changes)
            UniversalChecker->>UniversalChecker: Parallel LLM calls per file
        and BackendChecker
            Graph->>BackendChecker: check_batch(changes)
            BackendChecker->>BackendChecker: Parallel LLM calls per file
        and FrontendChecker
            Graph->>FrontendChecker: check_batch(changes)
            FrontendChecker->>FrontendChecker: Parallel LLM calls per file
        end
    end

    Graph->>Graph: 2. run_static_analysis

    par 3. Static Analysis Tools
        Graph->>Graph: ruff (Python files)
        Graph->>Graph: bandit (Python files)
        Graph->>Graph: eslint (JS/TS files)
    end

    Graph->>Graph: 4. run_impact_analysis

    par 5. Impact Analysis
        Graph->>Graph: ImpactAnalyzer (AST call chains)
        Graph->>Graph: PatternImpactAnalyzer (breaking changes)
    end

    Graph->>Graph: _generate_summary(all_findings)

    Graph-->>Agent: CodeReviewResult

    Agent->>ADO: post_review_comments
```

## Analyzer Pipeline

```mermaid
flowchart LR
    subgraph Input["PR Changes"]
        Files[Changed Files]
    end

    subgraph LLM["LLM-Based Analysis (Parallel)"]
        UC[UniversalChecker]
        BC[BackendChecker]
        FC[FrontendChecker]
    end

    subgraph Static["Static Analysis"]
        RA[StaticAnalyzer]
        R[ruff]
        B[bandit]
        E[eslint]
        R & B & E --> RA
    end

    subgraph Impact["Impact Analysis"]
        IA[ImpactAnalyzer<br/>AST-based]
        PA[PatternImpactAnalyzer<br/>Pattern-based]
    end

    subgraph Output["Unified Output"]
        F["ReviewFinding[]"]
        Sum[PRSummary]
    end

    Files --> LLM
    Files --> Static
    Files --> Impact

    UC --> F
    BC --> F
    FC --> F
    RA --> F
    IA --> F
    PA --> F

    F --> Sum
```

## Analyzer Components

### Static Analysis (`analyzers/static_analyzer.py`)

Integrated static analysis tools:

| Tool | Language | What it checks |
|------|----------|----------------|
| `ruff` | Python | Linting, code style, complexity |
| `bandit` | Python | Security vulnerabilities |
| `eslint` | JavaScript/TypeScript | Code style, potential bugs |

Features:
- Auto-detects available tools on the system
- Converts tool output to standardized `ReviewFinding` format
- Severity mapping from tool-specific to unified severity levels

### Impact Analysis (`analyzers/impact_analyzer.py`)

Analyzes potential impact of code changes:

| Analyzer | Purpose |
|----------|---------|
| `ImpactAnalyzer` | AST-based function call tracking |
| `PatternImpactAnalyzer` | Pattern matching for breaking changes |

Detects:
- Deleted functions/classes (breaking changes)
- API contract changes
- Decorator changes on public APIs
- Pattern-based breaking change detection
