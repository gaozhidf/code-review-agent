# Architecture

This document describes the high-level architecture of `code-review-agent`.

## Overview

`code-review-agent` is an AI-powered code review tool integrated with Azure DevOps, built on top of LangGraph for orchestration and supports multiple LLM providers.

## System Architecture

```mermaid
flowchart TD
    subgraph Entry["CLI Entry"]
        __main__.py --> agent.py
    end
    
    agent.py -->|1. Fetch PR changes| Azure[AzureDevOpsClient\n* Get pull request\n* Get iterations\n* Get changes\n* Extract diffs]
    
    Azure --> Changes["CodeChange[]<br/>file_path + diff + language"]
    
    agent.py -->|2. Run review| LangGraph[CodeReviewGraph\nLangGraph State Machine]
    
    subgraph LangGraph["LangGraph Pipeline"]
        direction LR
        START([START]) --> check_universal
        check_universal --> check_backend
        check_backend --> check_frontend
        check_frontend --> generate_summary
        generate_summary --> END([END])
    end
    
    subgraph Checkers["Checkers (Nodes)"]
        direction TB
        check_universal --> UniversalChecker --> findings1[accumulate findings]
        check_backend --> BackendChecker --> findings2[accumulate findings]
        check_frontend --> FrontendChecker --> findings3[accumulate findings]
    end
    
    subgraph CheckerLogic["Each Checker"]
        direction TB
        A["Receive CodeChange"] --> B["Inject LLM prompt +<br/>Team coding standards"] --> C[Call LLM] --> D["Parse JSON findings"] --> E["Return list of findings"]
    end
    
    subgraph LLM["LLM Layer"]
        direction TB
        LLMConfig -->|get_default_llm| Provider{Provider}
        Provider --> OpenAI
        Provider --> Gemini
        Provider --> Anthropic
    end
    
    generate_summary -->|aggregates findings| Summary[PRSummary\n* Count by severity\n* Calculate overall risk\n* LLM generate summary]
    
    LangGraph --> CodeReviewResult
    
    agent.py -->|3. Post results| Post[post_review_comments\n* Post inline comments\n* Post summary comment]
    
    Post --> AzureDevOps[Azure DevOps PR]
    
    CodeReviewResult --> agent.py
```

## LangGraph State

The entire review pipeline shares a single state object:

```python
class ReviewState(TypedDict):
    pr_id: str                       # Pull request ID
    repository: str                  # Repository ID
    changes: List[CodeChange]        # Changed files with diff content
    findings: List[ReviewFinding]    # Accumulated findings (mutated by nodes)
    summary: Optional[PRSummary]     # Final summary generated at the end
    completed: bool                  # Completion flag
```

## Checker Responsibilities

| Checker | Scope | What it checks |
|---------|-------|----------------|
| `UniversalChecker` | All code | Correctness, logic errors, missing error handling, security issues, complexity, naming, duplication, exposed secrets |
| `BackendChecker` | Backend code | API contract consistency, N+1 queries, missing indexes, transaction issues, performance blocking calls, observability gaps, retries/timeouts |
| `FrontendChecker` | Frontend code | State race conditions, unnecessary re-renders, accessibility, XSS vulnerabilities, bundle size issues |

Each checker runs independently, can add zero or more findings, and findings are accumulated through the graph pipeline.

## Data Models

| Model | Purpose |
|-------|---------|
| `CodeChange` | Holds file path, diff content, detected language, change type (new/deleted/modified) |
| `ReviewFinding` | Single finding: title, description, severity, category, line numbers, suggestion |
| `PRSummary` | Aggregated summary: overall risk, count by severity, key concerns, natural language summary |
| `CodeReviewResult` | Final result container: PR ID + all changes + all findings + summary |

## Azure DevOps SDK Compatibility

This project uses `azure-devops 7.1.0b4` (beta preview). The SDK has breaking changes compared to stable versions:

- `change.item` is now stored in `change.additional_properties['item']`
- `change.change_type` renamed to `change.additional_properties['changeType']`
- `git_client.create_pull_request_thread()` renamed to `git_client.create_thread()`

All adaptations are handled in `src/code_review_agent/integrations/azure_devops.py`.

## Entry Flow

1. **CLI**: `python -m code_review_agent --project <project> --repository <repo> --pr-id <id>`
2. **CodeReviewAgent.review_pull_request()**
   - Creates AzureDevOpsClient, fetches all changes
   - Initializes LangGraph and runs pipeline
   - Posts comments back to Azure DevOps
   - Returns result
3. Done.

## Sequence Diagram (Textual)

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

    Agent->>Graph: analyze(CodeChange)

    par Universal Check
        Graph->>Graph: check_universal
        Graph->>Graph: UniversalChecker
    and Backend Check
        Graph->>Graph: check_backend
        Graph->>Graph: BackendChecker
    and Frontend Check
        Graph->>Graph: check_frontend
        Graph->>Graph: FrontendChecker
    end

    Graph-->>Agent: findings

    Agent->>LLM: generate_summary(findings)
    LLM-->>Agent: PRSummary

    Agent->>ADO: post_review_comments
```
