"""GitLab API client for migration operations"""

from typing import Any, Dict, List, Optional
import httpx
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GitLabClient:
    """
    GitLab API client for fetching project metadata and resources.
    
    Supports all operations needed for discovery phase including:
    - Project information
    - Repository details
    - Issues, MRs, Wiki, Releases
    - CI/CD configuration
    - Settings and permissions
    """
    
    def __init__(self, base_url: str, token: str, timeout: int = 30):
        """
        Initialize GitLab client.
        
        Args:
            base_url: GitLab instance URL (e.g., https://gitlab.com)
            token: Personal Access Token with api scope
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v4"
        self.token = token
        self.timeout = timeout
        self.headers = {
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json"
        }
        self._client = None
    
    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.Client(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True
            )
        return self._client
    
    def close(self):
        """Close HTTP client"""
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to GitLab API"""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        try:
            response = self._get_client().get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"GitLab API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling GitLab API: {str(e)}")
            raise
    
    def _get_paginated(self, endpoint: str, params: Optional[Dict] = None, max_pages: int = 100) -> List[Dict[str, Any]]:
        """Make paginated GET request to GitLab API"""
        results = []
        params = params or {}
        params.setdefault('per_page', 100)
        page = 1
        
        while page <= max_pages:
            params['page'] = page
            response = self._get(endpoint, params)
            
            if not response:
                break
            
            if isinstance(response, list):
                results.extend(response)
                if len(response) < params['per_page']:
                    break
            else:
                results.append(response)
                break
            
            page += 1
        
        return results
    
    # Project APIs
    
    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get project details"""
        return self._get(f"projects/{project_id}")
    
    def list_projects(self, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """List all accessible projects"""
        return self._get_paginated("projects", params)
    
    def get_project_by_path(self, path: str) -> Dict[str, Any]:
        """Get project by path (namespace/project)"""
        import urllib.parse
        encoded_path = urllib.parse.quote(path, safe='')
        return self._get(f"projects/{encoded_path}")
    
    # Repository APIs
    
    def get_repository_tree(self, project_id: int, path: str = "", ref: str = "HEAD") -> List[Dict[str, Any]]:
        """Get repository tree"""
        params = {"path": path, "ref": ref, "per_page": 100}
        return self._get_paginated(f"projects/{project_id}/repository/tree", params, max_pages=1)
    
    def get_file_content(self, project_id: int, file_path: str, ref: str = "HEAD") -> Dict[str, Any]:
        """Get file content"""
        import urllib.parse
        encoded_path = urllib.parse.quote(file_path, safe='')
        params = {"ref": ref}
        return self._get(f"projects/{project_id}/repository/files/{encoded_path}", params)
    
    def list_branches(self, project_id: int) -> List[Dict[str, Any]]:
        """List repository branches"""
        return self._get_paginated(f"projects/{project_id}/repository/branches")
    
    def list_tags(self, project_id: int) -> List[Dict[str, Any]]:
        """List repository tags"""
        return self._get_paginated(f"projects/{project_id}/repository/tags")
    
    def get_commits(self, project_id: int, ref_name: Optional[str] = None, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Get commits"""
        params = {}
        if ref_name:
            params['ref_name'] = ref_name
        return self._get_paginated(f"projects/{project_id}/repository/commits", params, max_pages=max_pages)
    
    # Issues APIs
    
    def list_issues(self, project_id: int, state: str = "all") -> List[Dict[str, Any]]:
        """List project issues"""
        params = {"state": state}
        return self._get_paginated(f"projects/{project_id}/issues", params)
    
    def count_issues(self, project_id: int, state: str = "opened") -> int:
        """Count issues by state"""
        issues = self.list_issues(project_id, state)
        return len(issues)
    
    # Merge Requests APIs
    
    def list_merge_requests(self, project_id: int, state: str = "all") -> List[Dict[str, Any]]:
        """List merge requests"""
        params = {"state": state}
        return self._get_paginated(f"projects/{project_id}/merge_requests", params)
    
    def count_merge_requests(self, project_id: int, state: str = "opened") -> int:
        """Count merge requests by state"""
        mrs = self.list_merge_requests(project_id, state)
        return len(mrs)
    
    # Wiki APIs
    
    def get_wiki_pages(self, project_id: int) -> List[Dict[str, Any]]:
        """List wiki pages"""
        try:
            return self._get_paginated(f"projects/{project_id}/wikis")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def has_wiki(self, project_id: int) -> bool:
        """Check if project has wiki enabled"""
        pages = self.get_wiki_pages(project_id)
        return len(pages) > 0
    
    # Releases APIs
    
    def list_releases(self, project_id: int) -> List[Dict[str, Any]]:
        """List project releases"""
        return self._get_paginated(f"projects/{project_id}/releases")
    
    # CI/CD APIs
    
    def has_ci_config(self, project_id: int) -> bool:
        """Check if project has .gitlab-ci.yml"""
        try:
            self.get_file_content(project_id, ".gitlab-ci.yml")
            return True
        except:
            return False
    
    def get_ci_config(self, project_id: int) -> Optional[str]:
        """Get CI configuration content"""
        try:
            file_data = self.get_file_content(project_id, ".gitlab-ci.yml")
            import base64
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return content
        except:
            return None
    
    def list_pipelines(self, project_id: int, max_pages: int = 1) -> List[Dict[str, Any]]:
        """List CI/CD pipelines"""
        return self._get_paginated(f"projects/{project_id}/pipelines", max_pages=max_pages)
    
    def list_pipeline_schedules(self, project_id: int) -> List[Dict[str, Any]]:
        """List pipeline schedules"""
        return self._get_paginated(f"projects/{project_id}/pipeline_schedules")
    
    def list_environments(self, project_id: int) -> List[Dict[str, Any]]:
        """List project environments"""
        return self._get_paginated(f"projects/{project_id}/environments")
    
    def list_variables(self, project_id: int) -> List[Dict[str, Any]]:
        """List project CI/CD variables"""
        return self._get_paginated(f"projects/{project_id}/variables")
    
    # Webhooks APIs
    
    def list_hooks(self, project_id: int) -> List[Dict[str, Any]]:
        """List project webhooks"""
        return self._get_paginated(f"projects/{project_id}/hooks")
    
    # Protected resources APIs
    
    def list_protected_branches(self, project_id: int) -> List[Dict[str, Any]]:
        """List protected branches"""
        return self._get_paginated(f"projects/{project_id}/protected_branches")
    
    def list_protected_tags(self, project_id: int) -> List[Dict[str, Any]]:
        """List protected tags"""
        return self._get_paginated(f"projects/{project_id}/protected_tags")
    
    # Deploy keys APIs
    
    def list_deploy_keys(self, project_id: int) -> List[Dict[str, Any]]:
        """List deploy keys"""
        return self._get_paginated(f"projects/{project_id}/deploy_keys")
    
    # LFS APIs
    
    def has_lfs(self, project_id: int) -> bool:
        """Check if project uses Git LFS"""
        # Check for .gitattributes file
        try:
            content_data = self.get_file_content(project_id, ".gitattributes")
            import base64
            content = base64.b64decode(content_data['content']).decode('utf-8')
            return 'filter=lfs' in content
        except:
            pass
        
        # Check project statistics
        try:
            project = self.get_project(project_id)
            stats = project.get('statistics', {})
            lfs_size = stats.get('lfs_objects_size', 0)
            return lfs_size > 0
        except:
            return False
    
    # Package registry APIs
    
    def list_packages(self, project_id: int) -> List[Dict[str, Any]]:
        """List project packages"""
        try:
            return self._get_paginated(f"projects/{project_id}/packages")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def has_packages(self, project_id: int) -> bool:
        """Check if project has packages"""
        packages = self.list_packages(project_id)
        return len(packages) > 0
    
    # Groups APIs
    
    def list_groups(self) -> List[Dict[str, Any]]:
        """List all accessible groups"""
        return self._get_paginated("groups")
    
    def get_group(self, group_id: int) -> Dict[str, Any]:
        """Get group details"""
        return self._get(f"groups/{group_id}")
    
    def list_group_projects(self, group_id: int) -> List[Dict[str, Any]]:
        """List projects in a group"""
        return self._get_paginated(f"groups/{group_id}/projects")
