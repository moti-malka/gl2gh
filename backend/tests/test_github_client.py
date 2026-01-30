"""Unit tests for GitHub Client"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.clients.github_client import GitHubClient, RateLimiter


@pytest.fixture
def github_token():
    """GitHub token for testing"""
    return "ghp_test_token_1234567890"


@pytest.fixture
def github_client(github_token):
    """Create a GitHubClient instance"""
    return GitHubClient(token=github_token)


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response"""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.headers = {}
    response.json.return_value = {"id": 123, "name": "test"}
    return response


class TestRateLimiter:
    """Test RateLimiter class"""
    
    def test_initialization(self):
        """Test RateLimiter initialization"""
        limiter = RateLimiter(max_requests_per_minute=60)
        assert limiter.max_requests_per_minute == 60
        assert limiter.min_interval == 1.0
        assert limiter.last_request_time == 0
        assert limiter.retry_after == 0
    
    def test_set_retry_after(self):
        """Test setting retry_after"""
        limiter = RateLimiter()
        limiter.set_retry_after(10)
        assert limiter.retry_after > 0
    
    @pytest.mark.asyncio
    async def test_wait_if_needed_no_wait(self):
        """Test wait_if_needed when no wait is required"""
        limiter = RateLimiter(max_requests_per_minute=6000)  # Very high limit
        await limiter.wait_if_needed()
        # Should complete immediately
        assert limiter.last_request_time > 0


