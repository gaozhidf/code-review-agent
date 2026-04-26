# code-review-agent

🤖 AI-powered code review agent integrated with Azure DevOps, supporting multiple LLM providers.

Automate code quality inspection for backend and frontend pull requests, with configurable severity levels and team-specific standards learning.

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
- Inline PR comments with severity classification (`critical > major > minor`)
- PR-level risk summary explaining what changed and why it matters
- Learns and enforces team-specific standards from past PRs
- Acts as a first-pass reviewer, **never auto-approves**

### Multiple LLM Support
- OpenAI GPT-4o / GPT-4o-mini
- Anthropic Claude 3
- Google Gemini 1.5

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-username/code-review-agent.git
cd code-review-agent

# Install dependencies with uv
uv sync

# Configure environment
cp .env.example .env
# Edit .env to add your API keys

# Run via CLI
python -m code_review_agent --project your-project --repository your-repo-id --pr-id 123
```
