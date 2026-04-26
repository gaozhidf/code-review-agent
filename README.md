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

Coming soon
