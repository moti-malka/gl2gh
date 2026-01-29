"""
Tests for GitLab client pagination functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from discovery_agent.gitlab_client import GitLabClient, GitLabResponse, APICallStats


class TestGitLabResponse:
    """Tests for GitLabResponse class."""
    
    def test_is_success_200(self):
        """Test is_success for 200 status."""
        response = GitLabResponse(200, {"data": "test"}, {})
        assert response.is_success is True
    
    def test_is_success_404(self):
        """Test is_success for 404 status."""
        response = GitLabResponse(404, {"error": "not found"}, {})
        assert response.is_success is False
    
    def test_next_page_present(self):
        """Test next_page extraction from headers."""
        response = GitLabResponse(200, [], {"X-Next-Page": "2"})
        assert response.next_page == "2"
    
    def test_next_page_lowercase(self):
        """Test next_page with lowercase header."""
        response = GitLabResponse(200, [], {"x-next-page": "3"})
        assert response.next_page == "3"
    
    def test_next_page_missing(self):
        """Test next_page when not present."""
        response = GitLabResponse(200, [], {})
        assert response.next_page is None
    
    def test_total_items(self):
        """Test total_items extraction."""
        response = GitLabResponse(200, [], {"X-Total": "150"})
        assert response.total_items == 150
    
    def test_total_pages(self):
        """Test total_pages extraction."""
        response = GitLabResponse(200, [], {"X-Total-Pages": "5"})
        assert response.total_pages == 5


class TestGitLabClientPagination:
    """Tests for GitLabClient pagination."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock requests session."""
        with patch("discovery_agent.gitlab_client.requests.Session") as mock:
            yield mock.return_value
    
    def test_paginate_single_page(self, mock_session):
        """Test pagination with single page of results."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-Next-Page": ""}
        mock_response.json.return_value = [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
        ]
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        items = list(client.paginate("/api/v4/test"))
        
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 2
    
    def test_paginate_multiple_pages(self, mock_session):
        """Test pagination across multiple pages."""
        # Setup mock responses for 3 pages
        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.headers = {"X-Next-Page": "2", "X-Total-Pages": "3"}
        page1_response.json.return_value = [{"id": 1}, {"id": 2}]
        
        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.headers = {"X-Next-Page": "3", "X-Total-Pages": "3"}
        page2_response.json.return_value = [{"id": 3}, {"id": 4}]
        
        page3_response = Mock()
        page3_response.status_code = 200
        page3_response.headers = {"X-Next-Page": "", "X-Total-Pages": "3"}
        page3_response.json.return_value = [{"id": 5}]
        
        mock_session.get.side_effect = [page1_response, page2_response, page3_response]
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        items = list(client.paginate("/api/v4/test"))
        
        assert len(items) == 5
        assert [i["id"] for i in items] == [1, 2, 3, 4, 5]
        assert mock_session.get.call_count == 3
    
    def test_paginate_max_items(self, mock_session):
        """Test pagination with max_items limit."""
        # Setup mock response with more items than limit
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-Next-Page": "2"}  # More pages available
        mock_response.json.return_value = [
            {"id": i} for i in range(1, 101)  # 100 items
        ]
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        items = list(client.paginate("/api/v4/test", max_items=50))
        
        assert len(items) == 50
        # Should stop after reaching max_items, not fetch next page
    
    def test_paginate_empty_response(self, mock_session):
        """Test pagination with empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = []
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        items = list(client.paginate("/api/v4/test"))
        
        assert len(items) == 0
    
    def test_paginate_error_response(self, mock_session):
        """Test pagination stops on error response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "not found"}
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        items = list(client.paginate("/api/v4/test"))
        
        assert len(items) == 0
    
    def test_paginate_per_page_param(self, mock_session):
        """Test that per_page parameter is passed correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = []
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        list(client.paginate("/api/v4/test", per_page=50))
        
        # Check that per_page was set to 50
        call_args = mock_session.get.call_args
        assert call_args[1]["params"]["per_page"] == 50


