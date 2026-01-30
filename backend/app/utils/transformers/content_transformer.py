"""Content transformer for issues, merge requests, and markdown"""

import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from .base_transformer import BaseTransformer, TransformationResult


class ContentTransformer(BaseTransformer):
    """
    Transform GitLab issues and merge requests to GitHub format.
    
    Handles:
    - Markdown conversion (GitLab → GitHub flavored)
    - User mentions update
    - Cross-references update
    - Attribution headers
    - Label and milestone mapping
    - Attachment link rewriting
    """
    
    def __init__(self):
        super().__init__("ContentTransformer")
        self.user_mappings: Dict[str, str] = {}  # gitlab_username -> github_username
        self.attachment_mappings: Dict[str, str] = {}  # old_path -> new_url
    
    def set_user_mappings(self, mappings: List[Dict[str, Any]]):
        """
        Set user mappings for mention conversion.
        
        Args:
            mappings: List of user mapping dicts from UserMapper
        """
        self.user_mappings = {}
        for mapping in mappings:
            gitlab_username = mapping.get("gitlab", {}).get("username")
            github_login = mapping.get("github", {}).get("login")
            if gitlab_username and github_login:
                self.user_mappings[gitlab_username] = github_login
    
    def set_attachment_mappings(self, mappings: Dict[str, str]):
        """
        Set attachment URL mappings for link rewriting.
        
        Args:
            mappings: Dict mapping old GitLab paths to new GitHub URLs
                      e.g. {"/uploads/abc123/file.png": "https://github.com/..."}
        """
        self.attachment_mappings = mappings or {}
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Transform GitLab content to GitHub format.
        
        Args:
            input_data: Dict with:
                - 'content_type': 'issue' or 'merge_request'
                - 'content': GitLab issue or MR dict
                - 'gitlab_project': Project path (for cross-refs)
                - 'github_repo': GitHub owner/repo (for cross-refs)
            
        Returns:
            TransformationResult with transformed content
        """
        self.log_transform_start(input_data.get("content_type", "content"))
        result = TransformationResult(success=True)
        
        # Validate input
        validation = self.validate_input(input_data, ["content_type", "content"])
        if not validation.success:
            return validation
        
        try:
            content_type = input_data["content_type"]
            content = input_data["content"]
            gitlab_project = input_data.get("gitlab_project", "")
            github_repo = input_data.get("github_repo", "")
            
            if content_type == "issue":
                transformed = self._transform_issue(content, gitlab_project, github_repo)
            elif content_type == "merge_request":
                transformed = self._transform_merge_request(content, gitlab_project, github_repo)
            else:
                result.add_error(f"Unknown content type: {content_type}")
                return result
            
            result.data = transformed
            self.log_transform_complete(True, f"Transformed {content_type}")
            
        except Exception as e:
            result.add_error(f"Content transformation error: {str(e)}")
            self.log_transform_complete(False, str(e))
        
        return result
    
    def _transform_issue(
        self,
        issue: Dict[str, Any],
        gitlab_project: str,
        github_repo: str
    ) -> Dict[str, Any]:
        """Transform a GitLab issue to GitHub format"""
        
        # Create attribution header
        attribution = self._create_attribution_header(
            issue.get("author", {}),
            issue.get("created_at"),
            "issue",
            issue.get("web_url", "")
        )
        
        # Transform description
        description = issue.get("description", "")
        transformed_description = self._transform_markdown(
            description,
            gitlab_project,
            github_repo
        )
        
        # Combine attribution and description
        body = f"{attribution}\n\n{transformed_description}"
        
        # Transform labels
        labels = [self._sanitize_label(label) for label in issue.get("labels", [])]
        
        # Transform assignees
        assignees = self._transform_assignees(issue.get("assignees", []))
        
        return {
            "title": issue.get("title", ""),
            "body": body,
            "labels": labels,
            "assignees": assignees,
            "milestone": self._transform_milestone(issue.get("milestone")),
            "state": "open" if issue.get("state") == "opened" else "closed",
            "metadata": {
                "gitlab_iid": issue.get("iid"),
                "gitlab_id": issue.get("id"),
                "gitlab_url": issue.get("web_url"),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at")
            }
        }
    
    def _transform_merge_request(
        self,
        mr: Dict[str, Any],
        gitlab_project: str,
        github_repo: str
    ) -> Dict[str, Any]:
        """Transform a GitLab merge request to GitHub PR format"""
        
        # Create attribution header with reviewer info
        reviewers_text = ""
        if mr.get("reviewers"):
            reviewer_names = [r.get("username", "") for r in mr.get("reviewers", [])]
            reviewers_text = f"\n_Original reviewers: {', '.join(['@' + r for r in reviewer_names])}_"
        
        attribution = self._create_attribution_header(
            mr.get("author", {}),
            mr.get("created_at"),
            "merge request",
            mr.get("web_url", "")
        )
        attribution += reviewers_text
        
        # Transform description
        description = mr.get("description", "")
        transformed_description = self._transform_markdown(
            description,
            gitlab_project,
            github_repo
        )
        
        # Combine attribution and description
        body = f"{attribution}\n\n{transformed_description}"
        
        # Transform labels
        labels = [self._sanitize_label(label) for label in mr.get("labels", [])]
        
        # Transform assignees and reviewers
        assignees = self._transform_assignees(mr.get("assignees", []))
        
        return {
            "title": mr.get("title", ""),
            "body": body,
            "head": mr.get("source_branch", ""),
            "base": mr.get("target_branch", "main"),
            "labels": labels,
            "assignees": assignees,
            "milestone": self._transform_milestone(mr.get("milestone")),
            "draft": mr.get("work_in_progress", False) or mr.get("draft", False),
            "state": self._map_mr_state(mr.get("state")),
            "metadata": {
                "gitlab_iid": mr.get("iid"),
                "gitlab_id": mr.get("id"),
                "gitlab_url": mr.get("web_url"),
                "merge_status": mr.get("merge_status"),
                "merged_at": mr.get("merged_at"),
                "created_at": mr.get("created_at"),
                "updated_at": mr.get("updated_at")
            }
        }
    
    def _create_attribution_header(
        self,
        author: Dict[str, Any],
        created_at: Optional[str],
        content_type: str,
        original_url: str
    ) -> str:
        """Create attribution header for migrated content"""
        
        author_username = author.get("username", "unknown")
        author_name = author.get("name", author_username)
        
        # Check if we have a GitHub mapping for this user
        github_username = self.user_mappings.get(author_username, author_username)
        
        date_str = created_at if created_at else "unknown date"
        
        attribution = f"_Originally created as {content_type} by @{author_username}"
        if github_username != author_username:
            attribution += f" (now @{github_username})"
        attribution += f" on GitLab on {date_str}_"
        
        if original_url:
            attribution += f"\n_Original URL: {original_url}_"
        
        return attribution
    
    def _transform_markdown(
        self,
        markdown: str,
        gitlab_project: str,
        github_repo: str
    ) -> str:
        """
        Transform GitLab flavored markdown to GitHub flavored markdown.
        
        Handles:
        - User mentions
        - Issue/MR cross-references
        - Code blocks
        - Other GitLab-specific syntax
        - Attachment link rewriting
        """
        if not markdown:
            return ""
        
        # Transform user mentions
        markdown = self._transform_mentions(markdown)
        
        # Transform cross-references
        markdown = self._transform_cross_references(markdown, gitlab_project, github_repo)
        
        # Transform GitLab-specific syntax
        markdown = self._transform_gitlab_syntax(markdown)
        
        # Rewrite attachment links
        markdown = self._rewrite_attachment_links(markdown)
        
        return markdown
    
    def _transform_mentions(self, text: str) -> str:
        """Transform @mentions from GitLab to GitHub users"""
        
        def replace_mention(match):
            gitlab_username = match.group(1)
            github_username = self.user_mappings.get(gitlab_username, gitlab_username)
            return f"@{github_username}"
        
        # Match @username patterns
        return re.sub(r'@([\w\-\.]+)', replace_mention, text)
    
    def _transform_cross_references(
        self,
        text: str,
        gitlab_project: str,
        github_repo: str
    ) -> str:
        """Transform issue/MR cross-references"""
        
        # Transform #123 to owner/repo#123 for clarity
        if github_repo:
            # Only transform standalone #numbers, not in URLs
            text = re.sub(
                r'(?<!/)(?<!\w)#(\d+)(?!\w)',
                f"{github_repo}#\\1",
                text
            )
        
        # Transform !123 (MR reference) to #123 (GitHub uses # for both)
        text = re.sub(r'!(\d+)', r'#\1', text)
        
        return text
    
    def _transform_gitlab_syntax(self, text: str) -> str:
        """Transform GitLab-specific markdown syntax to GitHub"""
        
        # GitLab video embed → GitHub doesn't have this, keep as link
        text = re.sub(
            r'!\[([^\]]*)\]\(([^)]+\.mp4[^)]*)\)',
            r'[Video: \1](\2)',
            text
        )
        
        # GitLab collapsible sections → GitHub details/summary
        text = re.sub(
            r'<details>\s*<summary>([^<]+)</summary>',
            r'<details><summary>\1</summary>\n',
            text,
            flags=re.MULTILINE
        )
        
        # GitLab task lists already compatible with GitHub
        # [x] and [ ] work the same
        
        return text
    
    def _sanitize_label(self, label: Any) -> str:
        """Sanitize GitLab label for GitHub"""
        if isinstance(label, dict):
            label = label.get("name", "")
        
        # GitHub labels have some restrictions
        label = str(label).strip()
        
        # Replace or remove invalid characters
        # GitHub allows most characters, but limit to reasonable set
        label = re.sub(r'[^\w\s\-\.:]+', '', label)
        
        # Limit length (GitHub limit is 100 chars, but keep reasonable)
        if len(label) > 50:
            label = label[:50]
        
        return label
    
    def _transform_assignees(self, assignees: List[Dict[str, Any]]) -> List[str]:
        """Transform GitLab assignees to GitHub assignees"""
        github_assignees = []
        
        for assignee in assignees:
            gitlab_username = assignee.get("username")
            if gitlab_username:
                github_username = self.user_mappings.get(gitlab_username, gitlab_username)
                github_assignees.append(github_username)
        
        return github_assignees
    
    def _transform_milestone(self, milestone: Optional[Dict[str, Any]]) -> Optional[str]:
        """Transform GitLab milestone to GitHub milestone title"""
        if milestone:
            return milestone.get("title")
        return None
    
    def _map_mr_state(self, state: str) -> str:
        """Map GitLab MR state to GitHub PR state"""
        state_map = {
            "opened": "open",
            "closed": "closed",
            "merged": "closed",  # GitHub doesn't have separate merged state
            "locked": "closed"
        }
        return state_map.get(state, "open")
    
    def _rewrite_attachment_links(self, text: str) -> str:
        """
        Rewrite attachment links from GitLab paths to new URLs.
        
        Args:
            text: Markdown text containing attachment links
            
        Returns:
            Text with rewritten attachment links
        """
        if not text or not self.attachment_mappings:
            return text
        
        # Sort paths by length (longest first) to avoid partial replacements
        sorted_paths = sorted(self.attachment_mappings.keys(), key=len, reverse=True)
        
        for old_path in sorted_paths:
            new_url = self.attachment_mappings[old_path]
            # Replace the old path with the new URL
            text = text.replace(old_path, new_url)
        
        return text
    
    def transform_comment(
        self,
        comment: Dict[str, Any],
        gitlab_project: str,
        github_repo: str
    ) -> Dict[str, Any]:
        """
        Transform a GitLab comment/note to GitHub comment format.
        
        Args:
            comment: GitLab comment dict
            gitlab_project: GitLab project path
            github_repo: GitHub owner/repo
            
        Returns:
            Transformed comment dict
        """
        # Create attribution for comment
        author = comment.get("author", {})
        author_username = author.get("username", "unknown")
        github_username = self.user_mappings.get(author_username, author_username)
        created_at = comment.get("created_at", "")
        
        attribution = f"_Originally posted by @{author_username}"
        if github_username != author_username:
            attribution += f" (now @{github_username})"
        attribution += f" on {created_at}_\n\n---\n\n"
        
        # Transform comment body
        body = comment.get("body", "")
        transformed_body = self._transform_markdown(body, gitlab_project, github_repo)
        
        return {
            "body": attribution + transformed_body,
            "metadata": {
                "gitlab_id": comment.get("id"),
                "created_at": created_at,
                "updated_at": comment.get("updated_at")
            }
        }
