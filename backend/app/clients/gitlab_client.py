"""GitLab API client with rate limiting and comprehensive data extraction"""

import asyncio
import time
import urllib.parse
from typing import Any, Dict, List, Optional, AsyncIterator, Union
from pathlib import Path
import httpx
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff"""
    
    def __init__(self, max_requests_per_minute: int = 300):
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


class GitLabClient:
    """
    GitLab API client for comprehensive data extraction.
    
    Features:
    - Rate limiting with exponential backoff
    - Automatic pagination
    - Comprehensive error handling
    - Progress callbacks
    """
    
    def __init__(
        self,
        base_url: str,
        token: str,
        max_requests_per_minute: int = 300,
        timeout: int = 30
    ):
        """
        Initialize GitLab client.
        
        Args:
            base_url: GitLab instance URL (e.g., https://gitlab.com)
            token: Personal Access Token
            max_requests_per_minute: Rate limit (default: 300)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/v4"
        self.token = token
        self.timeout = timeout
        self.rate_limiter = RateLimiter(max_requests_per_minute)
        self.logger = get_logger(__name__)
        
        # Create HTTP client
        self.client = httpx.AsyncClient(
            headers={
                "PRIVATE-TOKEN": token,
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
            endpoint: API endpoint (without /api/v4 prefix)
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
                
                # Check if there are more pages
                total_pages = response.headers.get('x-total-pages')
                if total_pages and page >= int(total_pages):
                    break
                
                page += 1
                
            except Exception as e:
                self.logger.error(f"Error fetching page {page} of {endpoint}: {e}")
                break
    
    # ===== Project Methods =====
    
    async def list_projects(
        self,
        membership: bool = True,
        archived: bool = False,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List accessible projects.
        
        Args:
            membership: Only list projects user is member of
            archived: Include archived projects
            max_pages: Maximum pages to fetch
            
        Returns:
            List of project dictionaries
        """
        params = {
            "membership": membership,
            "archived": archived
        }
        projects = []
        async for project in self.paginated_request("projects", params=params, max_pages=max_pages):
            projects.append(project)
        return projects
    
    async def list_group_projects(
        self,
        group_id: Union[int, str],
        include_subgroups: bool = True,
        archived: bool = False,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List all projects in a group.
        
        Args:
            group_id: Group ID or path
            include_subgroups: Include projects from subgroups
            archived: Include archived projects
            max_pages: Maximum pages to fetch
            
        Returns:
            List of project dictionaries
        """
        # URL encode if it's a path
        if isinstance(group_id, str):
            group_id = urllib.parse.quote(group_id, safe='')
        
        params = {
            "include_subgroups": include_subgroups,
            "archived": archived
        }
        projects = []
        async for project in self.paginated_request(f"groups/{group_id}/projects", params=params, max_pages=max_pages):
            projects.append(project)
        return projects
    
    async def get_current_user(self) -> Dict[str, Any]:
        """
        Get current authenticated user information.
        
        Returns:
            User information dictionary
            
        Raises:
            httpx.HTTPError: On request failure
        """
        response = await self._request("GET", "/user")
        return response.json()
    
    async def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get project details"""
        response = await self._request('GET', f"projects/{project_id}")
        return response.json()
    
    async def get_project_by_path(self, path_with_namespace: str) -> Dict[str, Any]:
        """Get project by path"""
        # URL encode the path
        encoded_path = urllib.parse.quote(path_with_namespace, safe='')
        response = await self._request('GET', f"projects/{encoded_path}")
        return response.json()
    
    # ===== Repository Methods =====
    
    async def list_branches(self, project_id: int) -> List[Dict[str, Any]]:
        """List all branches"""
        branches = []
        async for branch in self.paginated_request(f"projects/{project_id}/repository/branches"):
            branches.append(branch)
        return branches
    
    async def list_tags(self, project_id: int) -> List[Dict[str, Any]]:
        """List all tags"""
        tags = []
        async for tag in self.paginated_request(f"projects/{project_id}/repository/tags"):
            tags.append(tag)
        return tags
    
    async def get_file_content(
        self,
        project_id: int,
        file_path: str,
        ref: str = 'HEAD'
    ) -> Optional[str]:
        """Get file content"""
        try:
            encoded_path = urllib.parse.quote(file_path, safe='')
            response = await self._request(
                'GET',
                f"projects/{project_id}/repository/files/{encoded_path}/raw",
                params={'ref': ref}
            )
            return response.text
        except Exception as e:
            self.logger.warning(f"Failed to get file {file_path}: {e}")
            return None
    
    # ===== CI/CD Methods =====
    
    async def list_variables(self, project_id: int) -> List[Dict[str, Any]]:
        """List CI/CD variables (metadata only, not values)"""
        variables = []
        async for var in self.paginated_request(f"projects/{project_id}/variables"):
            variables.append(var)
        return variables
    
    async def list_environments(self, project_id: int) -> List[Dict[str, Any]]:
        """List environments"""
        environments = []
        async for env in self.paginated_request(f"projects/{project_id}/environments"):
            environments.append(env)
        return environments
    
    async def list_pipeline_schedules(self, project_id: int) -> List[Dict[str, Any]]:
        """List pipeline schedules"""
        schedules = []
        async for schedule in self.paginated_request(f"projects/{project_id}/pipeline_schedules"):
            # Get full schedule details
            try:
                response = await self._request(
                    'GET',
                    f"projects/{project_id}/pipeline_schedules/{schedule['id']}"
                )
                schedules.append(response.json())
            except Exception as e:
                self.logger.warning(f"Failed to get schedule {schedule['id']}: {e}")
                schedules.append(schedule)
        return schedules
    
    async def list_pipelines(
        self,
        project_id: int,
        max_count: Optional[int] = 100
    ) -> List[Dict[str, Any]]:
        """List recent pipelines"""
        pipelines = []
        count = 0
        async for pipeline in self.paginated_request(f"projects/{project_id}/pipelines"):
            pipelines.append(pipeline)
            count += 1
            if max_count and count >= max_count:
                break
        return pipelines
    
    # ===== Issue Methods =====
    
    async def list_issues(
        self,
        project_id: int,
        state: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List all issues.
        
        Args:
            project_id: Project ID
            state: Filter by state (opened, closed, all)
            max_pages: Maximum pages to fetch
            
        Returns:
            List of issues
        """
        params = {'scope': 'all'}
        if state:
            params['state'] = state
        
        issues = []
        async for issue in self.paginated_request(
            f"projects/{project_id}/issues",
            params=params,
            max_pages=max_pages
        ):
            issues.append(issue)
        return issues
    
    async def get_issue(self, project_id: int, issue_iid: int) -> Dict[str, Any]:
        """Get issue details"""
        response = await self._request('GET', f"projects/{project_id}/issues/{issue_iid}")
        return response.json()
    
    async def list_issue_notes(self, project_id: int, issue_iid: int) -> List[Dict[str, Any]]:
        """List issue comments/notes"""
        notes = []
        async for note in self.paginated_request(
            f"projects/{project_id}/issues/{issue_iid}/notes"
        ):
            notes.append(note)
        return notes
    
    # ===== Merge Request Methods =====
    
    async def list_merge_requests(
        self,
        project_id: int,
        state: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List all merge requests.
        
        Args:
            project_id: Project ID
            state: Filter by state (opened, closed, merged, all)
            max_pages: Maximum pages to fetch
            
        Returns:
            List of merge requests
        """
        params = {'scope': 'all'}
        if state:
            params['state'] = state
        
        mrs = []
        async for mr in self.paginated_request(
            f"projects/{project_id}/merge_requests",
            params=params,
            max_pages=max_pages
        ):
            mrs.append(mr)
        return mrs
    
    async def get_merge_request(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        """Get merge request details"""
        response = await self._request(
            'GET',
            f"projects/{project_id}/merge_requests/{mr_iid}"
        )
        return response.json()
    
    async def list_merge_request_notes(
        self,
        project_id: int,
        mr_iid: int
    ) -> List[Dict[str, Any]]:
        """List merge request discussions/notes"""
        notes = []
        async for note in self.paginated_request(
            f"projects/{project_id}/merge_requests/{mr_iid}/notes"
        ):
            notes.append(note)
        return notes
    
    async def list_merge_request_discussions(
        self,
        project_id: int,
        mr_iid: int
    ) -> List[Dict[str, Any]]:
        """List merge request discussions (with position data)"""
        discussions = []
        async for discussion in self.paginated_request(
            f"projects/{project_id}/merge_requests/{mr_iid}/discussions"
        ):
            discussions.append(discussion)
        return discussions
    
    async def list_merge_request_approvals(
        self,
        project_id: int,
        mr_iid: int
    ) -> Dict[str, Any]:
        """Get merge request approval status"""
        try:
            response = await self._request(
                'GET',
                f"projects/{project_id}/merge_requests/{mr_iid}/approvals"
            )
            return response.json()
        except Exception as e:
            self.logger.warning(f"Failed to get MR approvals: {e}")
            return {}
    
    # ===== Release Methods =====
    
    async def list_releases(self, project_id: int) -> List[Dict[str, Any]]:
        """List all releases"""
        releases = []
        async for release in self.paginated_request(f"projects/{project_id}/releases"):
            releases.append(release)
        return releases
    
    # ===== Package Methods =====
    
    async def list_packages(self, project_id: int) -> List[Dict[str, Any]]:
        """List packages"""
        packages = []
        async for package in self.paginated_request(f"projects/{project_id}/packages"):
            packages.append(package)
        return packages
    
    # ===== Settings Methods =====
    
    async def list_protected_branches(self, project_id: int) -> List[Dict[str, Any]]:
        """List protected branches"""
        branches = []
        async for branch in self.paginated_request(
            f"projects/{project_id}/protected_branches"
        ):
            branches.append(branch)
        return branches
    
    async def list_protected_tags(self, project_id: int) -> List[Dict[str, Any]]:
        """List protected tags"""
        tags = []
        async for tag in self.paginated_request(f"projects/{project_id}/protected_tags"):
            tags.append(tag)
        return tags
    
    async def list_project_members(self, project_id: int) -> List[Dict[str, Any]]:
        """List project members"""
        members = []
        # Direct members
        async for member in self.paginated_request(f"projects/{project_id}/members"):
            members.append(member)
        # Inherited members
        async for member in self.paginated_request(
            f"projects/{project_id}/members/all"
        ):
            if not any(m['id'] == member['id'] for m in members):
                member['inherited'] = True
                members.append(member)
        return members
    
    async def list_webhooks(self, project_id: int) -> List[Dict[str, Any]]:
        """List webhooks"""
        hooks = []
        async for hook in self.paginated_request(f"projects/{project_id}/hooks"):
            hooks.append(hook)
        return hooks
    
    # Alias for backwards compatibility
    list_hooks = list_webhooks
    
    async def list_deploy_keys(self, project_id: int) -> List[Dict[str, Any]]:
        """List deploy keys"""
        keys = []
        async for key in self.paginated_request(f"projects/{project_id}/deploy_keys"):
            keys.append(key)
        return keys
    
    # ===== Commits Methods =====
    
    async def get_commits(
        self,
        project_id: int,
        ref_name: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get commits for a project.
        
        Args:
            project_id: Project ID
            ref_name: Branch or tag name
            max_pages: Maximum pages to fetch
            
        Returns:
            List of commits
        """
        params = {}
        if ref_name:
            params['ref_name'] = ref_name
        
        commits = []
        async for commit in self.paginated_request(f"projects/{project_id}/repository/commits", params=params, max_pages=max_pages):
            commits.append(commit)
        return commits
    
    # ===== CI/CD Methods =====
    
    async def has_ci_config(self, project_id: int) -> bool:
        """Check if project has GitLab CI config"""
        try:
            content = await self.get_file_content(project_id, '.gitlab-ci.yml')
            return content is not None
        except Exception:
            return False
    
    # ===== Wiki Methods =====
    
    async def has_wiki(self, project_id: int) -> bool:
        """Check if project has wiki enabled with content"""
        try:
            wiki_pages = await self.get_wiki_pages(project_id)
            return len(wiki_pages) > 0
        except Exception:
            return False
    
    async def get_wiki_pages(self, project_id: int) -> List[Dict[str, Any]]:
        """Get wiki pages for a project"""
        pages = []
        async for page in self.paginated_request(f"projects/{project_id}/wikis"):
            pages.append(page)
        return pages
    
    # ===== Package Methods =====
    
    async def has_packages(self, project_id: int) -> bool:
        """Check if project has packages"""
        try:
            packages = await self.list_packages(project_id)
            return len(packages) > 0
        except Exception:
            return False
    
    # ===== LFS Methods =====
    
    async def has_lfs(self, project_id: int) -> bool:
        """Check if project uses LFS"""
        # Check .gitattributes file
        gitattributes = await self.get_file_content(project_id, '.gitattributes')
        if gitattributes and 'filter=lfs' in gitattributes:
            return True
        return False
    
    # ===== Download Methods =====
    
    async def download_file(
        self,
        url: str,
        output_path: Path,
        chunk_size: int = 8192
    ) -> bool:
        """
        Download file from URL.
        
        Args:
            url: File URL
            output_path: Output file path
            chunk_size: Download chunk size
            
        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with self.client.stream('GET', url) as response:
                response.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size):
                        f.write(chunk)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download {url}: {e}")
            return False
