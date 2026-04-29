"""Impact analysis for code changes."""

import ast
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from ..models import ReviewFinding, Severity, CodeChange


class ImpactType(Enum):
    """Types of impact analysis."""
    CALLER_AFFECTED = "caller_affected"      # Called function changed
    API_CONTRACT = "api_contract"            # API signature changed
    DEPENDENCY = "dependency"               # Dependency changed
    EXPORT_AFFECTED = "export_affected"      # Exported item changed


@dataclass
class ImpactFinding:
    """Represents an impact analysis finding."""
    impact_type: ImpactType
    source_file: str
    source_line: int
    target_file: str
    description: str
    severity: Severity
    suggestion: str


@dataclass
class FunctionDef:
    """Represents a function definition."""
    name: str
    file_path: str
    line: int
    end_line: int
    args: List[str]
    decorators: List[str]
    is_async: bool
    is_method: bool = False
    is_public: bool = True  # Starts with _ or __ is private

    @property
    def is_exported(self) -> bool:
        """Check if function is exported (public API)."""
        return self.is_public and not self.name.startswith("__")


@dataclass
class CallReference:
    """Represents a function call."""
    caller: str
    callee: str
    file_path: str
    line: int
    is_from_import: bool = False
    import_module: Optional[str] = None


class ImpactAnalyzer:
    """Analyze impact of code changes on downstream functionality."""

    def __init__(self):
        self.function_defs: Dict[str, List[FunctionDef]] = {}  # file -> functions
        self.call_refs: List[CallReference] = []
        self.export_map: Dict[str, Set[str]] = {}  # module -> exported names

    def analyze(self, changes: List[CodeChange]) -> List[ImpactFinding]:
        """Analyze impact of code changes."""
        findings = []

        # First pass: collect all function definitions
        for change in changes:
            if change.is_deleted:
                continue
            self._extract_functions(change)

        # Second pass: find call references and analyze impacts
        for change in changes:
            if change.is_deleted:
                # Analyze deleted functions
                impacts = self._analyze_deletion(change)
                findings.extend(impacts)
            else:
                # Analyze modifications
                impacts = self._analyze_modification(change)
                findings.extend(impacts)

        return findings

    def _extract_functions(self, change: CodeChange) -> None:
        """Extract function definitions from a code change."""
        if change.language and change.language.lower() not in ["python", "py"]:
            return

        try:
            tree = ast.parse(change.diff)
        except SyntaxError:
            return

        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func = FunctionDef(
                    name=node.name,
                    file_path=change.file_path,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    args=[arg.arg for arg in node.args.args],
                    decorators=[self._get_decorator_name(d) for d in node.decorator_list],
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                    is_method=self._is_method(node),
                    is_public=not node.name.startswith("_"),
                )
                funcs.append(func)

        if funcs:
            self.function_defs[change.file_path] = funcs

    def _is_method(self, node: ast.FunctionDef) -> bool:
        """Check if function is a class method."""
        # Simple heuristic: function inside a ClassDef parent
        # In real implementation, would need parent tracking
        return False

    def _get_decorator_name(self, node: ast.expr) -> str:
        """Get decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return "unknown"

    def _analyze_deletion(self, change: CodeChange) -> List[ImpactFinding]:
        """Analyze impact of a deleted function."""
        findings = []

        # Find all callers of the deleted function
        deleted_name = self._extract_deleted_function_name(change)
        if not deleted_name:
            return findings

        for ref in self.call_refs:
            if ref.callee == deleted_name:
                findings.append(ImpactFinding(
                    impact_type=ImpactType.CALLER_AFFECTED,
                    source_file=ref.file_path,
                    source_line=ref.line,
                    target_file=change.file_path,
                    description=f"Function '{deleted_name}' was deleted. "
                               f"Caller in '{ref.file_path}' line {ref.line} will break.",
                    severity=Severity.CRITICAL,
                    suggestion=f"Implement '{deleted_name}' or update caller in '{ref.file_path}'",
                ))

        return findings

    def _analyze_modification(self, change: CodeChange) -> List[ImpactFinding]:
        """Analyze impact of a modified function."""
        findings = []

        # Check for signature changes (not implemented in basic version)
        # This would require comparing old vs new function definitions

        # Check for decorator changes on public APIs
        funcs = self.function_defs.get(change.file_path, [])
        for func in funcs:
            if func.is_exported and func.decorators:
                critical_decorators = ["@property", "@cached_property", "@lru_cache"]
                for dec in func.decorators:
                    if dec in critical_decorators:
                        findings.append(ImpactFinding(
                            impact_type=ImpactType.API_CONTRACT,
                            source_file=change.file_path,
                            source_line=func.line,
                            target_file=change.file_path,
                            description=f"Public function '{func.name}' has critical decorator '{dec}'",
                            severity=Severity.MAJOR,
                            suggestion=f"Verify caching behavior change doesn't break callers",
                        ))

        return findings

    def _extract_deleted_function_name(self, change: CodeChange) -> Optional[str]:
        """Extract function name from a deletion diff."""
        # Look for patterns like "-    def function_name("
        pattern = r'^-.*def\s+(\w+)\s*\('
        for line in change.diff.split("\n"):
            match = re.match(pattern, line)
            if match:
                return match.group(1)
        return None

    def convert_to_findings(self, impacts: List[ImpactFinding]) -> List[ReviewFinding]:
        """Convert impact findings to ReviewFinding format."""
        return [
            ReviewFinding(
                title=f"[Impact] {impact.impact_type.value}: {impact.description[:50]}...",
                description=impact.description,
                severity=impact.severity,
                category="impact-analysis",
                file_path=impact.target_file,
                line_start=impact.source_line,
                suggestion=impact.suggestion,
            )
            for impact in impacts
        ]


# Pattern-based analyzer for non-Python files
class PatternImpactAnalyzer:
    """Simple pattern-based impact analyzer for any language."""

    # Common patterns that indicate API/interface changes
    SIGNATURE_PATTERNS = [
        r"export\s+(?:async\s+)?function\s+(\w+)",  # TS/JS export
        r"export\s+const\s+(\w+)\s*=",  # TS/JS const export
        r"export\s+class\s+(\w+)",  # TS/JS class export
        r"export\s+(?:async\s+)?function\s+(\w+)",  # JS export
        r"def\s+(\w+)\s*\([^)]*\)\s*->",  # Python with return type
        r"public\s+(?:static\s+)?(?:async\s+)?(\w+)\s*\(",  # Java/C#
    ]

    # Patterns indicating breaking changes
    BREAKING_PATTERNS = [
        (r"-\s*\w+\s*\([^)]*\)\s*{?\s*$", Severity.MAJOR),  # Removed function
        (r"-\s*const\s+\w+\s*=", Severity.MAJOR),  # Removed const
        (r"-\s*class\s+\w+", Severity.CRITICAL),  # Removed class
    ]

    def analyze(self, change: CodeChange) -> List[ImpactFinding]:
        """Analyze patterns in a code change."""
        findings = []

        for pattern, severity in self.BREAKING_PATTERNS:
            for i, line in enumerate(change.diff.split("\n"), 1):
                if re.match(pattern, line):
                    findings.append(ImpactFinding(
                        impact_type=ImpactType.API_CONTRACT,
                        source_file=change.file_path,
                        source_line=i,
                        target_file=change.file_path,
                        description=f"Potential breaking change detected: {line.strip()}",
                        severity=severity,
                        suggestion="Review this change for downstream impact",
                    ))

        return findings

    def convert_to_findings(self, impacts: List[ImpactFinding]) -> List[ReviewFinding]:
        """Convert impact findings to ReviewFinding format."""
        return [
            ReviewFinding(
                title=f"[Impact] {impact.impact_type.value}",
                description=impact.description,
                severity=impact.severity,
                category="impact-analysis",
                file_path=impact.target_file,
                line_start=impact.source_line,
                suggestion=impact.suggestion,
            )
            for impact in impacts
        ]


# Global instances
_impact_analyzer: Optional[ImpactAnalyzer] = None
_pattern_analyzer: Optional[PatternImpactAnalyzer] = None


def get_impact_analyzer() -> ImpactAnalyzer:
    """Get or create the global impact analyzer instance."""
    global _impact_analyzer
    if _impact_analyzer is None:
        _impact_analyzer = ImpactAnalyzer()
    return _impact_analyzer


def get_pattern_analyzer() -> PatternImpactAnalyzer:
    """Get or create the global pattern analyzer instance."""
    global _pattern_analyzer
    if _pattern_analyzer is None:
        _pattern_analyzer = PatternImpactAnalyzer()
    return _pattern_analyzer