class TestGitHubClient:
    """Test GitHubClient class"""
    
    def test_initialization(self, github_token):
        """Test GitHubClient initialization"""
        client = GitHubClient(token=github_token, max_requests_per_minute=100, timeout=60)
        
        assert client.token == github_token
        assert client.api_url == "https://api.github.com"
        assert client.timeout == 60
        assert isinstance(client.rate_limiter, RateLimiter)
        assert client.client is not None
    
    @pytest.mark.asyncio
    async def test_close(self, github_client):
        """Test closing the client"""
        await github_client.close()
        # Client should be closed, but we can't easily test this
    
    @pytest.mark.asyncio
    async def test_context_manager_async(self, github_token):
        """Test async context manager"""
        async with GitHubClient(token=github_token) as client:
            assert client is not None
        # Client should be closed after exiting context
    
    @pytest.mark.asyncio
    async def test_request_success(self, github_client, mock_httpx_response):
        """Test successful _request"""
        with patch.object(github_client.client, 'request', new=AsyncMock(return_value=mock_httpx_response)):
            response = await github_client._request('GET', '/user')
            assert response.status_code == 200
            assert response.json() == {"id": 123, "name": "test"}
    
    @pytest.mark.asyncio
    async def test_request_rate_limit_429(self, github_client):
        """Test _request with rate limit (429)"""
        rate_limit_response = MagicMock(spec=httpx.Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'Retry-After': '1'}
        
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}
        
        # First call returns 429, second call succeeds
        with patch.object(
            github_client.client,
            'request',
            new=AsyncMock(side_effect=[rate_limit_response, success_response])
        ):
            response = await github_client._request('GET', '/user', max_retries=1)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_request_server_error_retry(self, github_client):
        """Test _request with server error and retry"""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500
        
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=error_response)
        
        with patch.object(
            github_client.client,
            'request',
            new=AsyncMock(side_effect=error)
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await github_client._request('GET', '/user', max_retries=0)
    
    @pytest.mark.asyncio
    async def test_paginated_request(self, github_client):
        """Test paginated_request"""
        page1_response = MagicMock(spec=httpx.Response)
        page1_response.status_code = 200
        page1_response.headers = {'Link': '<https://api.github.com/repos/owner/repo/issues?page=2>; rel="next"'}
        page1_response.json.return_value = [{"id": 1}, {"id": 2}]
        
        page2_response = MagicMock(spec=httpx.Response)
        page2_response.status_code = 200
        page2_response.headers = {}  # No next link
        page2_response.json.return_value = [{"id": 3}]
        
        with patch.object(
            github_client.client,
            'request',
            new=AsyncMock(side_effect=[page1_response, page2_response])
        ):
            items = []
            async for item in github_client.paginated_request('/repos/owner/repo/issues'):
                items.append(item)
            
            assert len(items) == 3
            assert items[0]["id"] == 1
            assert items[1]["id"] == 2
            assert items[2]["id"] == 3
    
    # ===== Authentication Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, github_client, mock_httpx_response):
        """Test verify_token success"""
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            result = await github_client.verify_token()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_token_failure(self, github_client):
        """Test verify_token failure"""
        with patch.object(github_client, '_request', new=AsyncMock(side_effect=Exception("Unauthorized"))):
            result = await github_client.verify_token()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_authenticated_user(self, github_client, mock_httpx_response):
        """Test get_authenticated_user"""
        user_data = {"login": "testuser", "id": 123, "name": "Test User"}
        mock_httpx_response.json.return_value = user_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            user = await github_client.get_authenticated_user()
            assert user["login"] == "testuser"
            assert user["id"] == 123
    
    # ===== Repository Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_repository_org(self, github_client, mock_httpx_response):
        """Test create_repository for organization"""
        repo_data = {
            "id": 123,
            "name": "test-repo",
            "full_name": "test-org/test-repo",
            "private": True
        }
        mock_httpx_response.json.return_value = repo_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            repo = await github_client.create_repository(
                org="test-org",
                name="test-repo",
                description="Test repository",
                private=True
            )
            assert repo["name"] == "test-repo"
            assert repo["full_name"] == "test-org/test-repo"
    
    @pytest.mark.asyncio
    async def test_create_repository_user(self, github_client, mock_httpx_response):
        """Test create_repository for user"""
        repo_data = {
            "id": 456,
            "name": "user-repo",
            "full_name": "testuser/user-repo"
        }
        mock_httpx_response.json.return_value = repo_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            repo = await github_client.create_repository(
                org=None,
                name="user-repo"
            )
            assert repo["name"] == "user-repo"
    
    @pytest.mark.asyncio
    async def test_get_repository(self, github_client, mock_httpx_response):
        """Test get_repository"""
        repo_data = {"id": 123, "name": "test-repo", "owner": {"login": "owner"}}
        mock_httpx_response.json.return_value = repo_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            repo = await github_client.get_repository("owner", "test-repo")
            assert repo["id"] == 123
            assert repo["name"] == "test-repo"
    
    @pytest.mark.asyncio
    async def test_delete_repository(self, github_client, mock_httpx_response):
        """Test delete_repository"""
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            result = await github_client.delete_repository("owner", "test-repo")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_list_branches(self, github_client, mock_httpx_response):
        """Test list_branches"""
        branches_data = [
            {"name": "main", "protected": True},
            {"name": "develop", "protected": False}
        ]
        
        async def mock_paginated():
            for branch in branches_data:
                yield branch
        
        with patch.object(github_client, 'paginated_request', return_value=mock_paginated()):
            branches = await github_client.list_branches("owner", "repo")
            assert len(branches) == 2
            assert branches[0]["name"] == "main"
    
    # ===== Issue Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_issue(self, github_client, mock_httpx_response):
        """Test create_issue"""
        issue_data = {
            "id": 1,
            "number": 1,
            "title": "Test Issue",
            "body": "Test body",
            "state": "open"
        }
        mock_httpx_response.json.return_value = issue_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            issue = await github_client.create_issue(
                repo="owner/repo",
                title="Test Issue",
                body="Test body",
                labels=["bug"]
            )
            assert issue["title"] == "Test Issue"
            assert issue["number"] == 1
    
    @pytest.mark.asyncio
    async def test_list_issues(self, github_client):
        """Test list_issues"""
        issues_data = [
            {"id": 1, "number": 1, "title": "Issue 1"},
            {"id": 2, "number": 2, "title": "Issue 2"}
        ]
        
        async def mock_paginated():
            for issue in issues_data:
                yield issue
        
        with patch.object(github_client, 'paginated_request', return_value=mock_paginated()):
            issues = await github_client.list_issues("owner/repo", state="open")
            assert len(issues) == 2
            assert issues[0]["title"] == "Issue 1"
    
    @pytest.mark.asyncio
    async def test_create_issue_comment(self, github_client, mock_httpx_response):
        """Test create_issue_comment"""
        comment_data = {"id": 1, "body": "Test comment"}
        mock_httpx_response.json.return_value = comment_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            comment = await github_client.create_issue_comment(
                repo="owner/repo",
                issue_num=1,
                body="Test comment"
            )
            assert comment["body"] == "Test comment"
    
    # ===== Pull Request Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_pull_request(self, github_client, mock_httpx_response):
        """Test create_pull_request"""
        pr_data = {
            "id": 1,
            "number": 1,
            "title": "Test PR",
            "head": {"ref": "feature"},
            "base": {"ref": "main"}
        }
        mock_httpx_response.json.return_value = pr_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            pr = await github_client.create_pull_request(
                repo="owner/repo",
                title="Test PR",
                head="feature",
                base="main",
                body="Test PR body"
            )
            assert pr["title"] == "Test PR"
            assert pr["number"] == 1
    
    @pytest.mark.asyncio
    async def test_list_pull_requests(self, github_client):
        """Test list_pull_requests"""
        prs_data = [
            {"id": 1, "number": 1, "title": "PR 1"},
            {"id": 2, "number": 2, "title": "PR 2"}
        ]
        
        async def mock_paginated():
            for pr in prs_data:
                yield pr
        
        with patch.object(github_client, 'paginated_request', return_value=mock_paginated()):
            prs = await github_client.list_pull_requests("owner/repo", state="open")
            assert len(prs) == 2
            assert prs[0]["title"] == "PR 1"
    
    # ===== Release Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_release(self, github_client, mock_httpx_response):
        """Test create_release"""
        release_data = {
            "id": 1,
            "tag_name": "v1.0.0",
            "name": "Release 1.0.0",
            "draft": False
        }
        mock_httpx_response.json.return_value = release_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            release = await github_client.create_release(
                repo="owner/repo",
                tag="v1.0.0",
                name="Release 1.0.0",
                body="Release notes"
            )
            assert release["tag_name"] == "v1.0.0"
    
    @pytest.mark.asyncio
    async def test_list_releases(self, github_client):
        """Test list_releases"""
        releases_data = [
            {"id": 1, "tag_name": "v1.0.0"},
            {"id": 2, "tag_name": "v0.9.0"}
        ]
        
        async def mock_paginated():
            for release in releases_data:
                yield release
        
        with patch.object(github_client, 'paginated_request', return_value=mock_paginated()):
            releases = await github_client.list_releases("owner/repo")
            assert len(releases) == 2
            assert releases[0]["tag_name"] == "v1.0.0"
    
    # ===== Branch Protection Tests =====
    
    @pytest.mark.asyncio
    async def test_update_branch_protection(self, github_client, mock_httpx_response):
        """Test update_branch_protection"""
        protection_data = {
            "required_status_checks": {"strict": True},
            "enforce_admins": True
        }
        mock_httpx_response.json.return_value = protection_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            protection = await github_client.update_branch_protection(
                repo="owner/repo",
                branch="main",
                rules=protection_data
            )
            assert protection["enforce_admins"] is True
    
    @pytest.mark.asyncio
    async def test_get_branch_protection(self, github_client, mock_httpx_response):
        """Test get_branch_protection"""
        protection_data = {"required_status_checks": {"strict": True}}
        mock_httpx_response.json.return_value = protection_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            protection = await github_client.get_branch_protection("owner/repo", "main")
            assert protection is not None
    
    @pytest.mark.asyncio
    async def test_get_branch_protection_not_found(self, github_client):
        """Test get_branch_protection when not found"""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 404
        
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=error_response)
        
        with patch.object(github_client, '_request', new=AsyncMock(side_effect=error)):
            protection = await github_client.get_branch_protection("owner/repo", "main")
            assert protection is None
    
    # ===== Collaborator Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_add_collaborator(self, github_client, mock_httpx_response):
        """Test add_collaborator"""
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            result = await github_client.add_collaborator("owner/repo", "testuser", "push")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_list_collaborators(self, github_client):
        """Test list_collaborators"""
        collaborators_data = [
            {"login": "user1", "permissions": {"admin": True}},
            {"login": "user2", "permissions": {"push": True}}
        ]
        
        async def mock_paginated():
            for collab in collaborators_data:
                yield collab
        
        with patch.object(github_client, 'paginated_request', return_value=mock_paginated()):
            collaborators = await github_client.list_collaborators("owner/repo")
            assert len(collaborators) == 2
            assert collaborators[0]["login"] == "user1"
    
    # ===== File Content Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_or_update_file(self, github_client, mock_httpx_response):
        """Test create_or_update_file"""
        commit_data = {
            "content": {"name": "test.txt", "path": "test.txt"},
            "commit": {"sha": "abc123"}
        }
        mock_httpx_response.json.return_value = commit_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            result = await github_client.create_or_update_file(
                repo="owner/repo",
                path="test.txt",
                content="Test content",
                message="Add test file"
            )
            assert result["commit"]["sha"] == "abc123"
    
    @pytest.mark.asyncio
    async def test_get_file_content(self, github_client, mock_httpx_response):
        """Test get_file_content"""
        import base64
        content = "Test file content"
        encoded_content = base64.b64encode(content.encode()).decode()
        
        file_data = {
            "name": "test.txt",
            "content": encoded_content,
            "encoding": "base64"
        }
        mock_httpx_response.json.return_value = file_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            file_content = await github_client.get_file_content("owner/repo", "test.txt")
            assert file_content == content
    
    # ===== Environment Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_environment(self, github_client, mock_httpx_response):
        """Test create_environment"""
        env_data = {"name": "production", "wait_timer": 0}
        mock_httpx_response.json.return_value = env_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            env = await github_client.create_environment(
                repo="owner/repo",
                environment_name="production",
                wait_timer=0
            )
            assert env["name"] == "production"
    
    @pytest.mark.asyncio
    async def test_list_environments(self, github_client, mock_httpx_response):
        """Test list_environments"""
        envs_data = {
            "environments": [
                {"name": "production"},
                {"name": "staging"}
            ]
        }
        mock_httpx_response.json.return_value = envs_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            envs = await github_client.list_environments("owner/repo")
            assert len(envs) == 2
            assert envs[0]["name"] == "production"
    
    # ===== Secrets Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_get_public_key(self, github_client, mock_httpx_response):
        """Test get_public_key"""
        key_data = {"key_id": "123", "key": "public_key_value"}
        mock_httpx_response.json.return_value = key_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            key = await github_client.get_public_key("owner/repo")
            assert key["key_id"] == "123"
    
    @pytest.mark.asyncio
    async def test_create_or_update_secret(self, github_client, mock_httpx_response):
        """Test create_or_update_secret"""
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            result = await github_client.create_or_update_secret(
                repo="owner/repo",
                secret_name="MY_SECRET",
                encrypted_value="encrypted_value",
                key_id="123"
            )
            assert result is True
    
    # ===== Webhook Methods Tests =====
    
    @pytest.mark.asyncio
    async def test_create_webhook(self, github_client, mock_httpx_response):
        """Test create_webhook"""
        webhook_data = {
            "id": 1,
            "config": {"url": "https://example.com/webhook"},
            "events": ["push", "pull_request"]
        }
        mock_httpx_response.json.return_value = webhook_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            webhook = await github_client.create_webhook(
                repo="owner/repo",
                url="https://example.com/webhook",
                events=["push", "pull_request"]
            )
            assert webhook["id"] == 1
    
    # ===== Rate Limit Tests =====
    
    @pytest.mark.asyncio
    async def test_get_rate_limit(self, github_client, mock_httpx_response):
        """Test get_rate_limit"""
        rate_limit_data = {
            "resources": {
                "core": {
                    "limit": 5000,
                    "remaining": 4999,
                    "reset": 1234567890
                }
            }
        }
        mock_httpx_response.json.return_value = rate_limit_data
        
        with patch.object(github_client, '_request', new=AsyncMock(return_value=mock_httpx_response)):
            rate_limit = await github_client.get_rate_limit()
            assert rate_limit["resources"]["core"]["limit"] == 5000
