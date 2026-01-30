"""GitHub API client with rate limiting and comprehensive GitHub operations"""

import asyncio
import time
import urllib.parse
from typing import Any, Dict, List, Optional, AsyncIterator, Union
from pathlib import Path
import httpx
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff for GitHub API"""
    
    def __init__(self, max_requests_per_minute: int = 5000):
        """
        Initialize rate limiter.
        
        Args:
            max_requests_per_minute: Maximum requests per minute
                GitHub default: 5000 requests/hour = ~83 requests/minute
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.min_interval = 60.0 / max_requests_per_minute
        self.last_request_time = 0
        self.retry_after = 0
        
    async def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()
        
        # Wait if we got a retry-after response
        if self.retry_after > now:
            wait_time = self.retry_after - now
            logger.warning(f"Rate limited, waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
            self.retry_after = 0
        
        # Normal rate limiting
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def set_retry_after(self, seconds: int):
        """Set retry-after delay from HTTP header"""
        self.retry_after = time.time() + seconds


class GitHubClient:
    """
    GitHub API client for comprehensive GitHub operations.
    
    Features:
    - Rate limiting with exponential backoff
    - Automatic pagination using Link headers
    - Comprehensive error handling
    - Async/await pattern matching GitLabClient
    """
    
    def __init__(
        self,
        token: str,
        max_requests_per_minute: int = 83,  # ~5000 per hour
        timeout: int = 30
    ):
        """
        Initialize GitHub client.
        
        Args:
            token: Personal Access Token or OAuth token
            max_requests_per_minute: Rate limit (default: 83 = ~5000/hour)
            timeout: Request timeout in seconds
        """
        self.token = token
        self.api_url = "https://api.github.com"
        self.timeout = timeout
        self.rate_limiter = RateLimiter(max_requests_per_minute)
        self.logger = get_logger(__name__)
        
        # Create HTTP client
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            },
            timeout=timeout,
            follow_redirects=True
        )
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    def __enter__(self):
        """Sync context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit - schedule async close"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close())
            else:
                loop.run_until_complete(self.close())
        except RuntimeError:
            # No event loop, create one
            asyncio.run(self.close())
        return False
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> httpx.Response:
        """
        Make HTTP request with rate limiting and retries.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (with or without leading slash)
            params: Query parameters
            data: Request body
            max_retries: Maximum retry attempts
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: On request failure after retries
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Rate limiting
                await self.rate_limiter.wait_if_needed()
                
                # Make request
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.rate_limiter.set_retry_after(retry_after)
                    retry_count += 1
                    if retry_count <= max_retries:
                        self.logger.warning(f"Rate limited (429), retry {retry_count}/{max_retries}")
                        continue
                
                # Check for success
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and retry_count < max_retries:
                    # Retry on server errors
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 60)
                    self.logger.warning(
                        f"Server error {e.response.status_code}, retry {retry_count}/{max_retries} "
                        f"after {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise
                
            except httpx.RequestError as e:
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 60)
                    self.logger.warning(f"Request error: {e}, retry {retry_count}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        raise Exception(f"Max retries exceeded for {method} {endpoint}")
    
    async def paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Make paginated API request yielding individual items.
        GitHub uses Link headers for pagination.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            per_page: Items per page (max 100)
            max_pages: Maximum pages to fetch (None = all)
            
        Yields:
            Individual items from all pages
        """
        params = params or {}
        params['per_page'] = min(per_page, 100)
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
            
            params['page'] = page
            
            try:
                response = await self._request('GET', endpoint, params=params)
                items = response.json()
                
                if not items:
                    break
                
                for item in items:
                    yield item
                
                # Check Link header for next page
                link_header = response.headers.get('Link', '')
                has_next = 'rel="next"' in link_header
                
                if not has_next:
                    break
                
                page += 1
                
            except Exception as e:
                self.logger.error(f"Error fetching page {page} of {endpoint}: {e}")
                break
    
    # ===== Authentication Methods =====
    
    async def verify_token(self) -> bool:
        """
        Verify that the token is valid.
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            response = await self._request('GET', '/user')
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Token verification failed: {e}")
            return False
    
    async def get_authenticated_user(self) -> Dict[str, Any]:
        """
        Get authenticated user information.
        
        Returns:
            User information dictionary
        """
        response = await self._request('GET', '/user')
        return response.json()
    
    # ===== Repository Methods =====
    
    async def create_repository(
        self,
        org: Optional[str],
        name: str,
        **settings
    ) -> Dict[str, Any]:
        """
        Create a new repository.
        
        Args:
            org: Organization name (None for user repo)
            name: Repository name
            **settings: Additional settings (description, private, has_issues, etc.)
            
        Returns:
            Created repository information
        """
        data = {
            "name": name,
            "description": settings.get("description", ""),
            "homepage": settings.get("homepage", ""),
            "private": settings.get("private", True),
            "has_issues": settings.get("has_issues", True),
            "has_projects": settings.get("has_projects", True),
            "has_wiki": settings.get("has_wiki", True),
            "auto_init": settings.get("auto_init", False),
        }
        
        # Add topics if provided
        if "topics" in settings:
            data["topics"] = settings["topics"]
        
        if org:
            endpoint = f"/orgs/{org}/repos"
        else:
            endpoint = "/user/repos"
        
        response = await self._request('POST', endpoint, data=data)
        return response.json()
    
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get repository details.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Repository information
        """
        response = await self._request('GET', f"/repos/{owner}/{repo}")
        return response.json()
    
    async def delete_repository(self, owner: str, repo: str) -> bool:
        """
        Delete a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            True if successful
        """
        try:
            await self._request('DELETE', f"/repos/{owner}/{repo}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete repository: {e}")
            return False
    
    async def list_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List all branches in a repository"""
        branches = []
        async for branch in self.paginated_request(f"/repos/{owner}/{repo}/branches"):
            branches.append(branch)
        return branches
    
    async def list_tags(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List all tags in a repository"""
        tags = []
        async for tag in self.paginated_request(f"/repos/{owner}/{repo}/tags"):
            tags.append(tag)
        return tags
    
    # ===== Issue Methods =====
    
    async def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        **opts
    ) -> Dict[str, Any]:
        """
        Create an issue.
        
        Args:
            repo: Repository in format "owner/repo"
            title: Issue title
            body: Issue body
            **opts: Additional options (labels, assignees, milestone)
            
        Returns:
            Created issue information
        """
        data = {
            "title": title,
            "body": body
        }
        
        if "labels" in opts:
            data["labels"] = opts["labels"]
        if "assignees" in opts:
            data["assignees"] = opts["assignees"]
        if "milestone" in opts:
            data["milestone"] = opts["milestone"]
        
        response = await self._request('POST', f"/repos/{repo}/issues", data=data)
        return response.json()
    
    async def list_issues(
        self,
        repo: str,
        **filters
    ) -> List[Dict[str, Any]]:
        """
        List issues in a repository.
        
        Args:
            repo: Repository in format "owner/repo"
            **filters: Filter options (state, labels, assignee, etc.)
            
        Returns:
            List of issues
        """
        params = {}
        if "state" in filters:
            params["state"] = filters["state"]
        if "labels" in filters:
            params["labels"] = ",".join(filters["labels"])
        if "assignee" in filters:
            params["assignee"] = filters["assignee"]
        
        issues = []
        async for issue in self.paginated_request(f"/repos/{repo}/issues", params=params):
            issues.append(issue)
        return issues
    
    async def create_issue_comment(
        self,
        repo: str,
        issue_num: int,
        body: str
    ) -> Dict[str, Any]:
        """
        Create a comment on an issue.
        
        Args:
            repo: Repository in format "owner/repo"
            issue_num: Issue number
            body: Comment body
            
        Returns:
            Created comment information
        """
        data = {"body": body}
        response = await self._request(
            'POST',
            f"/repos/{repo}/issues/{issue_num}/comments",
            data=data
        )
        return response.json()
    
    # ===== Pull Request Methods =====
    
    async def create_pull_request(
        self,
        repo: str,
        title: str,
        head: str,
        base: str,
        **opts
    ) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            repo: Repository in format "owner/repo"
            title: PR title
            head: Head branch
            base: Base branch
            **opts: Additional options (body, draft, maintainer_can_modify)
            
        Returns:
            Created pull request information
        """
        data = {
            "title": title,
            "head": head,
            "base": base,
            "body": opts.get("body", ""),
            "draft": opts.get("draft", False),
            "maintainer_can_modify": opts.get("maintainer_can_modify", True)
        }
        
        response = await self._request('POST', f"/repos/{repo}/pulls", data=data)
        return response.json()
    
    async def list_pull_requests(
        self,
        repo: str,
        **filters
    ) -> List[Dict[str, Any]]:
        """
        List pull requests in a repository.
        
        Args:
            repo: Repository in format "owner/repo"
            **filters: Filter options (state, head, base)
            
        Returns:
            List of pull requests
        """
        params = {}
        if "state" in filters:
            params["state"] = filters["state"]
        if "head" in filters:
            params["head"] = filters["head"]
        if "base" in filters:
            params["base"] = filters["base"]
        
        prs = []
        async for pr in self.paginated_request(f"/repos/{repo}/pulls", params=params):
            prs.append(pr)
        return prs
    
    # ===== Release Methods =====
    
    async def create_release(
        self,
        repo: str,
        tag: str,
        **opts
    ) -> Dict[str, Any]:
        """
        Create a release.
        
        Args:
            repo: Repository in format "owner/repo"
            tag: Tag name
            **opts: Additional options (name, body, draft, prerelease, target_commitish)
            
        Returns:
            Created release information
        """
        data = {
            "tag_name": tag,
            "name": opts.get("name", tag),
            "body": opts.get("body", ""),
            "draft": opts.get("draft", False),
            "prerelease": opts.get("prerelease", False)
        }
        
        if "target_commitish" in opts:
            data["target_commitish"] = opts["target_commitish"]
        
        response = await self._request('POST', f"/repos/{repo}/releases", data=data)
        return response.json()
    
    async def list_releases(self, repo: str) -> List[Dict[str, Any]]:
        """List all releases in a repository"""
        releases = []
        async for release in self.paginated_request(f"/repos/{repo}/releases"):
            releases.append(release)
        return releases
    
    async def upload_release_asset(
        self,
        release_id: int,
        file_path: str,
        repo: str
    ) -> Dict[str, Any]:
        """
        Upload an asset to a release.
        
        Args:
            release_id: Release ID
            file_path: Path to file to upload
            repo: Repository in format "owner/repo"
            
        Returns:
            Uploaded asset information
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get release to get upload_url
        release_response = await self._request('GET', f"/repos/{repo}/releases/{release_id}")
        release = release_response.json()
        upload_url = release['upload_url'].replace('{?name,label}', '')
        
        # Upload asset
        with open(path, 'rb') as f:
            content = f.read()
        
        # Use raw httpx request for file upload
        response = await self.client.post(
            upload_url,
            params={'name': path.name},
            content=content,
            headers={
                'Content-Type': 'application/octet-stream'
            }
        )
        response.raise_for_status()
        return response.json()
    
    # ===== Branch Protection Methods =====
    
    async def update_branch_protection(
        self,
        repo: str,
        branch: str,
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update branch protection rules.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch name
            rules: Protection rules
            
        Returns:
            Updated protection information
        """
        response = await self._request(
            'PUT',
            f"/repos/{repo}/branches/{branch}/protection",
            data=rules
        )
        return response.json()
    
    async def get_branch_protection(
        self,
        repo: str,
        branch: str
    ) -> Optional[Dict[str, Any]]:
        """Get branch protection rules"""
        try:
            response = await self._request(
                'GET',
                f"/repos/{repo}/branches/{branch}/protection"
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    # ===== Collaborator Methods =====
    
    async def add_collaborator(
        self,
        repo: str,
        username: str,
        permission: str = "push"
    ) -> bool:
        """
        Add a collaborator to a repository.
        
        Args:
            repo: Repository in format "owner/repo"
            username: Username to add
            permission: Permission level (pull, push, admin, maintain, triage)
            
        Returns:
            True if successful
        """
        try:
            data = {"permission": permission}
            await self._request(
                'PUT',
                f"/repos/{repo}/collaborators/{username}",
                data=data
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to add collaborator: {e}")
            return False
    
    async def list_collaborators(self, repo: str) -> List[Dict[str, Any]]:
        """List all collaborators in a repository"""
        collaborators = []
        async for collaborator in self.paginated_request(f"/repos/{repo}/collaborators"):
            collaborators.append(collaborator)
        return collaborators
    
    # ===== File Content Methods =====
    
    async def create_or_update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
        sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or update a file in a repository.
        
        Args:
            repo: Repository in format "owner/repo"
            path: File path
            content: File content (will be base64 encoded)
            message: Commit message
            branch: Branch name (default: repo default branch)
            sha: File SHA (required for updates)
            
        Returns:
            Commit information
        """
        import base64
        
        data = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode()
        }
        
        if branch:
            data["branch"] = branch
        if sha:
            data["sha"] = sha
        
        response = await self._request('PUT', f"/repos/{repo}/contents/{path}", data=data)
        return response.json()
    
    async def get_file_content(
        self,
        repo: str,
        path: str,
        ref: Optional[str] = None
    ) -> Optional[str]:
        """
        Get file content from repository.
        
        Args:
            repo: Repository in format "owner/repo"
            path: File path
            ref: Branch, tag, or commit SHA
            
        Returns:
            File content as string, or None if not found
        """
        import base64
        
        try:
            params = {}
            if ref:
                params["ref"] = ref
            
            response = await self._request('GET', f"/repos/{repo}/contents/{path}", params=params)
            data = response.json()
            
            # Decode base64 content
            if "content" in data:
                return base64.b64decode(data["content"]).decode()
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to get file {path}: {e}")
            return None
    
    # ===== Environment Methods =====
    
    async def create_environment(
        self,
        repo: str,
        environment_name: str,
        **settings
    ) -> Dict[str, Any]:
        """
        Create or update an environment.
        
        Args:
            repo: Repository in format "owner/repo"
            environment_name: Environment name
            **settings: Environment settings (wait_timer, reviewers, deployment_branch_policy)
            
        Returns:
            Environment information
        """
        data = {}
        
        if "wait_timer" in settings:
            data["wait_timer"] = settings["wait_timer"]
        if "reviewers" in settings:
            data["reviewers"] = settings["reviewers"]
        if "deployment_branch_policy" in settings:
            data["deployment_branch_policy"] = settings["deployment_branch_policy"]
        
        response = await self._request(
            'PUT',
            f"/repos/{repo}/environments/{environment_name}",
            data=data
        )
        return response.json()
    
    async def list_environments(self, repo: str) -> List[Dict[str, Any]]:
        """List all environments in a repository"""
        response = await self._request('GET', f"/repos/{repo}/environments")
        data = response.json()
        return data.get("environments", [])
    
    async def create_environment_secret(
        self,
        repo: str,
        environment_name: str,
        secret_name: str,
        encrypted_value: str
    ) -> bool:
        """
        Create or update an environment secret.
        
        Args:
            repo: Repository in format "owner/repo"
            environment_name: Environment name
            secret_name: Secret name
            encrypted_value: Encrypted secret value
            
        Returns:
            True if successful
        """
        try:
            data = {"encrypted_value": encrypted_value}
            await self._request(
                'PUT',
                f"/repos/{repo}/environments/{environment_name}/secrets/{secret_name}",
                data=data
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to create environment secret: {e}")
            return False
    
    # ===== Actions Secrets Methods =====
    
    async def get_public_key(self, repo: str) -> Dict[str, Any]:
        """Get repository public key for encrypting secrets"""
        response = await self._request('GET', f"/repos/{repo}/actions/secrets/public-key")
        return response.json()
    
    async def create_or_update_secret(
        self,
        repo: str,
        secret_name: str,
        encrypted_value: str,
        key_id: str
    ) -> bool:
        """
        Create or update a repository secret.
        
        Args:
            repo: Repository in format "owner/repo"
            secret_name: Secret name
            encrypted_value: Encrypted secret value
            key_id: Public key ID
            
        Returns:
            True if successful
        """
        try:
            data = {
                "encrypted_value": encrypted_value,
                "key_id": key_id
            }
            await self._request(
                'PUT',
                f"/repos/{repo}/actions/secrets/{secret_name}",
                data=data
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to create secret: {e}")
            return False
    
    async def list_secrets(self, repo: str) -> List[Dict[str, Any]]:
        """List repository secrets (names only, not values)"""
        response = await self._request('GET', f"/repos/{repo}/actions/secrets")
        data = response.json()
        return data.get("secrets", [])
    
    # ===== Webhook Methods =====
    
    async def create_webhook(
        self,
        repo: str,
        url: str,
        events: List[str],
        **opts
    ) -> Dict[str, Any]:
        """
        Create a webhook.
        
        Args:
            repo: Repository in format "owner/repo"
            url: Webhook URL
            events: List of events to trigger webhook
            **opts: Additional options (secret, content_type, insecure_ssl)
            
        Returns:
            Created webhook information
        """
        data = {
            "config": {
                "url": url,
                "content_type": opts.get("content_type", "json"),
                "insecure_ssl": opts.get("insecure_ssl", "0")
            },
            "events": events,
            "active": opts.get("active", True)
        }
        
        if "secret" in opts:
            data["config"]["secret"] = opts["secret"]
        
        response = await self._request('POST', f"/repos/{repo}/hooks", data=data)
        return response.json()
    
    async def list_webhooks(self, repo: str) -> List[Dict[str, Any]]:
        """List all webhooks in a repository"""
        webhooks = []
        async for webhook in self.paginated_request(f"/repos/{repo}/hooks"):
            webhooks.append(webhook)
        return webhooks
    
    # ===== Wiki Methods =====
    
    async def list_wiki_pages(self, repo: str) -> List[Dict[str, Any]]:
        """List all wiki pages"""
        try:
            pages = []
            async for page in self.paginated_request(f"/repos/{repo}/wiki"):
                pages.append(page)
            return pages
        except Exception as e:
            self.logger.warning(f"Failed to list wiki pages: {e}")
            return []
    
    # ===== Rate Limit Methods =====
    
    async def get_rate_limit(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        response = await self._request('GET', '/rate_limit')
        return response.json()
