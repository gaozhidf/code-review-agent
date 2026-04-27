from typing import List
from langchain_core.prompts import ChatPromptTemplate
from code_review_agent.models import CodeChange, ReviewFinding, Severity
from code_review_agent.llm_config import LLMConfig
from code_review_agent.standards import TeamStandardsManager
from .base_checker import BaseChecker


FRONTEND_REVIEW_PROMPT = """You are an expert frontend code reviewer reviewing this change.
Analyze the following frontend code diff specifically for:
1. **State & Async**: Race conditions, unnecessary re-renders, improper async handling
2. **Accessibility**: Missing semantic HTML, incorrect ARIA usage, lack of keyboard navigation support
3. **Performance**: Large bundle size impacts, unnecessary re-renders, unoptimized assets
4. **Client Security**: XSS vulnerabilities, unsafe DOM manipulation, unsafe user input handling
{team_standards}
For each issue found, output it in the following format:
SEVERITY: critical|major|minor
TITLE: Short title
DESCRIPTION: Detailed explanation of the issue and why it matters
LINE_START: starting line number (if known)
LINE_END: ending line number (if known)
SUGGESTION: Concrete suggestion for improvement

If no issues found, just say "No issues found".

File: {file_path}
Language: {language}

Diff:
```diff
{diff}
```

Now provide your analysis:"""


class FrontendChecker(BaseChecker):
    """Checks for frontend-specific code issues."""
    
    category = "frontend"
    
    def __init__(self):
        self.llm = LLMConfig.get_default_llm()
        self.standards = TeamStandardsManager()
    
    def check(self, change: CodeChange) -> List[ReviewFinding]:
        # Identify frontend files
        frontend_extensions = {
            ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
            ".html", ".css", ".scss", ".less", ".astro"
        }
        ext = "." + change.file_path.split(".")[-1].lower() if "." in change.file_path else ""
        if ext not in frontend_extensions:
            return []

        prompt = ChatPromptTemplate.from_template(FRONTEND_REVIEW_PROMPT)
        chain = prompt | self.llm

        response = chain.invoke({
            "file_path": change.file_path,
            "language": change.language or ext.lstrip("."),
            "diff": change.diff,
            "team_standards": self.standards.get_standards_prompt()
        })

        findings = self._parse_response(response.content, change.file_path)
        # Apply team severity overrides
        findings = [self.standards.override_severity(f) for f in findings]
        return findings

    async def acheck(self, change: CodeChange) -> List[ReviewFinding]:
        """Async version of check using ainvoke."""
        frontend_extensions = {
            ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
            ".html", ".css", ".scss", ".less", ".astro"
        }
        ext = "." + change.file_path.split(".")[-1].lower() if "." in change.file_path else ""
        if ext not in frontend_extensions:
            return []

        prompt = ChatPromptTemplate.from_template(FRONTEND_REVIEW_PROMPT)
        chain = prompt | self.llm

        response = await chain.ainvoke({
            "file_path": change.file_path,
            "language": change.language or ext.lstrip("."),
            "diff": change.diff,
            "team_standards": self.standards.get_standards_prompt()
        })

        findings = self._parse_response(response.content, change.file_path)
        findings = [self.standards.override_severity(f) for f in findings]
        return findings
    
    def _parse_response(self, content: str, file_path: str) -> List[ReviewFinding]:
        findings = []
        current: dict = {}
        
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            if line.lower() == "no issues found":
                break
            
            if line.startswith("SEVERITY:"):
                if current:
                    self._add_finding(findings, current, file_path)
                current = {}
                current["severity"] = line.split(":", 1)[1].strip()
            elif line.startswith("TITLE:"):
                current["title"] = line.split(":", 1)[1].strip()
            elif line.startswith("DESCRIPTION:"):
                current["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("LINE_START:"):
                val = line.split(":", 1)[1].strip()
                current["line_start"] = int(val) if val.isdigit() else None
            elif line.startswith("LINE_END:"):
                val = line.split(":", 1)[1].strip()
                current["line_end"] = int(val) if val.isdigit() else None
            elif line.startswith("SUGGESTION:"):
                current["suggestion"] = line.split(":", 1)[1].strip()
            elif "description" in current:
                current["description"] += " " + line
        
        if current and "title" in current:
            self._add_finding(findings, current, file_path)

        return findings

    def _add_finding(self, findings: List[ReviewFinding], data: dict, file_path: str) -> None:
        try:
            severity = Severity(data.get("severity", "minor"))
        except ValueError:
            severity = Severity.MINOR

        findings.append(ReviewFinding(
            title=data["title"],
            description=data["description"],
            severity=severity,
            category=self.category,
            file_path=file_path,
            line_start=data.get("line_start"),
            line_end=data.get("line_end"),
            suggestion=data.get("suggestion"),
        ))
