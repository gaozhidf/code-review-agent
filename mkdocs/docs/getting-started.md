# Getting Started

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management (or use pip)
- Azure DevOps account with PAT (Personal Access Token)
- LLM API key (OpenAI / Anthropic / Google Gemini)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/code-review-agent.git
cd code-review-agent
```

2. Install dependencies with uv:
```bash
uv sync
```

Or with pip:
```bash
pip install -r requirements.txt
```

3. Copy the environment template:
```bash
cp .env.example .env
```

4. Edit `.env` to configure your credentials:
```env
# Choose at least one LLM provider
OPENAI_API_KEY=your-openai-key
# ANTHROPIC_API_KEY=your-anthropic-key
# GEMINI_API_KEY=your-gemini-key

# Azure DevOps
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-organization
AZURE_DEVOPS_PAT=your-personal-access-token

# Choose your default model
DEFAULT_LLM_MODEL=openai/gpt-4o
```

## Creating your team standards file

```bash
cp config/team-standards.json.example config/team-standards.json
```

You can add learned patterns and severity overrides later.

## Verify Installation

```bash
python -c "from code_review_agent import CodeReviewAgent; print('OK')"
```
