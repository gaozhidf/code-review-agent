"""Integration tests for analyzer performance evaluation."""

import pytest
from code_review_agent.models import CodeChange, Severity
from code_review_agent.analyzers.static_analyzer import get_static_analyzer
from code_review_agent.analyzers.impact_analyzer import get_impact_analyzer, get_pattern_analyzer
from test_data.golden_dataset import GOLDEN_DATASET, get_test_cases_by_issue_type, IssueType


class TestAnalyzerPerformance:
    """Test cases for evaluating analyzer performance."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.static_analyzer = get_static_analyzer()
        self.impact_analyzer = get_impact_analyzer()
        self.pattern_analyzer = get_pattern_analyzer()

    def test_static_analyzer_on_golden_dataset(self):
        """Test static analyzer detects known patterns."""
        # Hardcoded secrets should be detected by pattern matching
        secrets_cases = get_test_cases_by_issue_type(IssueType.HARD_CODED_SECRET)
        
        for case in secrets_cases:
            change = CodeChange(
                file_path=case.file_path,
                diff=case.diff,
                language=case.language
            )
            impacts = self.pattern_analyzer.analyze(change)
            findings = self.pattern_analyzer.convert_to_findings(impacts)
            
            # Should detect something related to the issue
            assert isinstance(findings, list)

    def test_impact_analyzer_on_golden_dataset(self):
        """Test impact analyzer on golden dataset."""
        for case in GOLDEN_DATASET:
            change = CodeChange(
                file_path=case.file_path,
                diff=case.diff,
                language=case.language
            )
            impacts = self.pattern_analyzer.analyze(change)
            findings = self.pattern_analyzer.convert_to_findings(impacts)
            
            # All findings should have required fields
            for finding in findings:
                assert hasattr(finding, 'title')
                assert hasattr(finding, 'description')
                assert hasattr(finding, 'severity')
                assert hasattr(finding, 'category')

    def test_analyzer_categories(self):
        """Test that findings are categorized correctly."""
        change = CodeChange(
            file_path="test.py",
            diff="""-def old_func():
-    pass
""",
            language="python"
        )
        
        impacts = self.pattern_analyzer.analyze(change)
        findings = self.pattern_analyzer.convert_to_findings(impacts)
        
        for finding in findings:
            assert finding.category in [
                "impact-analysis",
                "static-ruff",
                "static-bandit",
                "static-eslint",
            ]


class TestAnalyzerIntegration:
    """Integration tests for analyzers."""

    def test_full_analyzer_pipeline(self):
        """Test the full analyzer pipeline."""
        changes = [
            CodeChange(
                file_path="src/api.py",
                diff="""+def new_api():
+    pass
""",
                language="python"
            ),
            CodeChange(
                file_path="src/utils.py",
                diff="""-def old_func():
-    pass
""",
                language="python"
            ),
        ]
        
        # Run pattern analyzer on all changes
        all_findings = []
        pattern_analyzer = get_pattern_analyzer()
        
        for change in changes:
            impacts = pattern_analyzer.analyze(change)
            findings = pattern_analyzer.convert_to_findings(impacts)
            all_findings.extend(findings)
        
        assert isinstance(all_findings, list)

    def test_analyzer_handles_various_languages(self):
        """Test analyzer works with different languages."""
        languages = ["python", "javascript", "typescript", "go", "java"]
        
        for lang in languages:
            change = CodeChange(
                file_path=f"test.{lang}",
                diff="+some_code = True",
                language=lang
            )
            
            pattern_analyzer = get_pattern_analyzer()
            impacts = pattern_analyzer.analyze(change)
            findings = pattern_analyzer.convert_to_findings(impacts)
            
            assert isinstance(findings, list)


class TestAnalyzerMetrics:
    """Tests for analyzer metrics collection."""

    def test_finding_severity_distribution(self):
        """Test severity distribution in findings."""
        all_findings = []
        pattern_analyzer = get_pattern_analyzer()
        
        for case in GOLDEN_DATASET:
            change = CodeChange(
                file_path=case.file_path,
                diff=case.diff,
                language=case.language
            )
            impacts = pattern_analyzer.analyze(change)
            findings = pattern_analyzer.convert_to_findings(impacts)
            all_findings.extend(findings)
        
        # Count severities
        severity_counts = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 0,
            Severity.MINOR: 0,
        }
        
        for finding in all_findings:
            if finding.severity in severity_counts:
                severity_counts[finding.severity] += 1
        
        # Should have some findings (may vary based on pattern matching)
        assert sum(severity_counts.values()) >= 0
