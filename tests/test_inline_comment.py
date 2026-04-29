"""Tests for Azure DevOps inline comments."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from azure.devops.v7_1.git.models import (
    GitPullRequestCommentThread,
    Comment,
    CommentThreadContext,
    CommentPosition
)
from code_review_agent.models import CodeChange, ReviewFinding, Severity


class TestInlineComment:
    """Test inline comment posting to Azure DevOps."""

    @pytest.fixture
    def mock_git_client(self):
        """Create a mock Git client."""
        client = Mock()
        client.create_pull_request_thread = Mock(return_value=Mock(id=123))
        client.create_thread = Mock(return_value=Mock(id=123))
        return client

    @pytest.fixture
    def mock_connection(self, mock_git_client):
        """Create a mock Azure DevOps connection."""
        conn = Mock()
        conn.clients.get_git_client = Mock(return_value=mock_git_client)
        return conn

    @pytest.fixture
    def azure_client(self, mock_connection):
        """Create AzureDevOpsClient with mocked dependencies."""
        with patch('code_review_agent.integrations.azure_devops.Connection', return_value=mock_connection):
            with patch.dict('os.environ', {
                'AZURE_DEVOPS_ORG_URL': 'https://dev.azure.com/testorg',
                'AZURE_DEVOPS_PAT': 'fake-pat-token'
            }):
                from code_review_agent.integrations.azure_devops import AzureDevOpsClient
                return AzureDevOpsClient()

    @pytest.fixture
    def sample_finding(self):
        """Create a sample finding for testing."""
        return ReviewFinding(
            title="Division by zero",
            description="This code will raise ZeroDivisionError when x is 0",
            severity=Severity.CRITICAL,
            category="correctness",
            file_path="/backend/app.py",
            line_start=45,
            line_end=45
        )

    def test_post_inline_comment_with_line_info(self, azure_client, sample_finding, mock_git_client):
        """Test posting an inline comment with line information."""
        azure_client._post_inline_comment(
            project="test-project",
            repository_id="repo-123",
            pull_request_id=456,
            finding=sample_finding
        )

        # Verify the thread was created
        mock_git_client.create_pull_request_thread.assert_called_once()

        # Get the thread that was passed
        call_args = mock_git_client.create_pull_request_thread.call_args
        thread = call_args.kwargs['git_pull_request_comment_thread']

        # Verify thread structure
        assert isinstance(thread, GitPullRequestCommentThread)
        assert len(thread.comments) == 1
        assert "Division by zero" in thread.comments[0].content
        assert "🔴 **CRITICAL**" in thread.comments[0].content

        # Verify thread context
        assert isinstance(thread.thread_context, CommentThreadContext)
        assert thread.thread_context.file_path == "/backend/app.py"
        assert isinstance(thread.thread_context.right_file_start, CommentPosition)
        assert thread.thread_context.right_file_start.line == 45
        assert thread.thread_context.right_file_start.offset == 1
        assert thread.thread_context.right_file_end.line == 45

    def test_post_inline_comment_without_line_info(self, azure_client, mock_git_client):
        """Test posting a comment without line information (should be skipped)."""
        finding = ReviewFinding(
            title="Missing test coverage",
            description="This function has no unit tests",
            severity=Severity.MINOR,
            category="tests"
        )

        azure_client._post_inline_comment(
            project="test-project",
            repository_id="repo-123",
            pull_request_id=456,
            finding=finding
        )

        # Without line info, the comment should be skipped
        mock_git_client.create_pull_request_thread.assert_not_called()

    def test_post_inline_comment_fallback_to_create_thread(self, mock_git_client):
        """Test fallback to create_thread method."""
        mock_git_client.create_pull_request_thread = None
        del mock_git_client.create_pull_request_thread

        with patch('code_review_agent.integrations.azure_devops.Connection') as mock_conn:
            mock_conn.return_value.clients.get_git_client.return_value = mock_git_client

            with patch.dict('os.environ', {
                'AZURE_DEVOPS_ORG_URL': 'https://dev.azure.com/testorg',
                'AZURE_DEVOPS_PAT': 'fake-pat-token'
            }):
                from code_review_agent.integrations.azure_devops import AzureDevOpsClient
                client = AzureDevOpsClient()

                finding = ReviewFinding(
                    title="Test",
                    description="Test finding",
                    severity=Severity.MINOR,
                    category="test",
                    file_path="/test.py",
                    line_start=10,
                    line_end=10
                )

                client._post_inline_comment(
                    project="test-project",
                    repository_id="repo-123",
                    pull_request_id=456,
                    finding=finding
                )

                mock_git_client.create_thread.assert_called_once()

    def test_comment_formatting(self, azure_client):
        """Test that comments are properly formatted with severity emoji and suggestions."""
        finding = ReviewFinding(
            title="SQL Injection Risk",
            description="User input is directly concatenated into SQL query",
            severity=Severity.CRITICAL,
            category="security",
            file_path="/api/users.py",
            line_start=23,
            line_end=25,
            suggestion="Use parameterized queries instead"
        )

        comment_text = azure_client._format_finding_comment(finding)

        assert "🔴 **CRITICAL**" in comment_text
        assert "[security]" in comment_text
        assert "SQL Injection Risk" in comment_text
        assert "User input is directly concatenated" in comment_text
        assert "**Suggestion:**" in comment_text
        assert "parameterized queries" in comment_text

    def test_comment_without_suggestion(self, azure_client):
        """Test comment formatting without suggestion."""
        finding = ReviewFinding(
            title="Code Smell",
            description="This code is hard to read",
            severity=Severity.MINOR,
            category="maintainability",
            file_path="/utils/helper.py",
            line_start=5
        )

        comment_text = azure_client._format_finding_comment(finding)

        assert "🔵 **MINOR**" in comment_text
        assert "**Suggestion:**" not in comment_text


class TestInlineCommentEdgeCases:
    """Test edge cases for inline comments."""

    def test_finding_with_only_line_start(self):
        """Test finding with only line_start (no line_end)."""
        finding = ReviewFinding(
            title="Test",
            description="Test description",
            severity=Severity.MAJOR,
            category="test",
            file_path="/test.py",
            line_start=42
        )
        # line_end should default to line_start
        assert finding.line_end is None

    def test_finding_without_file_path(self):
        """Test finding without file_path (top-level comment)."""
        finding = ReviewFinding(
            title="General Comment",
            description="This applies to the whole PR",
            severity=Severity.MINOR,
            category="general"
        )
        assert finding.file_path is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
