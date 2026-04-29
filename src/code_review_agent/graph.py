from typing import TypedDict, List, Optional, Annotated
from loguru import logger
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from code_review_agent.models import CodeChange, ReviewFinding, PRSummary, CodeReviewResult, Severity
from code_review_agent.checkers import UniversalChecker, BackendChecker, FrontendChecker
from code_review_agent.llm_config import LLMConfig
from code_review_agent.analyzers import get_static_analyzer, get_pattern_analyzer
from langchain_core.prompts import ChatPromptTemplate
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures


class ReviewState(TypedDict):
    pr_id: str
    repository: str
    changes: List[CodeChange]
    universal_findings: Annotated[List[ReviewFinding], "extend"]
    backend_findings: Annotated[List[ReviewFinding], "extend"]
    frontend_findings: Annotated[List[ReviewFinding], "extend"]
    static_findings: Annotated[List[ReviewFinding], "extend"]
    impact_findings: Annotated[List[ReviewFinding], "extend"]
    summary: Optional[PRSummary]
    completed: bool


class CodeReviewGraph:
    """LangGraph based code review workflow with parallel execution."""

    def __init__(self, max_workers: int = 10, enable_static_analysis: bool = True,
                 enable_impact_analysis: bool = True):
        logger.info("Initializing CodeReviewGraph (parallel mode)...")
        self.universal_checker = UniversalChecker()
        self.backend_checker = BackendChecker()
        self.frontend_checker = FrontendChecker()
        self.llm = LLMConfig.get_default_llm()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.enable_static_analysis = enable_static_analysis
        self.enable_impact_analysis = enable_impact_analysis

        # Initialize analyzers
        if enable_static_analysis:
            self.static_analyzer = get_static_analyzer()
            logger.info(f"[Static] Available tools: {list(self.static_analyzer.available_tools.keys())}")
        else:
            self.static_analyzer = None

        if enable_impact_analysis:
            self.pattern_analyzer = get_pattern_analyzer()
        else:
            self.pattern_analyzer = None

        self.graph = self._build_graph()
        logger.success("CodeReviewGraph initialized (parallel mode)")

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ReviewState)

        # Add nodes
        workflow.add_node("check_all", self._check_all_parallel)
        workflow.add_node("run_static_analysis", self._run_static_analysis)
        workflow.add_node("run_impact_analysis", self._run_impact_analysis)
        workflow.add_node("generate_summary", self._generate_summary)

        # Sequential flow
        workflow.add_edge("check_all", "run_static_analysis")
        workflow.add_edge("run_static_analysis", "run_impact_analysis")
        workflow.add_edge("run_impact_analysis", "generate_summary")
        workflow.add_edge("generate_summary", END)

        workflow.set_entry_point("check_all")

        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)

    def _check_all_parallel(self, state: ReviewState) -> ReviewState:
        """Run all checkers in parallel using ThreadPoolExecutor."""
        changes = [c for c in state["changes"] if not c.is_deleted]
        num_files = len(changes)

        logger.info(f"[Check All] Starting parallel check for {num_files} files with 3 checkers...")

        def run_checker(checker, changes):
            """Run a single checker on all files."""
            return checker.check_batch(changes)

        # Run all 3 checkers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            universal_future = pool.submit(run_checker, self.universal_checker, changes)
            backend_future = pool.submit(run_checker, self.backend_checker, changes)
            frontend_future = pool.submit(run_checker, self.frontend_checker, changes)

            # Wait for all to complete
            universal_findings = universal_future.result()
            backend_findings = backend_future.result()
            frontend_findings = frontend_future.result()

        logger.success(f"[Check All] Completed - Universal: {len(universal_findings)}, "
                       f"Backend: {len(backend_findings)}, Frontend: {len(frontend_findings)}")

        return {
            "universal_findings": universal_findings,
            "backend_findings": backend_findings,
            "frontend_findings": frontend_findings,
        }

    def _run_static_analysis(self, state: ReviewState) -> ReviewState:
        """Run static analysis tools on changed files."""
        if not self.enable_static_analysis or not self.static_analyzer:
            logger.info("[Static] Static analysis disabled, skipping...")
            return {"static_findings": []}

        changes = [c for c in state["changes"] if not c.is_deleted]
        logger.info(f"[Static] Running static analysis on {len(changes)} files...")

        all_findings = []
        for change in changes:
            # For static analysis, we need the full file content
            # In a real implementation, we would fetch the full file from the repo
            # For now, we analyze the diff as content
            tool_results = self.static_analyzer.analyze_file(change.file_path, change.diff)
            findings = self.static_analyzer.convert_to_findings(tool_results)
            all_findings.extend(findings)

        logger.success(f"[Static] Found {len(all_findings)} issues from static analysis")
        return {"static_findings": all_findings}

    def _run_impact_analysis(self, state: ReviewState) -> ReviewState:
        """Run impact analysis on changed files."""
        if not self.enable_impact_analysis or not self.pattern_analyzer:
            logger.info("[Impact] Impact analysis disabled, skipping...")
            return {"impact_findings": []}

        changes = state["changes"]
        logger.info(f"[Impact] Running impact analysis on {len(changes)} files...")

        all_findings = []
        for change in changes:
            impacts = self.pattern_analyzer.analyze(change)
            findings = self.pattern_analyzer.convert_to_findings(impacts)
            all_findings.extend(findings)

        logger.success(f"[Impact] Found {len(all_findings)} potential impacts")
        return {"impact_findings": all_findings}

    def _generate_summary(self, state: ReviewState) -> ReviewState:
        """Generate summary using LLM."""
        logger.info("[Summary] Generating code review summary with LLM...")

        changes = state["changes"]

        # Combine findings from all sources
        universal = state.get("universal_findings", [])
        backend = state.get("backend_findings", [])
        frontend = state.get("frontend_findings", [])
        static = state.get("static_findings", [])
        impact = state.get("impact_findings", [])
        all_findings = universal + backend + frontend + static + impact

        # Count findings by severity
        counts: dict = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 0,
            Severity.MINOR: 0,
        }
        for f in all_findings:
            counts[f.severity] += 1

        # Determine overall risk
        if counts[Severity.CRITICAL] > 0:
            overall_risk = Severity.CRITICAL
        elif counts[Severity.MAJOR] > 0:
            overall_risk = Severity.MAJOR
        else:
            overall_risk = Severity.MINOR

        logger.debug(f"[Summary] Finding counts - Critical: {counts[Severity.CRITICAL]}, "
                     f"Major: {counts[Severity.MAJOR]}, Minor: {counts[Severity.MINOR]}")

        # Generate summary with LLM
        prompt = ChatPromptTemplate.from_template("""
Generate a summary of this code review.

PR has {total_changes} changed files with {total_findings} total findings:
|- Critical: {critical_count}
|- Major: {major_count}
|- Minor: {minor_count}

Breakdown:
|- LLM (Universal): {llm_count}
|- LLM (Backend): {backend_count}
|- LLM (Frontend): {frontend_count}
|- Static Analysis: {static_count}
|- Impact Analysis: {impact_count}

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
|- <concern 1>
|- <concern 2>
...
        """)

        findings_bullets = [f"- [{f.severity}] {f.category}: {f.title}" for f in all_findings]
        files_list = [f"- {c.file_path}" for c in changes]

        logger.debug("[Summary] Invoking LLM to generate summary...")

        response = self.llm.invoke(prompt.format(
            total_changes=len(changes),
            total_findings=len(all_findings),
            critical_count=counts[Severity.CRITICAL],
            major_count=counts[Severity.MAJOR],
            minor_count=counts[Severity.MINOR],
            llm_count=len(universal),
            backend_count=len(backend),
            frontend_count=len(frontend),
            static_count=len(static),
            impact_count=len(impact),
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

        logger.success("[Summary] Summary generation completed")
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
        import uuid

        initial_state: ReviewState = {
            "pr_id": pr_id,
            "repository": repository,
            "changes": changes,
            "universal_findings": [],
            "backend_findings": [],
            "frontend_findings": [],
            "static_findings": [],
            "impact_findings": [],
            "summary": None,
            "completed": False
        }

        config = {"configurable": {"thread_id": f"pr-{pr_id}-{uuid.uuid4().hex[:8]}"}}
        result = self.graph.invoke(initial_state, config=config)

        # Combine all findings
        all_findings = (
            result.get("universal_findings", []) +
            result.get("backend_findings", []) +
            result.get("frontend_findings", []) +
            result.get("static_findings", []) +
            result.get("impact_findings", [])
        )

        return CodeReviewResult(
            pr_id=result["pr_id"],
            repository=result["repository"],
            changes=changes,
            findings=all_findings,
            summary=result["summary"]
        )
