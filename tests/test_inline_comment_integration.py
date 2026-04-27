"""Integration tests for Azure DevOps inline comments using real .env."""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv
from code_review_agent.models import CodeChange, ReviewFinding, Severity

# Load .env at module level
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class TestInlineCommentIntegration:
    """Integration tests that use real Azure DevOps credentials from .env."""

    @pytest.fixture
    def azure_client(self):
        """Create real AzureDevOpsClient with .env credentials."""
        required_vars = ["AZURE_DEVOPS_ORG_URL", "AZURE_DEVOPS_PAT"]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            pytest.skip(f"Missing env vars: {missing}")

        from code_review_agent.integrations.azure_devops import AzureDevOpsClient
        return AzureDevOpsClient()

    @pytest.fixture
    def sample_finding(self):
        """Create a sample finding for testing."""
        return ReviewFinding(
            title="Test: Division by zero",
            description="This is a test comment for integration testing",
            severity=Severity.MAJOR,
            category="test",
            file_path="/test_file.py",
            line_start=1,
            line_end=1
        )

    def test_connection(self, azure_client):
        """Test that we can connect to Azure DevOps."""
        assert azure_client.git_client is not None

    def test_post_inline_comment(self, azure_client, sample_finding):
        """Test posting a real inline comment to Azure DevOps."""
        # These should be set in .env for real integration test
        project = os.getenv("TEST_PROJECT")
        repository_id = os.getenv("TEST_REPOSITORY_ID")
        pull_request_id = int(os.getenv("TEST_PULL_REQUEST_ID"))

        if not all([project, repository_id, pull_request_id]):
            pytest.skip("TEST_PROJECT, TEST_REPOSITORY_ID, TEST_PULL_REQUEST_ID not set in .env")

        azure_client._post_inline_comment(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            finding=sample_finding
        )

    def test_post_inline_comment_multiple_lines(self, azure_client):
        """Test posting an inline comment spanning multiple lines."""
        project = os.getenv("TEST_PROJECT")
        repository_id = os.getenv("TEST_REPOSITORY_ID")
        pull_request_id = int(os.getenv("TEST_PULL_REQUEST_ID"))

        if not all([project, repository_id, pull_request_id]):
            pytest.skip("TEST_PROJECT, TEST_REPOSITORY_ID, TEST_PULL_REQUEST_ID not set in .env")

        finding = ReviewFinding(
            title="Test: Multi-line comment",
            description="This comment spans multiple lines",
            severity=Severity.MINOR,
            category="test",
            file_path="/test_file.py",
            line_start=10,
            line_end=15
        )

        azure_client._post_inline_comment(
            project=project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            finding=finding
        )

    def test_post_inline_comment_full_review_flow(self, azure_client):
        """Test the full flow of posting multiple findings as inline comments."""
        project = os.getenv("TEST_PROJECT")
        repository_id = os.getenv("TEST_REPOSITORY_ID")
        pull_request_id = int(os.getenv("TEST_PULL_REQUEST_ID"))

        if not all([project, repository_id, pull_request_id]):
            pytest.skip("TEST_PROJECT, TEST_REPOSITORY_ID, TEST_PULL_REQUEST_ID not set in .env")

        findings = [
            ReviewFinding(
                title=f"Test Finding {i}",
                description=f"This is test finding number {i}",
                severity=Severity.MINOR,
                category="test",
                file_path="/test_file.py",
                line_start=i * 10,
                line_end=i * 10 + 2
            )
            for i in range(1, 4)
        ]

        for finding in findings:
            azure_client._post_inline_comment(
                project=project,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                finding=finding
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
