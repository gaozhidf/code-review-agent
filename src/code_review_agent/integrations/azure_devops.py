import os
from typing import List, Dict, Optional
from azure.devops.connection import Connection
from azure.devops.v7_1.git.models import GitPullRequestCommentThread, Comment, GitVersionDescriptor, CommentThreadContext, CommentPosition
from azure.devops.v7_1.git.git_client import GitClient
from msrest.authentication import BasicAuthentication
from loguru import logger
from code_review_agent.models import CodeChange, CodeReviewResult, ReviewFinding, Severity


class AzureDevOpsClient:
    """Azure DevOps integration for posting code review comments."""
    
    def __init__(self):
        logger.info("Initializing Azure DevOps client...")
        
        org_url = os.getenv("AZURE_DEVOPS_ORG_URL")
        pat = os.getenv("AZURE_DEVOPS_PAT") or os.getenv("AZURE_DEVOOS_PAT")  # fallback for typo
        
        if not org_url or not pat:
            raise ValueError("AZURE_DEVOPS_ORG_URL and AZURE_DEVOPS_PAT must be set in environment")
        
        credentials = BasicAuthentication("", pat)
        self.connection = Connection(org_url, credentials)
        self.git_client: GitClient = self.connection.clients.get_git_client()
        
        logger.success("Azure DevOps client initialized successfully")
    
    def get_pull_request_changes(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int
    ) -> List[CodeChange]:
        """Fetch all changes from a pull request."""
        logger.info(f"Fetching pull request #{pull_request_id} changes...")
        
        pr = self.git_client.get_pull_request(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        logger.debug(f"PR title: {pr.title}")
        
        logger.info("Fetching pull request iterations...")
        iterations = self.git_client.get_pull_request_iterations(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            project=project
        )
        logger.info(f"Found {len(iterations)} iterations")
        
        code_changes = []
        seen_files = set()  # Track files to avoid duplicates
        
        for iteration in iterations:
            iter_id = iteration.id
            logger.debug(f"Processing iteration {iter_id}/{len(iterations)}")
            
            # Get commit IDs for this iteration
            source_commit_id = None
            target_commit_id = None
            
            if hasattr(iteration, 'source_ref_commit') and iteration.source_ref_commit:
                source_commit_id = iteration.source_ref_commit.commit_id
            if hasattr(iteration, 'target_ref_commit') and iteration.target_ref_commit:
                target_commit_id = iteration.target_ref_commit.commit_id
            
            # Get changes for this iteration
            logger.debug(f"Fetching changes for iteration {iter_id}...")
            changes = self.git_client.get_pull_request_iteration_changes(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                iteration_id=iter_id,
            )
            logger.debug(f"Found {len(changes.change_entries)} changes in iteration {iter_id}")
            
            for change in changes.change_entries:
                # In azure-devops 7.1.0b4, item is in additional_properties
                item = None
                if hasattr(change, 'item') and change.item:
                    item = change.item
                elif 'item' in change.additional_properties:
                    item = change.additional_properties['item']
                
                if item:
                    # Get file path
                    file_path = item['path'] if isinstance(item, dict) else item.path
                    
                    # Skip if already processed
                    if file_path in seen_files:
                        continue
                    seen_files.add(file_path)
                    
                    # Get change_type
                    change_type = None
                    if hasattr(change, 'change_type'):
                        change_type = change.change_type
                    elif 'changeType' in change.additional_properties:
                        change_type = change.additional_properties['changeType']
                    
                    logger.debug(f"Getting diff for file: {file_path} (change_type: {change_type})")
                    
                    # Get the diff content using iteration-specific commit IDs
                    diff = self._get_diff(
                        project, repository_id, source_commit_id, target_commit_id, change, item
                    )
                    code_changes.append(CodeChange(
                        file_path=file_path,
                        diff=diff,
                        language=self._detect_language(file_path),
                        is_new=change_type == "add",
                        is_deleted=change_type == "delete"
                    ))
        
        logger.success(f"Completed fetching {len(code_changes)} file changes")
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
        logger.info(f"Posting review comments to PR #{pull_request_id}...")
        logger.info(f"Total findings: {result.summary.total_findings}")
        
        inline_count = 0
        for i, finding in enumerate(result.findings):
            if finding.line_start:
                inline_count += 1
                logger.debug(f"Posting inline comment {i+1}/{len(result.findings)}: {finding.title}")
                self._post_inline_comment(
                    project=project,
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    finding=finding
                )
        
        logger.info(f"Posted {inline_count} inline comments")
        
        # Always post the overall summary as a top-level comment
        logger.info("Posting summary comment...")
        self._post_summary_comment(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            result=result
        )
        
        logger.success(f"Successfully posted review comments to PR #{pull_request_id}")
    
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
        source_commit_id: Optional[str],
        target_commit_id: Optional[str],
        change,
        item
    ) -> str:
        """Get diff content by getting before/after file content and diffing it."""
        # If diff is already available, return it
        if hasattr(change, 'diff') and change.diff:
            logger.debug("Diff already available from API")
            return change.diff
        
        if 'diff' in change.additional_properties and change.additional_properties['diff']:
            diff_data = change.additional_properties['diff']
            if isinstance(diff_data, str):
                logger.debug("Diff available in additional_properties")
                return diff_data
            elif hasattr(diff_data, 'diff'):
                logger.debug("Diff available as object with diff attribute")
                return diff_data.diff
        
        # Need to get content manually and compute diff
        try:
            if isinstance(item, dict):
                item_path = item['path']
                original_object_id = item.get('originalObjectId')
                object_id = item.get('objectId')
            else:
                item_path = item.path
                original_object_id = getattr(item, 'original_object_id', None)
                object_id = getattr(item, 'object_id', None)
            
            # Determine change type based on object IDs
            has_original = bool(original_object_id)
            has_current = bool(object_id)
            
            if has_current and not has_original:
                change_type = "add"
            elif has_original and not has_current:
                change_type = "delete"
            else:
                change_type = "edit"
            
            logger.debug(f"Change type determined: {change_type}")
            
            if change_type == "add":
                # New file, use source commit (contains the new file)
                logger.debug(f"Getting content for new file: {item_path}")
                after_content = self._get_item_content(
                    project, repository_id, source_commit_id, item_path
                )
                return self._format_added_file_diff(after_content)
            elif change_type == "delete":
                # Deleted file, use target commit (contains the file before deletion)
                logger.debug(f"Getting content for deleted file: {item_path}")
                before_content = self._get_item_content(
                    project, repository_id, target_commit_id, item_path
                )
                return self._format_deleted_file_diff(before_content)
            else:
                # Modified file: before = target (old), after = source (new)
                logger.debug(f"Getting content for modified file: {item_path}")
                before_content = ""
                after_content = ""
                if target_commit_id:
                    before_content = self._get_item_content(
                        project, repository_id, target_commit_id, item_path
                    )
                if source_commit_id:
                    after_content = self._get_item_content(
                        project, repository_id, source_commit_id, item_path
                    )
                return self._compute_unified_diff(before_content, after_content)
        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            return ""
        
        return ""
    
    def _get_item_content(
        self,
        project: str,
        repository_id: str,
        object_id: str,
        path: str
    ) -> str:
        """Get file content by commit ID."""
        version_descriptor = GitVersionDescriptor(
            version=object_id,
            version_type="commit"
        )
        content_stream = self.git_client.get_item_content(
            project=project,
            repository_id=repository_id,
            path=path,
            version_descriptor=version_descriptor
        )
        # Read content from stream
        content = b''
        for chunk in content_stream:
            content += chunk
        return content.decode('utf-8', errors='replace')
    
    def _format_added_file_diff(self, content: str) -> str:
        """Format diff for a newly added file."""
        lines = content.splitlines(keepends=True)
        return ''.join(f'+{line}' for line in lines)
    
    def _format_deleted_file_diff(self, content: str) -> str:
        """Format diff for a deleted file."""
        lines = content.splitlines(keepends=True)
        return ''.join(f'-{line}' for line in lines)
    
    def _compute_unified_diff(self, before: str, after: str) -> str:
        """Compute unified diff between before and after content."""
        import difflib
        
        before_lines = before.splitlines()
        after_lines = after.splitlines()
        
        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile='a',
            tofile='b',
            n=3
        )
        
        # Skip the first two lines (--- a +++ b)
        diff_lines = list(diff)[2:]
        
        # Convert to +, -,  format that's easy to read
        result = []
        for line in diff_lines:
            if line.startswith('+'):
                result.append(line)
            elif line.startswith('-'):
                result.append(line)
            elif line.startswith('@'):
                # Keep hunk headers
                result.append(line)
            else:
                # Context lines
                result.append(' ' + line)
        
        return '\n'.join(result)
    
    def _post_inline_comment(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        finding: ReviewFinding
    ) -> None:
        """Post a single inline comment thread."""
        # Azure DevOps requires line >= 1, skip if no line info
        if not finding.line_start or finding.line_start < 1:
            logger.warning(f"Skipping inline comment '{finding.title}' - no valid line number")
            return

        comment_text = self._format_finding_comment(finding)

        thread = GitPullRequestCommentThread()
        thread.comments = [Comment(content=comment_text)]

        # Map diff line to PR comment coordinates
        # Azure uses 1-based line numbers, offset starts at 1
        line_start = finding.line_start
        line_end = finding.line_end if finding.line_end and finding.line_end >= 1 else line_start

        if not finding.file_path:
            raise ValueError("file_path is required for inline comment")
        thread.thread_context = CommentThreadContext(
            file_path=finding.file_path,
            right_file_start=CommentPosition(line=line_start, offset=1),
            right_file_end=CommentPosition(line=line_end, offset=1)
        )

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
