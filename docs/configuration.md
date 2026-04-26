# Configuration

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI |
| `OPENAI_BASE_URL` | OpenAI API base URL | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Anthropic |
| `GEMINI_API_KEY` | Google Gemini API key | If using Gemini |
| `AZURE_DEVOPS_ORG_URL` | Azure DevOps organization URL | Required for Azure integration |
| `AZURE_DEVOPS_PAT` | Azure DevOps Personal Access Token | Required |
| `DEFAULT_LLM_MODEL` | Default LLM to use | Default: `openai/gpt-4o` |
| `TEAM_STANDARDS_PATH` | Path to team standards JSON file | Default: `./config/team-standards.json` |

## LLM Model Format

Models are specified as `provider/model-name`:

| Provider | Examples |
|----------|----------|
| `openai` | `openai/gpt-4o`, `openai/gpt-4o-mini`, `openai/gpt-4-turbo` |
| `anthropic` | `anthropic/claude-3-opus-20240229`, `anthropic/claude-3-sonnet-20240229` |
| `gemini` | `gemini/gemini-1.5-pro-latest`, `gemini/gemini-1.5-flash-latest` |

## Team Standards

The team standards file is a JSON with this format:

```json
{
  "project_id": "your-project-id",
  "learned_patterns": [
    {
      "pattern": "We require all database queries to have pagination limits to prevent out-of-memory issues",
      "category": "performance",
      "severity": "major",
      "example_commit_sha": "abc123def",
      "example_file": "src/db/queries.py",
      "occurrences": 3
    }
  ],
  "severity_overrides": {
    "hardcoded_secret": "critical",
    "missing_error_handling": "major"
  }
}
```

See [Team Standards](team-standards.md) for more information.

## Azure DevOps PAT Permissions

Your PAT needs these permissions:
- **Code (Read & Write)** - to fetch diff and post comments
- **Pull Request Threads (Contribute)** - to create review threads
