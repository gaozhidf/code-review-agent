import json
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from code_review_agent.models import ReviewFinding, Severity


class LearnedPattern(BaseModel):
    """A learned pattern from past PR reviews."""
    pattern: str  # Description of the pattern/rule
    category: str
    severity: Severity
    example_commit_sha: Optional[str] = None
    example_file: Optional[str] = None
    occurrences: int = 1


class TeamStandards(BaseModel):
    """Team-specific learned standards."""
    project_id: str
    learned_patterns: List[LearnedPattern] = Field(default_factory=list)
    severity_overrides: Dict[str, Severity] = Field(default_factory=dict)


class TeamStandardsManager:
    """Manages learning and applying team-specific code review standards."""
    
    def __init__(self, standards_path: Optional[str] = None):
        if standards_path is None:
            standards_path = os.getenv(
                "TEAM_STANDARDS_PATH",
                "./config/team-standards.json"
            )
        self.standards_path = standards_path
        self.standards = self._load_standards()
    
    def _load_standards(self) -> TeamStandards:
        """Load standards from disk."""
        if not os.path.exists(self.standards_path):
            # Return empty standards if file doesn't exist
            return TeamStandards(project_id="default")
        
        with open(self.standards_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return TeamStandards(**data)
    
    def _save_standards(self) -> None:
        """Save standards to disk."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.standards_path), exist_ok=True)
        
        with open(self.standards_path, "w", encoding="utf-8") as f:
            json.dump(self.standards.model_dump(), f, indent=2)
    
    def get_standards_prompt(self) -> str:
        """Generate prompt text to inject into review to enforce team standards."""
        if not self.standards.learned_patterns and not self.standards.severity_overrides:
            return ""
        
        lines = [
            "\n**Team-Specific Standards to Enforce:**",
            ""
        ]
        
        if self.standards.learned_patterns:
            lines.append("**Learned Patterns from Past PRs:**")
            for pattern in self.standards.learned_patterns:
                lines.append(f"- [{pattern.severity} / {pattern.category}]: {pattern.pattern}")
            lines.append("")
        
        if self.standards.severity_overrides:
            lines.append("**Severity Overrides:**")
            for issue_type, severity in self.standards.severity_overrides.items():
                lines.append(f"- {issue_type}: {severity}")
            lines.append("")
        
        return "\n".join(lines)
    
    def override_severity(self, finding: ReviewFinding) -> ReviewFinding:
        """Apply severity overrides from team standards."""
        for issue_type, severity in self.standards.severity_overrides.items():
            if issue_type.lower() in finding.title.lower() or issue_type.lower() in finding.description.lower():
                finding.severity = severity
        return finding
    
    def learn_from_past_review(
        self,
        pattern: str,
        category: str,
        severity: Severity,
        commit_sha: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> None:
        """Learn a new pattern from human feedback on a past PR."""
        # Check if pattern already exists
        for existing in self.standards.learned_patterns:
            if existing.pattern.lower() == pattern.lower():
                existing.occurrences += 1
                if commit_sha:
                    existing.example_commit_sha = commit_sha
                if file_path:
                    existing.example_file = file_path
                self._save_standards()
                return
        
        # Add new pattern
        self.standards.learned_patterns.append(LearnedPattern(
            pattern=pattern,
            category=category,
            severity=severity,
            example_commit_sha=commit_sha,
            example_file=file_path,
            occurrences=1
        ))
        self._save_standards()
    
    def add_severity_override(self, issue_type: str, severity: Severity) -> None:
        """Add or update a severity override."""
        self.standards.severity_overrides[issue_type] = severity
        self._save_standards()
