from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from code_review_agent.models import CodeChange, ReviewFinding, PRSummary, CodeReviewResult, Severity
from code_review_agent.checkers import UniversalChecker, BackendChecker, FrontendChecker
from code_review_agent.llm_config import LLMConfig
from langchain_core.prompts import ChatPromptTemplate


class ReviewState(TypedDict):
    pr_id: str
    repository: str
    changes: List[CodeChange]
    findings: List[ReviewFinding]
    summary: Optional[PRSummary]
    completed: bool


class CodeReviewGraph:
    """LangGraph based code review workflow."""
    
    def __init__(self):
        self.universal_checker = UniversalChecker()
        self.backend_checker = BackendChecker()
        self.frontend_checker = FrontendChecker()
        self.llm = LLMConfig.get_default_llm()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ReviewState)
        
        # Add nodes
        workflow.add_node("check_universal", self._check_universal)
        workflow.add_node("check_backend", self._check_backend)
        workflow.add_node("check_frontend", self._check_frontend)
        workflow.add_node("generate_summary", self._generate_summary)
        
        # Add edges
        workflow.add_edge("check_universal", "check_backend")
        workflow.add_edge("check_backend", "check_frontend")
        workflow.add_edge("check_frontend", "generate_summary")
        workflow.add_edge("generate_summary", END)
        
        # Set entry point
        workflow.set_entry_point("check_universal")
        
        return workflow.compile()
    
    def _check_universal(self, state: ReviewState) -> ReviewState:
        findings = state.get("findings", [])
        for change in state["changes"]:
            if change.is_deleted:
                continue
            new_findings = self.universal_checker.check(change)
            findings.extend(new_findings)
        return {"findings": findings}
    
    def _check_backend(self, state: ReviewState) -> ReviewState:
        findings = state["findings"]
        for change in state["changes"]:
            if change.is_deleted:
                continue
            new_findings = self.backend_checker.check(change)
            findings.extend(new_findings)
        return {"findings": findings}
    
    def _check_frontend(self, state: ReviewState) -> ReviewState:
        findings = state["findings"]
        for change in state["changes"]:
            if change.is_deleted:
                continue
            new_findings = self.frontend_checker.check(change)
            findings.extend(new_findings)
        return {"findings": findings}
    
    def _generate_summary(self, state: ReviewState) -> ReviewState:
        findings = state["findings"]
        changes = state["changes"]
        
        # Count findings by severity
        counts: dict = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 0,
            Severity.MINOR: 0,
        }
        for f in findings:
            counts[f.severity] += 1
        
        # Determine overall risk
        if counts[Severity.CRITICAL] > 0:
            overall_risk = Severity.CRITICAL
        elif counts[Severity.MAJOR] > 0:
            overall_risk = Severity.MAJOR
        else:
            overall_risk = Severity.MINOR
        
        # Generate summary with LLM
        prompt = ChatPromptTemplate.from_template("""
Generate a summary of this code review.

PR has {total_changes} changed files with {total_findings} total findings:
- Critical: {critical_count}
- Major: {major_count}
- Minor: {minor_count}

List of findings:
{findings_list}

List of changed files:
{files_list}

Write:
1. A 2-3 sentence overall summary
2. A list of 3-5 key concerns (if any) to highlight

Focus on what changed, the impact, and why it matters. Keep it concise.

Format as:
SUMMARY: <overall summary>
KEY_CONCERNS:
- <concern 1>
- <concern 2>
...
        """)
        
        findings_bullets = [f"- [{f.severity}] {f.title}: {f.description}" for f in findings]
        files_list = [f"- {c.file_path}" for c in changes]
        
        response = self.llm.invoke(prompt.format(
            total_changes=len(changes),
            total_findings=len(findings),
            critical_count=counts[Severity.CRITICAL],
            major_count=counts[Severity.MAJOR],
            minor_count=counts[Severity.MINOR],
            findings_list="\n".join(findings_bullets) if findings_bullets else "No findings",
            files_list="\n".join(files_list),
        ))
        
        # Parse response
        summary_text = ""
        key_concerns = []
        in_concerns = False
        
        for line in response.content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("SUMMARY:"):
                summary_text = line.split(":", 1)[1].strip()
                in_concerns = False
            elif line.startswith("KEY_CONCERNS:"):
                in_concerns = True
            elif in_concerns and line.startswith("-"):
                key_concerns.append(line[1:].strip())
        
        summary = PRSummary(
            overall_risk=overall_risk,
            total_findings=counts,
            summary=summary_text,
            key_concerns=key_concerns
        )
        
        return {
            "summary": summary,
            "completed": True
        }
    
    def run(
        self,
        pr_id: str,
        repository: str,
        changes: List[CodeChange]
    ) -> CodeReviewResult:
        """Run the full code review workflow."""
        initial_state: ReviewState = {
            "pr_id": pr_id,
            "repository": repository,
            "changes": changes,
            "findings": [],
            "summary": None,
            "completed": False
        }
        
        result = self.graph.invoke(initial_state)
        
        return CodeReviewResult(
            pr_id=result["pr_id"],
            repository=result["repository"],
            changes=changes,
            findings=result["findings"],
            summary=result["summary"]
        )
