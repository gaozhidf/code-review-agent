"""Code Review Agent - AI-powered code review with Azure DevOps integration."""

from .agent import CodeReviewAgent
from .graph import CodeReviewGraph
from .models import CodeChange, ReviewFinding, CodeReviewResult, Severity, PRSummary
from .standards import TeamStandardsManager, TeamStandards, LearnedPattern

__version__ = "0.1.0"

__all__ = [
    "CodeReviewAgent",
    "CodeReviewGraph",
    "CodeChange",
    "ReviewFinding",
    "CodeReviewResult",
    "PRSummary",
    "Severity",
    "TeamStandardsManager",
    "TeamStandards",
    "LearnedPattern",
]
