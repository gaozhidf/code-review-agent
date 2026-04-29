"""Tests for static analyzer."""

import pytest
from code_review_agent.analyzers.static_analyzer import (
    StaticAnalyzer, ToolResult, get_static_analyzer
)
from code_review_agent.models import ReviewFinding, Severity


class TestStaticAnalyzer:
    """Test cases for StaticAnalyzer."""

    def test_tool_detection(self):
        """Test that static analyzer can detect available tools."""
        analyzer = StaticAnalyzer()
        # Should at least initialize without error
        assert analyzer is not None

    def test_get_language_python(self):
        """Test language detection for Python files."""
        analyzer = StaticAnalyzer()
        assert analyzer._get_language(".py") == "python"

    def test_get_language_javascript(self):
        """Test language detection for JavaScript files."""
        analyzer = StaticAnalyzer()
        assert analyzer._get_language(".js") == "javascript"
        assert analyzer._get_language(".jsx") == "javascript"

    def test_get_language_typescript(self):
        """Test language detection for TypeScript files."""
        analyzer = StaticAnalyzer()
        assert analyzer._get_language(".ts") == "typescript"
        assert analyzer._get_language(".tsx") == "typescript"

    def test_get_language_unknown(self):
        """Test language detection for unknown extensions."""
        analyzer = StaticAnalyzer()
        assert analyzer._get_language(".xyz") is None

    def test_convert_to_findings(self):
        """Test conversion of tool results to ReviewFinding."""
        analyzer = StaticAnalyzer()
        
        tool_results = [
            ToolResult(
                tool="ruff",
                file_path="test.py",
                line=10,
                column=1,
                rule_id="W503",
                message="Line too long",
                severity="warning",
            ),
            ToolResult(
                tool="bandit",
                file_path="test.py",
                line=20,
                column=1,
                rule_id="B101",
                message="Use of hardcoded password",
                severity="error",
            ),
        ]

        findings = analyzer.convert_to_findings(tool_results)
        
        assert len(findings) == 2
        assert any(f.severity == Severity.MINOR for f in findings)  # W503 -> MINOR
        assert any(f.severity == Severity.CRITICAL for f in findings)  # bandit error -> CRITICAL

    def test_analyze_file_unknown_language(self):
        """Test analyzing a file with unknown language."""
        analyzer = StaticAnalyzer()
        results = analyzer.analyze_file("test.xyz", "some content")
        assert results == []

    def test_global_singleton(self):
        """Test that get_static_analyzer returns singleton."""
        analyzer1 = get_static_analyzer()
        analyzer2 = get_static_analyzer()
        assert analyzer1 is analyzer2
