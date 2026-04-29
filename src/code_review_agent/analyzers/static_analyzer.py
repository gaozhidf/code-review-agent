"""Static code analysis tools integration."""

import subprocess
import json
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass
from ..models import ReviewFinding, Severity


@dataclass
class ToolResult:
    """Result from a static analysis tool."""
    tool: str
    file_path: str
    line: int
    column: int
    rule_id: str
    message: str
    severity: str  # error, warning, info


# Extension to tool mapping
LANGUAGE_TOOLS: Dict[str, Dict[str, List[str]]] = {
    "python": {
        "ruff": ["ruff", "check", "--output-format=json", "--select=ALL"],
        "bandit": ["bandit", "-f", "json"],
    },
    "javascript": {
        "eslint": ["eslint", "--format=json"],
    },
    "typescript": {
        "eslint": ["eslint", "--format=json"],
    },
}

# Rule ID to severity mapping
RULE_SEVERITY_MAP: Dict[str, Dict[str, Severity]] = {
    "ruff": {
        "F": Severity.CRITICAL,  # Pyflakes
        "E": Severity.MAJOR,     # Errors
        "W": Severity.MINOR,     # Warnings
        "C": Severity.MAJOR,      # Complexity
        "SIM": Severity.MAJOR,    # Simplicity
        "B": Severity.MINOR,      # Bugbear
        "A": Severity.MINOR,      # Aerugosa
        "PLC": Severity.MAJOR,    # Pylint conventions
        "PIE": Severity.MINOR,    # PIE
        "RET": Severity.MAJOR,    # Return
    },
    "bandit": {
        "HIGH": Severity.CRITICAL,
        "MEDIUM": Severity.MAJOR,
        "LOW": Severity.MINOR,
    },
    "eslint": {
        "error": Severity.MAJOR,
        "warn": Severity.MINOR,
    },
}


