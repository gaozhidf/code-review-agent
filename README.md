# code-review-agent

AI-powered code review agent integrated with Azure DevOps, supporting multiple LLM providers (Gemini/OpenAI/Anthropic). Automates code quality inspection for backend and frontend code.

## Features

### Universal Code Checks
- **Correctness**: Detects logic errors, edge case gaps, missing error handling
- **Security**: Identifies injection risks, authentication/authorization gaps, exposed secrets, unsafe API usage
- **Maintainability**: Flags excessive complexity, poor naming, code duplication, tight coupling
- **Tests**: Catches missing test coverage, weak assertions, broken assumptions

### Backend Specific Checks
- API contract consistency and breaking changes detection
- Data access issues (N+1 queries, missing indexes, transaction problems)
- Performance & scalability risks (blocking calls, heavy loops)
- Observability gaps (missing logs/metrics, improper retries/timeouts)

### Frontend Specific Checks
- State & async issues (race conditions, unnecessary re-renders)
- Accessibility problems (missing semantic HTML, ARIA issues, keyboard navigation gaps)
- Performance issues (large bundle size, unnecessary renders)
- Client-side security risks (XSS vulnerabilities, unsafe DOM usage)

### Azure DevOps Workflow Integration
- Inline PR comments with severity classification (critical > major > minor)
- PR-level risk summary explaining what changed and why it matters
- Supports learning and enforcing team-specific standards from past PRs
- Acts as a first-pass reviewer, never auto-approves

## Configuration

Copy `.env.example` to `.env` and set your:
- Azure DevOps credentials
- LLM provider API key (choose one or more)
- Team-specific rules configuration

## Installation

```bash
uv sync
```

## Usage

### Run as CLI tool

```bash
# Activate virtual environment
source .venv/bin/activate

# Run code review on a pull request
python -m code_review_agent --project <your-project> --repository <repository-id> --pr-id <pr-number>
```

Example:
```bash
python -m code_review_agent --project code_agent --repository ecb5e9be-f3be-4a93-8fe0-83b893641a04 --pr-id 2
```

## Workflow

### Overall Agent Flow

```mermaid
flowchart TD
    A[Trigger: Run agent on PR] --> B[Fetch PR changes from Azure DevOps]
    B --> C[Extract diff content for each changed file]
    C --> D[LangGraph Review Pipeline]
    D --> E[Aggregate findings + generate summary]
    E --> F[Post inline comments to PR lines]
    F --> G[Post overall summary as top-level comment]
    G --> H[Done - Human review proceeds]
```

### Full System Architecture

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

### Parallel Execution Architecture

The system uses `ThreadPoolExecutor` for two levels of parallelism:

1. **Checker-level parallelism**: All 3 checkers (Universal, Backend, Frontend) run concurrently
2. **File-level parallelism**: Each checker processes multiple files in parallel (default 10 workers)

```python
# In graph.py - Checker parallelism
with ThreadPoolExecutor(max_workers=3) as pool:
    universal_future = pool.submit(run_checker, self.universal_checker, changes)
    backend_future = pool.submit(run_checker, self.backend_checker, changes)
    frontend_future = pool.submit(run_checker, self.frontend_checker, changes)

# In base_checker.py - File parallelism
def check_batch(self, changes: List[CodeChange]) -> List[ReviewFinding]:
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(self.check, changes))
```

### LangGraph State & Checkers

**Graph State (`ReviewState`)**:
- `pr_id`: Pull request ID
- `repository`: Repository ID
- `changes`: List of changed files with diff
- `universal_findings`: Findings from UniversalChecker
- `backend_findings`: Findings from BackendChecker
- `frontend_findings`: Findings from FrontendChecker
- `summary`: Final PR summary with risk assessment
- `completed`: Completion flag

**Checker Responsibilities**:

| Checker | Scope | What it checks |
|---------|-------|----------------|
| `UniversalChecker` | All code | Correctness, logic errors, missing error handling, security issues, complexity, naming, duplication, exposed secrets |
| `BackendChecker` | Backend code (.py, .java, .go, .js, .ts, .rb, .php, .cs, .cpp) | API contract consistency, N+1 queries, missing indexes, transaction issues, performance blocking calls, observability gaps, retries/timeouts |
| `FrontendChecker` | Frontend code (.js, .jsx, .ts, .tsx, .vue, .svelte, .html, .css, .scss, .less, .astro) | State race conditions, unnecessary re-renders, accessibility, XSS vulnerabilities, bundle size issues |

Each checker runs independently, can add zero or more findings, and findings are accumulated through the graph pipeline.

## Project Structure

```
code-review-agent/
├── src/code_review_agent/
│   ├── __main__.py          # CLI entry point
│   ├── agent.py             # Top-level review orchestration
│   ├── graph.py             # LangGraph definition (CodeReviewGraph)
│   ├── models.py            # Data models (CodeChange, Finding, PRSummary...)
│   ├── standards.py         # Team coding standards injection
│   ├── llm_config.py        # LLM provider configuration
│   ├── checkers/            # Individual checkers
│   │   ├── universal.py     # Universal checks
│   │   ├── backend.py       # Backend-specific checks
│   │   └── frontend.py      # Frontend-specific checks
│   ├── integrations/
│   │   └── azure_devops.py  # Azure DevOps API client (fixed for v7.1.0b4)
├── pyproject.toml
├── uv.lock
└── README.md
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_DEVOPS_ORG_URL` | Azure DevOps organization URL | Yes |
| `AZURE_DEVOPS_PAT` | Personal Access Token with code read/write permissions | Yes |
| `LLM_PROVIDER` | `openai` \/ `gemini` \/ `anthropic` | Yes |
| `LLM_API_KEY` | API key for your LLM provider | Yes |
| `LLM_MODEL` | Model name (optional, uses provider default if not set) | No |

## Notes on Azure DevOps SDK Compatibility

This project currently works with **azure-devops 7.1.0b4** (beta). Breaking changes in the preview SDK have been adapted in code:
- `change.item` is now accessed from `additional_properties`
- `change.change_type` renamed to `changeType`
- `create_pull_request_thread` renamed to `create_thread`

If you encounter further API errors, check the SDK version and update compatibility layer in `azure_devops.py`.

## License

MIT
