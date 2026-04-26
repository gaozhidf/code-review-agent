from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class CodeChange(BaseModel):
    """Represents a single code change in a PR."""
    file_path: str
    diff: str
    language: Optional[str] = None
    is_new: bool = False
    is_deleted: bool = False


class ReviewFinding(BaseModel):
    """A single code review finding."""
    title: str
    description: str
    severity: Severity
    category: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    suggestion: Optional[str] = None


class PRSummary(BaseModel):
    """Summary of the entire PR review."""
    overall_risk: Severity
    total_findings: Dict[Severity, int]
    summary: str
    key_concerns: List[str] = Field(default_factory=list)


class CodeReviewResult(BaseModel):
    """Complete result of a code review."""
    pr_id: str
    repository: str
    changes: List[CodeChange]
    findings: List[ReviewFinding]
    summary: PRSummary
