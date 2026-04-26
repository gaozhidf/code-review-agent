# Usage

## Command Line Interface

Run a review directly from the command line:

```bash
python -m code_review_agent \
  --project <your-azure-project> \
  --repository <repository-id> \
  --pr-id <pr-number>
```

This will:
1. Fetch all changes from the pull request
2. Run all applicable checks
3. Post inline comments and summary directly to Azure DevOps

## Azure DevOps Pipeline

Add this to your Azure DevOps pipeline to automatically run code review on every PR:

```yaml
# azure-pipelines.yml
trigger:
  - main

pr:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.11'

- script: |
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv sync
  displayName: Install dependencies

- script: |
    python -m code_review_agent \
      --project $(AZURE_PROJECT) \
      --repository $(AZURE_REPOSITORY_ID) \
      --pr-id $(System.PullRequest.PullRequestId)
  env:
    AZURE_DEVOPS_ORG_URL: $(AZURE_DEVOPS_ORG_URL)
    AZURE_DEVOPS_PAT: $(AZURE_DEVOPS_PAT)
    OPENAI_API_KEY: $(OPENAI_API_KEY)
    DEFAULT_LLM_MODEL: openai/gpt-4o
  displayName: Run AI Code Review
  continueOnError: true
```

**Setup:**
1. Add the above yaml to your repository as `azure-pipelines.yml`
2. Add these secrets to your Azure DevOps pipeline variables:
   - `AZURE_PROJECT` - your project name
   - `AZURE_REPOSITORY_ID` - your repository ID
   - `AZURE_DEVOPS_ORG_URL` - organization URL
   - `AZURE_DEVOPS_PAT` - personal access token
   - `OPENAI_API_KEY` - your OpenAI API key

A full example is available at [`examples/azure-pipeline.yml`](https://github.com/your-username/code-review-agent/blob/main/examples/azure-pipeline.yml).

## Python API

```python
from code_review_agent import CodeReviewAgent

agent = CodeReviewAgent()

# Review a PR and post comments to Azure DevOps
result = agent.review_pull_request(
    project="my-project",
    repository_id="my-repo-id",
    pull_request_id=123,
    post_comments=True
)

print(f"Found {len(result.findings)} findings")
print(f"Overall risk: {result.summary.overall_risk}")
```

## Output Example

### Inline Comment

> 🔴 **CRITICAL** [security] Hardcoded API key exposed
>
> This commit contains a hardcoded API key that should be removed and moved to environment variables or a secrets manager.
>
> **Suggestion:**
> Remove the hardcoded key and load it from process environment.

### PR Summary

# 🤖 AI Code Review Summary
>
> **Overall Risk**: MAJOR
>
> ## Findings by Severity
> - CRITICAL: 1
> - MAJOR: 2
> - MINOR: 3
>
> ## Key Concerns
> - Exposed API key in `src/config.py` needs immediate removal
> - Missing error handling on 2 new database queries
> - Potential N+1 query issue in the new ORM relation
>
> This PR introduces several new features but contains a critical security issue that must be addressed before merge. After addressing the security finding, the remaining issues are maintainability items that can be addressed now or in follow-up PRs.
>
> ---
> _This is an automated first-pass review. Human review is still required._
