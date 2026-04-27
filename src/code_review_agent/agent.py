from typing import List
from loguru import logger
from code_review_agent.models import CodeChange, CodeReviewResult
from code_review_agent.graph import CodeReviewGraph
from code_review_agent.integrations.azure_devops import AzureDevOpsClient


class CodeReviewAgent:
    """Main entry point for the code review agent."""
    
    def __init__(self):
        logger.info("Initializing CodeReviewAgent...")
        self.graph = CodeReviewGraph()
        logger.success("CodeReviewAgent initialized")
    
    def review_pull_request(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        post_comments: bool = True
    ) -> CodeReviewResult:
        """Fetch PR changes from Azure DevOps, run review, and post comments."""
        logger.info("=" * 50)
        logger.info(f"Starting code review for PR #{pull_request_id}")
        logger.info("=" * 50)
        
        # Get changes from Azure DevOps
        logger.info("Step 1/3: Fetching PR changes from Azure DevOps...")
        azure_client = AzureDevOpsClient()
        changes = azure_client.get_pull_request_changes(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        logger.success(f"Fetched {len(changes)} file changes")
        
        # Run the review
        logger.info("Step 2/3: Running AI code review...")
        result = self.graph.run(
            pr_id=str(pull_request_id),
            repository=repository_id,
            changes=changes
        )
        logger.success(f"AI review completed: {result.summary.total_findings} findings")
        
        # Post comments if requested
        if post_comments:
            logger.info("Step 3/3: Posting review comments to Azure DevOps...")
            azure_client.post_review_comments(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                result=result
            )
        else:
            logger.info("Step 3/3: Skipping comment posting (post_comments=False)")
        
        logger.info("=" * 50)
        logger.success(f"Code review completed for PR #{pull_request_id}")
        logger.info("=" * 50)
        
        return result
    
    def review_changes(
        self,
        pr_id: str,
        repository: str,
        changes: List[CodeChange]
    ) -> CodeReviewResult:
        """Review provided changes without Azure integration."""
        logger.info(f"Starting review for {len(changes)} changes...")
        result = self.graph.run(pr_id, repository, changes)
        logger.success(f"Review completed: {result.summary.total_findings} findings")
        return result