class StaticAnalyzer:
    """Wrapper for static code analysis tools."""

    def __init__(self):
        self.available_tools: Dict[str, str] = {}
        self._detect_available_tools()

    def _detect_available_tools(self) -> None:
        """Detect which static analysis tools are available."""
        tools = ["ruff", "bandit", "eslint"]
        for tool in tools:
            try:
                result = subprocess.run(
                    ["which", tool],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.available_tools[tool] = result.stdout.strip()
            except (subprocess.TimeoutExpired, Exception):
                pass

    def is_tool_available(self, tool: str) -> bool:
        """Check if a tool is available."""
        return tool in self.available_tools

    def analyze_file(self, file_path: str, content: str) -> List[ToolResult]:
        """Analyze a single file with available static tools."""
        results = []
        ext = Path(file_path).suffix.lower()

        # Determine language from extension
        lang = self._get_language(ext)
        if not lang:
            return results

        # Get tools for this language
        tools_config = LANGUAGE_TOOLS.get(lang, {})

        for tool_name, cmd in tools_config.items():
            if not self.is_tool_available(tool_name):
                continue

            result = self._run_tool(tool_name, cmd, file_path, content)
            if result:
                results.extend(result)

        return results

    def _get_language(self, ext: str) -> Optional[str]:
        """Get language from file extension."""
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
        }
        return lang_map.get(ext)

    def _run_tool(
        self,
        tool: str,
        cmd: List[str],
        file_path: str,
        content: str
    ) -> List[ToolResult]:
        """Run a static analysis tool."""
        try:
            # For ruff, we can use stdin or a temp file
            if tool == "ruff":
                return self._run_ruff(cmd, file_path, content)
            elif tool == "bandit":
                return self._run_bandit(file_path)
            elif tool == "eslint":
                return self._run_eslint(cmd, file_path)

        except Exception as e:
            # Log error but don't fail
            import logging
            logging.warning(f"Static analysis tool {tool} failed: {e}")

        return []

    def _run_ruff(self, cmd: List[str], file_path: str, content: str) -> List[ToolResult]:
        """Run ruff linter."""
        results = []
        try:
            # Write content to temp file for ruff
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix=Path(file_path).suffix,
                delete=False
            ) as f:
                f.write(content)
                temp_path = f.name

            full_cmd = cmd + [temp_path]
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            import os
            os.unlink(temp_path)

            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        for warning in item.get("warnings", []):
                            rule_prefix = warning.get("code", "")[0] if warning.get("code") else "W"
                            results.append(ToolResult(
                                tool="ruff",
                                file_path=file_path,
                                line=warning.get("location", {}).get("row", 1),
                                column=warning.get("location", {}).get("column", 1),
                                rule_id=warning.get("code", "UNK"),
                                message=warning.get("message", ""),
                                severity=warning.get("severity", "warning"),
                            ))
                except json.JSONDecodeError:
                    # Fallback: parse line by line
                    for line in result.stdout.split("\n"):
                        if ":" in line and "src" in line:
                            parts = line.split(":")
                            if len(parts) >= 4:
                                results.append(ToolResult(
                                    tool="ruff",
                                    file_path=file_path,
                                    line=int(parts[1]) if parts[1].isdigit() else 1,
                                    column=1,
                                    rule_id="LINT",
                                    message=":".join(parts[2:]).strip(),
                                    severity="warning",
                                ))
        except Exception:
            pass

        return results

    def _run_bandit(self, file_path: str) -> List[ToolResult]:
        """Run bandit security checker."""
        results = []
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", file_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for issue in data.get("results", []):
                    severity = issue.get("issue_severity", "LOW").upper()
                    severity_map = {"HIGH": "error", "MEDIUM": "warning", "LOW": "info"}

                    results.append(ToolResult(
                        tool="bandit",
                        file_path=file_path,
                        line=issue.get("line_number", 1),
                        column=1,
                        rule_id=issue.get("issue_id", "B001"),
                        message=issue.get("issue_text", ""),
                        severity=severity_map.get(severity, "info"),
                    ))
        except Exception:
            pass

        return results

    def _run_eslint(self, cmd: List[str], file_path: str) -> List[ToolResult]:
        """Run eslint."""
        results = []
        try:
            full_cmd = cmd + [file_path]
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        for item in data:
                            for msg in item.get("messages", []):
                                results.append(ToolResult(
                                    tool="eslint",
                                    file_path=file_path,
                                    line=msg.get("line", 1),
                                    column=msg.get("column", 1),
                                    rule_id=msg.get("ruleId", "UNKNOWN"),
                                    message=msg.get("message", ""),
                                    severity=msg.get("severity", 1),
                                ))
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

        return results

    def convert_to_findings(self, tool_results: List[ToolResult]) -> List[ReviewFinding]:
        """Convert tool results to ReviewFinding format."""
        findings = []

        for result in tool_results:
            # Map tool severity to our Severity enum
            if result.tool == "ruff":
                prefix = result.rule_id[0] if result.rule_id else "W"
                severity = RULE_SEVERITY_MAP.get("ruff", {}).get(prefix, Severity.MINOR)
            elif result.tool == "bandit":
                severity = Severity.CRITICAL if result.severity == "error" else \
                          Severity.MAJOR if result.severity == "warning" else Severity.MINOR
            elif result.tool == "eslint":
                severity = Severity.MAJOR if result.severity in [1, "warn"] else Severity.MINOR
            else:
                severity = Severity.MINOR

            findings.append(ReviewFinding(
                title=f"[{result.tool.upper()}] {result.rule_id}",
                description=result.message,
                severity=severity,
                category=f"static-{result.tool}",
                file_path=result.file_path,
                line_start=result.line,
                line_end=result.line,
                suggestion=f"Fix reported by {result.tool}: {result.rule_id}",
            ))

        return findings


# Global instance
_static_analyzer: Optional[StaticAnalyzer] = None


def get_static_analyzer() -> StaticAnalyzer:
    """Get or create the global static analyzer instance."""
    global _static_analyzer
    if _static_analyzer is None:
        _static_analyzer = StaticAnalyzer()
    return _static_analyzer
