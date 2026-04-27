# Architecture

This document describes the high-level architecture of `code-review-agent`.

## Overview

`code-review-agent` is an AI-powered code review tool integrated with Azure DevOps, built on top of LangGraph for orchestration and supports multiple LLM providers. It features **parallel execution** at both the checker level and file level for optimal performance.

## System Architecture

```mermaid
flowchart TD
    subgraph Entry["CLI Entry"]
        __main__.py --> agent.py
    end
    
    agent.py -->|1. Fetch PR changes| Azure[AzureDevOpsClient
* Get pull request
* Get iterations
* Get changes
* Extract diffs]
    
    Azure --> Changes["CodeChange[]<br/>file_path + diff + language"]
    
    agent.py -->|2. Run review| LangGraph[CodeReviewGraph
LangGraph State Machine]
    
    subgraph LangGraph["LangGraph Pipeline"]
        START([START]) --> check_all
        check_all --> generate_summary
        generate_summary --> END([END])
    end
    
    subgraph ParallelCheck["Parallel Execution (ThreadPoolExecutor)"]
        direction LR
        check_all -->|concurrent| Universal[UniversalChecker]
        check_all -->|concurrent| Backend[BackendChecker]
        check_all -->|concurrent| Frontend[FrontendChecker]
        
        Universal -->|parallel files| U1[File 1]
        Universal -->|parallel files| U2[File 2]
        Universal -->|parallel files| UN[N files]
        
        Backend -->|parallel files| B1[File 1]
        Backend -->|parallel files| B2[File 2]
        Backend -->|parallel files| BN[N files]
        
        Frontend -->|parallel files| F1[File 1]
        Frontend -->|parallel files| F2[File 2]
        Frontend -->|parallel files| FN[N files]
    end
    
    subgraph CheckerLogic["Each Checker"]
        direction TB
        L["Receive CodeChange[]"] --> M["Inject LLM prompt +<br/>Team coding standards"] --> N[Call LLM] --> O["Parse findings"] --> P["Return list of findings"]
    end
    
    subgraph LLM["LLM Layer"]
        direction TB
        LLMConfig -->|get_default_llm| Provider{Provider}
        Provider --> OpenAI
        Provider --> Gemini
        Provider --> Anthropic
    end
    
    generate_summary -->|aggregates findings| Summary[PRSummary
* Count by severity
* Calculate overall risk
* LLM generate summary]
    
    LangGraph --> CodeReviewResult
    
    agent.py -->|3. Post results| Post[post_review_comments
* Post inline comments
* Post summary comment]
    
    Post --> AzureDevOps[Azure DevOps PR]
    
    CodeReviewResult --> agent.py
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

    par Parallel Checkers
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

    Graph->>Graph: _generate_summary(all_findings)

    Graph-->>Agent: CodeReviewResult

    Agent->>ADO: post_review_comments
```
