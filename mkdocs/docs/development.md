# Development

## Running Tests

```bash
uv run pytest tests/
```

## Code Formatting

```bash
uv run black .
uv run ruff check --fix .
```

## Project Structure

```
code-review-agent/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/
│   └── team-standards.json.example
├── examples/
│   └── azure-pipeline.yml
├── mkdocs.yml             # MkDocs configuration
├── mkdocs/
│   └── docs/              # Documentation source
│       ├── index.md
│       ├── getting-started.md
│       ├── configuration.md
│       ├── usage.md
│       ├── team-standards.md
│       └── development.md
├── src/
│   └── code_review_agent/
│       ├── __init__.py
│       ├── __main__.py    # CLI entry
│       ├── models.py      # Data models
│       ├── llm_config.py  # LLM config
│       ├── agent.py       # Main agent
│       ├── graph.py       # LangGraph workflow
│       ├── standards.py   # Team standards learning
│       ├── checkers/      # Code checkers
│       │   ├── base_checker.py
│       │   ├── universal_checker.py
│       │   ├── backend_checker.py
│       │   └── frontend_checker.py
│       └── integrations/
│           └── azure_devops.py
└── tests/
    └── test_review.py
```

## Building Docs

With `mkdocs-material` installed:

```bash
mkdocs serve  # Local preview
mkdocs build  # Build static site
```

## Deploy to GitHub Pages

A pre-built GitHub Actions workflow is included at `.github/workflows/deploy-docs.yml` that automatically deploys your docs to GitHub Pages on push to main.

1. Enable GitHub Pages in your repository settings with "Deploy from a branch"
2. Select `gh-pages` branch as the source
3. Push to main and the workflow will automatically build and deploy