class TestGitLabClientGet:
    """Tests for GitLabClient.get method."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock requests session."""
        with patch("discovery_agent.gitlab_client.requests.Session") as mock:
            yield mock.return_value
    
    def test_get_success(self, mock_session):
        """Test successful GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"id": 1, "name": "test"}
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        status, data, headers = client.get("/api/v4/test")
        
        assert status == 200
        assert data["id"] == 1
    
    def test_get_with_params(self, mock_session):
        """Test GET request with query parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = []
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        client.get("/api/v4/test", params={"state": "opened", "per_page": 100})
        
        call_args = mock_session.get.call_args
        assert call_args[1]["params"]["state"] == "opened"
        assert call_args[1]["params"]["per_page"] == 100
    
    def test_get_text_response(self, mock_session):
        """Test GET request that returns non-JSON."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "plain text content"
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        status, data, headers = client.get("/api/v4/file/raw")
        
        assert status == 200
        assert data == "plain text content"


class TestGitLabClientBackoff:
    """Tests for GitLabClient retry/backoff behavior."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock requests session."""
        with patch("discovery_agent.gitlab_client.requests.Session") as mock:
            yield mock.return_value
    
    @patch("discovery_agent.gitlab_client.time.sleep")
    def test_retry_on_429(self, mock_sleep, mock_session):
        """Test retry on rate limit (429)."""
        # First call returns 429, second succeeds
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}
        rate_limit_response.json.return_value = {"error": "rate limited"}
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.json.return_value = {"success": True}
        
        mock_session.get.side_effect = [rate_limit_response, success_response]
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        status, data, headers = client.get("/api/v4/test")
        
        assert status == 200
        assert data["success"] is True
        assert mock_session.get.call_count == 2
        mock_sleep.assert_called()
    
    @patch("discovery_agent.gitlab_client.time.sleep")
    def test_retry_on_500(self, mock_sleep, mock_session):
        """Test retry on server error (500)."""
        error_response = Mock()
        error_response.status_code = 500
        error_response.headers = {}
        error_response.json.return_value = {"error": "internal error"}
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.json.return_value = {"success": True}
        
        mock_session.get.side_effect = [error_response, success_response]
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        status, data, headers = client.get("/api/v4/test")
        
        assert status == 200
        assert mock_session.get.call_count == 2
    
    @patch("discovery_agent.gitlab_client.time.sleep")
    def test_no_retry_on_404(self, mock_sleep, mock_session):
        """Test no retry on 404 (not retryable)."""
        not_found_response = Mock()
        not_found_response.status_code = 404
        not_found_response.headers = {}
        not_found_response.json.return_value = {"error": "not found"}
        
        mock_session.get.return_value = not_found_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        status, data, headers = client.get("/api/v4/test")
        
        assert status == 404
        assert mock_session.get.call_count == 1
        mock_sleep.assert_not_called()
    
    def test_respect_retry_after_header(self, mock_session):
        """Test that Retry-After header is respected."""
        client = GitLabClient("https://gitlab.example.com", "test-token")
        
        # Test _get_retry_after
        headers = {"Retry-After": "30"}
        retry_after = client._get_retry_after(headers)
        assert retry_after == 30
        
        # Test with lowercase header
        headers = {"retry-after": "15"}
        retry_after = client._get_retry_after(headers)
        assert retry_after == 15
        
        # Test with missing header
        headers = {}
        retry_after = client._get_retry_after(headers)
        assert retry_after is None


class TestAPICallStats:
    """Tests for API call statistics tracking."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock requests session."""
        with patch("discovery_agent.gitlab_client.requests.Session") as mock:
            yield mock.return_value
    
    def test_stats_tracking(self, mock_session):
        """Test that API calls are tracked."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        assert client.stats.total_calls == 0
        
        client.get("/api/v4/test")
        assert client.stats.total_calls == 1
        assert client.stats.successful_calls == 1
        
        client.get("/api/v4/test2")
        assert client.stats.total_calls == 2
        assert client.stats.successful_calls == 2
    
    def test_failed_call_stats(self, mock_session):
        """Test that failed calls are tracked."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "not found"}
        mock_session.get.return_value = mock_response
        
        client = GitLabClient("https://gitlab.example.com", "test-token")
        client._session = mock_session
        
        client.get("/api/v4/nonexistent")
        
        assert client.stats.total_calls == 1
        assert client.stats.failed_calls == 1
        assert client.stats.successful_calls == 0
