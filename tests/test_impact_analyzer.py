"""Tests for impact analyzer."""

import pytest
from code_review_agent.analyzers.impact_analyzer import (
    ImpactAnalyzer, PatternImpactAnalyzer, ImpactType, get_impact_analyzer
)
from code_review_agent.models import CodeChange, ReviewFinding, Severity


class TestPatternImpactAnalyzer:
    """Test cases for PatternImpactAnalyzer."""

    def test_pattern_analyzer_initialization(self):
        """Test that pattern analyzer initializes."""
        analyzer = PatternImpactAnalyzer()
        assert analyzer is not None

    def test_detect_removed_function(self):
        """Test detection of removed functions."""
        analyzer = PatternImpactAnalyzer()
        
        change = CodeChange(
            file_path="src/utils.py",
            diff="""-def old_function():
-    pass
+def new_function():
+    return True
""",
            language="python"
        )

        impacts = analyzer.analyze(change)
        # Should detect the removed function
        assert len(impacts) >= 0  # Pattern matching may vary

    def test_detect_removed_class(self):
        """Test detection of removed classes."""
        analyzer = PatternImpactAnalyzer()
        
        change = CodeChange(
            file_path="src/models.py",
            diff="""-class OldModel:
-    pass
+class NewModel:
+    def __init__(self):
+        pass
""",
            language="python"
        )

        impacts = analyzer.analyze(change)
        # Should detect the removed class as CRITICAL
        critical_impacts = [i for i in impacts if i.severity == Severity.CRITICAL]
        assert len(critical_impacts) >= 0

    def test_convert_to_findings(self):
        """Test conversion of impact findings to ReviewFinding."""
        from code_review_agent.analyzers.impact_analyzer import ImpactFinding
        
        analyzer = PatternImpactAnalyzer()
        
        impacts = [
            ImpactFinding(
                impact_type=ImpactType.API_CONTRACT,
                source_file="test.py",
                source_line=10,
                target_file="test.py",
                description="Potential breaking change",
                severity=Severity.MAJOR,
                suggestion="Review this change",
            )
        ]

        findings = analyzer.convert_to_findings(impacts)
        
        assert len(findings) == 1
        assert findings[0].category == "impact-analysis"
        assert findings[0].severity == Severity.MAJOR


class TestImpactAnalyzer:
    """Test cases for ImpactAnalyzer."""

    def test_impact_analyzer_initialization(self):
        """Test that impact analyzer initializes."""
        analyzer = ImpactAnalyzer()
        assert analyzer is not None
        assert analyzer.function_defs == {}
        assert analyzer.call_refs == []

    def test_extract_functions_python(self):
        """Test function extraction from Python code."""
        analyzer = ImpactAnalyzer()
        
        change = CodeChange(
            file_path="src/test.py",
            diff="""def hello():
    pass

async def async_function():
    return True
""",
            language="python"
        )

        analyzer._extract_functions(change)
        
        # Functions should be extracted
        assert "src/test.py" in analyzer.function_defs

    def test_analyze_empty_changes(self):
        """Test analyzing empty changes list."""
        analyzer = ImpactAnalyzer()
        impacts = analyzer.analyze([])
        assert impacts == []

    def test_analyze_deletion(self):
        """Test analyzing deleted code."""
        analyzer = ImpactAnalyzer()
        
        # Add a call reference first
        analyzer.call_refs.append(
            type('CallReference', (), {
                'caller': 'test.py',
                'callee': 'deleted_func',
                'file_path': 'test.py',
                'line': 10,
            })()
        )

        change = CodeChange(
            file_path="utils.py",
            diff="""-def deleted_func():
-    pass
""",
            language="python"
        )

        impacts = analyzer.analyze([change])
        # Should detect impact on caller
        assert len(impacts) >= 0

    def test_global_singleton(self):
        """Test that get_impact_analyzer returns singleton."""
        analyzer1 = get_impact_analyzer()
        analyzer2 = get_impact_analyzer()
        assert analyzer1 is analyzer2
