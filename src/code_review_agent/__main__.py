"""CLI entry point for code-review-agent."""

import argparse
from code_review_agent.agent import CodeReviewAgent


def main():
    parser = argparse.ArgumentParser(description="AI-powered code review agent")
    parser.add_argument("--project", required=True, help="Azure DevOps project name")
    parser.add_argument("--repository", required=True, help="Repository ID")
    parser.add_argument("--pr-id", required=True, type=int, help="Pull request ID")
    args = parser.parse_args()
    
    agent = CodeReviewAgent()
    result = agent.review_pull_request(
        project=args.project,
        repository_id=args.repository,
        pull_request_id=args.pr_id
    )
    
    print(f"\nReview complete: {len(result.findings)} findings found.")
    print(f"Overall risk: {result.summary.overall_risk}")


if __name__ == "__main__":
    main()
