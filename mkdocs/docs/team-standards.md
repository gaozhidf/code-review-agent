# Team Standards Learning

code-review-agent can learn your team's specific coding standards from past pull request reviews.

## How it works

1. After a human reviewer identifies a pattern that should be enforced in future reviews, you can add it to the learned patterns.
2. Every subsequent code review will automatically check for these patterns and apply your configured severity levels.
3. Severity overrides let you increase/decrease the default severity for specific issue types.

## Adding a Learned Pattern

```python
from code_review_agent import TeamStandardsManager
from code_review_agent.models import Severity

manager = TeamStandardsManager()

# Learn a new pattern
manager.learn_from_past_review(
    pattern="All API routes must have OpenAPI/schema documentation",
    category="backend/api-contract",
    severity=Severity.MAJOR,
    commit_sha="abc123def456",  # optional, example where this was caught
    file_path="src/routes/users.py"  # optional
)

# Override severity for a specific issue type
manager.add_severity_override("hardcoded secrets", Severity.CRITICAL)
manager.add_severity_override("missing test coverage", Severity.MINOR)
```

## What gets injected into the prompt

All learned patterns and severity overrides are automatically injected into the LLM prompt for every code review:

```text
**Team-Specific Standards to Enforce:**

**Learned Patterns from Past PRs:**
- [major / backend/api-contract]: All API routes must have OpenAPI/schema documentation

**Severity Overrides:**
- hardcoded secrets: critical
- missing test coverage: minor
```

## Example Use Cases

- Team conventions (e.g., "We always use dependency injection")
- Project-specific security requirements
- Performance expectations specific to your codebase
- Naming conventions that aren't caught by linters
- Architectural patterns that should be followed

## File Format

The team standards are stored in a JSON file:

```json
{
  "project_id": "my-project",
  "learned_patterns": [
    {
      "pattern": "All API routes must have OpenAPI documentation",
      "category": "backend/api-contract",
      "severity": "major",
      "example_commit_sha": "abc123",
      "example_file": "src/routes/users.py",
      "occurrences": 1
    }
  ],
  "severity_overrides": {
    "hardcoded_secret": "critical",
    "missing_error_handling": "major"
  }
}
```

The file is automatically updated when you learn new patterns, you don't need to edit it manually.
