from typing import List
from code_review_agent.models import CodeChange, CodeReviewResult
from code_review_agent.graph import CodeReviewGraph
from code_review_agent.integrations.azure_devops import AzureDevOpsClient


class CodeReviewAgent:
    """Main entry point for the code review agent."""
    
    def __init__(self):
        self.graph = CodeReviewGraph()
    
    def review_pull_request(
        self,
        project: str,
        repository_id: str,
        pull_request_id: int,
        post_comments: bool = True
    ) -> CodeReviewResult:
        """Fetch PR changes from Azure DevOps, run review, and post comments."""
        # Get changes from Azure DevOps
        azure_client = AzureDevOpsClient()
        changes = azure_client.get_pull_request_changes(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        # Run the review
        result = self.graph.run(
            pr_id=str(pull_request_id),
            repository=repository_id,
            changes=changes
        )
        
        # Post comments if requested
        if post_comments:
            azure_client.post_review_comments(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                result=result
            )
        
        return result
    
    def review_changes(
        self,
        pr_id: str,
        repository: str,
        changes: List[CodeChange]
    ) -> CodeReviewResult:
        """Review provided changes without Azure integration."""
        return self.graph.run(pr_id, repository, changes)
