import os
from typing import List, Dict, Optional
from azure.devops.connection import Connection
from azure.devops.v7_1.git.models import GitPullRequestCommentThread, Comment
from azure.devops.v7_1.git.git_client import GitClient
from msrest.authentication import BasicAuthentication
from code_review_agent.models import CodeChange, CodeReviewResult, ReviewFinding, Severity


class AzureDevOpsClient:
    """Azure DevOps integration for posting code review comments."""
    
    def __init__(self):
        org_url = os.getenv("AZURE_DEVOPS_ORG_URL")
        pat = os.getenv("AZURE_DEVOPS_PAT") or os.getenv("AZURE_DEVOOS_PAT")  # fallback for typo
        
        if not org_url or not pat:
            raise ValueError("AZURE_DEVOPS_ORG_URL and AZURE_DEVOPS_PAT must be set in environment")
        
        credentials = BasicAuthentication("", pat)
        self.connection = Connection(org_url, credentials)
        self.git_client: GitClient = self.connection.clients.get_git_client()
    
    def get_pull_request_changes(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int
    ) -> List[CodeChange]:
        """Fetch all changes from a pull request."""
        pr = self.git_client.get_pull_request(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        iterations = self.git_client.get_pull_request_iterations(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            project=project
        )
        latest_iter = iterations[-1].id
        changes = self.git_client.get_pull_request_iteration_changes(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            iteration_id=latest_iter,
        )
        
        code_changes = []
        for change in changes.change_entries:
            # In azure-devops 7.1.0b4, item is in additional_properties
            item = None
            if hasattr(change, 'item') and change.item:
                item = change.item
            elif 'item' in change.additional_properties:
                item = change.additional_properties['item']
            
            if item:
                # Get change_type
                change_type = None
                if hasattr(change, 'change_type'):
                    change_type = change.change_type
                elif 'changeType' in change.additional_properties:
                    change_type = change.additional_properties['changeType']
                
                # Get the diff content
                diff = self._get_diff(project, repository_id, pull_request_id, change, item)
                code_changes.append(CodeChange(
                    file_path=item['path'] if isinstance(item, dict) else item.path,
                    diff=diff,
                    language=self._detect_language(item['path'] if isinstance(item, dict) else item.path),
                    is_new=change_type == "add",
                    is_deleted=change_type == "delete"
                ))
        
        self._change_map = {change.file_path: change for change in code_changes}
        return code_changes
    
    def post_review_comments(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        result: CodeReviewResult
    ) -> None:
        """Post inline review comments and summary to Azure DevOps PR."""
        # Post inline comments when we have valid line info
        for finding in result.findings:
            if finding.line_start:
                self._post_inline_comment(
                    project=project,
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    finding=finding
                )
        
        # Always post the overall summary as a top-level comment
        self._post_summary_comment(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            result=result
        )
    
    def _detect_language(self, path: str) -> str:
        """Detect programming language from file path."""
        ext = path.split(".")[-1].lower() if "." in path else ""
        language_map = {
            "py": "Python",
            "js": "JavaScript",
            "jsx": "React JSX",
            "ts": "TypeScript",
            "tsx": "React TSX",
            "java": "Java",
            "go": "Go",
            "rb": "Ruby",
            "php": "PHP",
            "cs": "C#",
            "cpp": "C++",
            "c": "C",
            "html": "HTML",
            "css": "CSS",
            "scss": "SCSS",
            "vue": "Vue",
            "json": "JSON",
            "md": "Markdown",
            "sql": "SQL",
        }
        return language_map.get(ext, "Unknown")
    
    def _get_diff(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        change,
        item
    ) -> str:
        """Get diff content for a specific change."""
        if hasattr(change, 'diff') and change.diff:
            return change.diff
        
        # Fetch diff content if not provided
        try:
            object_id = item['objectId'] if isinstance(item, dict) else item.object_id
            diff_content = self.git_client.get_pull_request_file_diff(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                file_id=object_id
            )
            if diff_content and hasattr(diff_content, 'diff'):
                return diff_content.diff
        except Exception:
            pass
        
        return ""
    
    def _post_inline_comment(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        finding: ReviewFinding
    ) -> None:
        """Post a single inline comment thread."""
        comment_text = self._format_finding_comment(finding)
        
        thread = GitPullRequestCommentThread()
        thread.comments = [Comment(content=comment_text)]
        
        # Map diff line to PR comment coordinates
        # Azure uses 1-based line numbers on the right side (new version)
        line_end = finding.line_end or finding.line_start
        
        thread.thread_context = {
            "rightFileStart": {
                "line": finding.line_start,
                "offset": 1
            },
            "rightFileEnd": {
                "line": line_end,
                "offset": 1
            }
        }
        
        # In azure-devops 7.1.0b4, method name is create_thread
        if hasattr(self.git_client, 'create_pull_request_thread'):
            self.git_client.create_pull_request_thread(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                git_pull_request_comment_thread=thread
            )
        elif hasattr(self.git_client, 'create_thread'):
            self.git_client.create_thread(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                comment_thread=thread
            )
    
    def _post_summary_comment(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        result: CodeReviewResult
    ) -> None:
        """Post the overall summary as a top-level PR comment."""
        summary_text = self._format_summary(result)
        
        thread = GitPullRequestCommentThread()
        thread.comments = [Comment(content=summary_text)]
        # No context = top-level comment
        
        # In azure-devops 7.1.0b4, method name is create_thread
        if hasattr(self.git_client, 'create_pull_request_thread'):
            self.git_client.create_pull_request_thread(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                git_pull_request_comment_thread=thread
            )
        elif hasattr(self.git_client, 'create_thread'):
            self.git_client.create_thread(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                comment_thread=thread
            )
    
    def _format_finding_comment(self, finding: ReviewFinding) -> str:
        """Format a finding for Azure DevOps comment."""
        severity_emoji = {
            Severity.CRITICAL: "🔴 **CRITICAL**",
            Severity.MAJOR: "🟡 **MAJOR**",
            Severity.MINOR: "🔵 **MINOR**",
        }
        
        parts = [
            f"{severity_emoji[finding.severity]} [{finding.category}] {finding.title}",
            "",
            finding.description,
        ]
        
        if finding.suggestion:
            parts.extend(["", "**Suggestion:**", finding.suggestion])
        
        return "\n".join(parts)
    
    def _format_summary(self, result: CodeReviewResult) -> str:
        """Format overall review summary."""
        severity_order = [Severity.CRITICAL, Severity.MAJOR, Severity.MINOR]
        counts = result.summary.total_findings
        
        parts = [
            "# 🤖 AI Code Review Summary",
            "",
            f"**Overall Risk**: {result.summary.overall_risk.upper()}",
            "",
            "## Findings by Severity",
            "",
        ]
        
        for sev in severity_order:
            count = counts.get(sev, 0)
            parts.append(f"- {sev.upper()}: {count}")
        
        if result.summary.key_concerns:
            parts.extend([
                "",
                "## Key Concerns",
                "",
                *[f"- {concern}" for concern in result.summary.key_concerns]
            ])
        
        parts.extend([
            "",
            result.summary.summary,
            "",
            "---",
            "_This is an automated first-pass review. Human review is still required._"
        ])
        
        return "\n".join(parts)
