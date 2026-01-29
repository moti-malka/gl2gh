"""
AI-Powered Migration Analysis using Azure OpenAI.

Provides intelligent FULL PROJECT analysis (not just CI) to estimate
complete GitLab to GitHub migration effort with high accuracy.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class AIAnalysisResult(TypedDict):
    """Result from AI analysis - comprehensive breakdown."""
    # Total hours estimate
    hours_low: float
    hours_high: float
    
    # Risk level
    risk: str  # "low", "medium", "high"
    
    # Breakdown by component
    breakdown: dict  # code, mrs, issues, ci - each with hours and notes
    
    # Simple lists - what works, what doesn't
    supported: list[str]      # Features that work in GH Actions
    not_supported: list[str]  # Features needing manual work
    
    # Critical points for each component
    critical_notes: dict  # code_notes, mr_notes, issue_notes, ci_notes
    
    # Legacy compat
    confidence: str
    complexity_factors: list[str]
    migration_challenges: list[str]
    recommended_actions: list[str]
    github_actions_equivalent: str | None
    risk_assessment: str


@dataclass
class AIAnalyzerConfig:
    """Configuration for Azure OpenAI analyzer."""
    endpoint: str = ""
    api_key: str = ""
    deployment_name: str = "gpt-4o"
    api_version: str = "2024-02-15-preview"
    max_tokens: int = 3000  # Increased for comprehensive breakdown
    temperature: float = 0.3
    
    @classmethod
    def from_env(cls) -> "AIAnalyzerConfig":
        """Load configuration from environment variables."""
        return cls(
            endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if Azure OpenAI is properly configured."""
        return bool(self.endpoint and self.api_key)


# System prompt for COMPREHENSIVE migration analysis
MIGRATION_ANALYSIS_SYSTEM_PROMPT = """GitLab to GitHub migration expert. Return ONLY valid JSON.

HOUR ESTIMATES:
- Code: 1-2h base, +2-4h if LFS/submodules
- MRs: 0.5h per open MR
- Issues: 3h setup + 1h per 100 issues
- CI: 2-4h simple, 8-16h medium, 20-40h complex (DinD, runners, includes)

JSON FORMAT (no other text):
{
  "hours_low": N, "hours_high": N,
  "risk": "low|medium|high",
  "breakdown": {
    "code": {"hours_low": N, "hours_high": N, "notes": "..."},
    "mrs": {"hours_low": N, "hours_high": N, "notes": "..."},
    "issues": {"hours_low": N, "hours_high": N, "notes": "..."},
    "ci": {"hours_low": N, "hours_high": N, "notes": "..."}
  },
  "critical_notes": {"code_notes": [], "mr_notes": [], "issue_notes": [], "ci_notes": []},
  "supported": ["feature1"],
  "not_supported": ["feature2"]
}

RULES: Sum of breakdown = total. Be realistic. Max 3 items per list."""


def _build_full_analysis_prompt(project_data: dict) -> str:
    """Build comprehensive prompt with all project data for accurate estimation."""
    parts = []
    
    # Project overview
    parts.append("## PROJECT OVERVIEW")
    parts.append(f"Name: {project_data.get('name', 'Unknown')}")
    parts.append(f"Archived: {project_data.get('archived', False)}")
    parts.append(f"Default Branch: {project_data.get('default_branch', 'main')}")
    
    # Repository profile
    repo_profile = project_data.get('repo_profile', {})
    parts.append("\n## REPOSITORY")
    parts.append(f"- Branches: {repo_profile.get('branches_count', 'unknown')}")
    parts.append(f"- Tags: {repo_profile.get('tags_count', 'unknown')}")
    parts.append(f"- Has LFS: {repo_profile.get('has_lfs', 'unknown')}")
    parts.append(f"- Has Submodules: {repo_profile.get('has_submodules', 'unknown')}")
    
    # MRs and Issues
    mr_counts = project_data.get('mr_counts', {})
    issue_counts = project_data.get('issue_counts', {})
    
    parts.append("\n## MERGE REQUESTS")
    if isinstance(mr_counts, dict):
        parts.append(f"- Open: {mr_counts.get('open', 0)}")
        parts.append(f"- Merged: {mr_counts.get('merged', 0)}")
        parts.append(f"- Closed: {mr_counts.get('closed', 0)}")
        parts.append(f"- Total: {mr_counts.get('total', 0)}")
    
    parts.append("\n## ISSUES")
    if isinstance(issue_counts, dict):
        parts.append(f"- Open: {issue_counts.get('open', 0)}")
        parts.append(f"- Closed: {issue_counts.get('closed', 0)}")
        parts.append(f"- Total: {issue_counts.get('total', 0)}")
    
    # Integrations
    integrations = project_data.get('integrations', {})
    parts.append("\n## INTEGRATIONS")
    
    registry = integrations.get('registry', {})
    parts.append(f"- Container Registry: {'Yes' if registry.get('enabled') else 'No'}")
    
    pages = integrations.get('pages', {})
    parts.append(f"- GitLab Pages: {'Yes' if pages.get('enabled') else 'No'}")
    
    protected = integrations.get('protected_branches', {})
    parts.append(f"- Protected Branches: {protected.get('count', 0)}")
    
    releases = integrations.get('releases', {})
    parts.append(f"- Releases: {releases.get('releases_count', 0)}")
    
    # CI/CD Configuration - main focus
    ci_content = project_data.get('ci_content', '')
    ci_profile = project_data.get('ci_profile', {})
    
    parts.append("\n## CI/CD PIPELINE")
    if ci_content:
        parts.append(f"- Lines: {ci_profile.get('total_lines', 'unknown')}")
        parts.append(f"- Jobs: {ci_profile.get('job_count', 'unknown')}")
        
        features = ci_profile.get('features', {})
        if features:
            active = [k for k, v in features.items() if v]
            if active:
                parts.append(f"- Features: {', '.join(active)}")
        
        runner_hints = ci_profile.get('runner_hints', {})
        if runner_hints:
            hints = [k for k, v in runner_hints.items() if v]
            if hints:
                parts.append(f"- Runner hints: {', '.join(hints)}")
        
        if pages.get('has_pages_job'):
            parts.append("- Uses: GitLab Pages deployment")
        if registry.get('enabled'):
            parts.append("- Uses: Container Registry")
        
        parts.append("\n### .gitlab-ci.yml (first 3000 chars):")
        parts.append("```yaml")
        # Limit content more aggressively to leave room for response
        if len(ci_content) > 3000:
            parts.append(ci_content[:3000])
            parts.append("... [truncated - full file has " + str(len(ci_content)) + " chars]")
        else:
            parts.append(ci_content)
        parts.append("```")
    else:
        parts.append("- No CI/CD pipeline detected")
    
    parts.append("\n## TASK")
    parts.append("Provide DETAILED breakdown of migration hours for EACH component.")
    parts.append("Be REALISTIC - consider testing, validation, and edge cases!")
    
    return "\n".join(parts)


def _parse_ai_response(response_text: str) -> AIAnalysisResult | None:
    """Parse AI response with breakdown structure."""
    try:
        # Log the raw response for debugging
        logger.debug(f"Raw AI response:\n{response_text[:1000]}")
        
        # Try to extract JSON
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.error(f"No JSON in AI response. Response:\n{response_text[:500]}")
                return None
        
        data = json.loads(json_str)
        
        hours_low = float(data.get("hours_low", 2))
        hours_high = float(data.get("hours_high", 8))
        risk = data.get("risk", "medium")
        supported = data.get("supported", [])
        not_supported = data.get("not_supported", [])
        
        # Parse breakdown
        breakdown = data.get("breakdown", {})
        if not breakdown:
            # Build default breakdown from total
            breakdown = {
                "code": {"hours_low": 1, "hours_high": 2, "notes": "Standard repo migration"},
                "mrs": {"hours_low": 0, "hours_high": 0, "notes": "No MR migration specified"},
                "issues": {"hours_low": 0, "hours_high": 0, "notes": "No issue migration specified"},
                "ci": {"hours_low": hours_low, "hours_high": hours_high, "notes": "CI/CD migration"}
            }
        
        # Parse critical notes
        critical_notes = data.get("critical_notes", {})
        if not critical_notes:
            critical_notes = {
                "code_notes": [],
                "mr_notes": [],
                "issue_notes": [],
                "ci_notes": not_supported[:3] if not_supported else []
            }
        
        # Keep lists short
        supported = supported[:5] if isinstance(supported, list) else []
        not_supported = not_supported[:5] if isinstance(not_supported, list) else []
        
        return AIAnalysisResult(
            hours_low=hours_low,
            hours_high=hours_high,
            risk=risk,
            supported=supported,
            not_supported=not_supported,
            breakdown=breakdown,
            critical_notes=critical_notes,
            # Legacy compat
            confidence="high" if risk == "low" else "medium" if risk == "medium" else "low",
            complexity_factors=supported,
            migration_challenges=not_supported,
            recommended_actions=[],
            github_actions_equivalent=None,
            risk_assessment=risk,
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse AI response: {e}")
        return None


class AIAnalyzer:
    """
    Azure OpenAI-powered CI pipeline analyzer.
    
    Analyzes GitLab CI configurations and provides intelligent
    estimates for GitHub Actions migration effort.
    """
    
    def __init__(self, config: AIAnalyzerConfig | None = None):
        """
        Initialize the AI analyzer.
        
        Args:
            config: Azure OpenAI configuration. If None, loads from environment.
        """
        self.config = config or AIAnalyzerConfig.from_env()
        self._client = None
    
    @property
    def is_available(self) -> bool:
        """Check if AI analysis is available."""
        return self.config.is_configured
    
    def _get_client(self):
        """Get or create the Azure OpenAI client."""
        if self._client is None:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    azure_endpoint=self.config.endpoint,
                    api_key=self.config.api_key,
                    api_version=self.config.api_version,
                )
            except ImportError:
                logger.error("openai package not installed. Run: pip install openai")
                raise RuntimeError("openai package required for AI analysis")
        return self._client
    
    def analyze_pipeline(
        self,
        ci_content: str,
        project_context: dict | None = None,
    ) -> AIAnalysisResult | None:
        """
        Legacy method - redirects to full project analysis.
        
        Args:
            ci_content: Raw content of .gitlab-ci.yml
            project_context: Optional context about the project
            
        Returns:
            AIAnalysisResult with detailed analysis, or None if analysis failed
        """
        # Build minimal project data from legacy context
        project_data = {
            "name": project_context.get("name", "Unknown") if project_context else "Unknown",
            "ci_content": ci_content,
            "ci_profile": {"total_lines": len(ci_content.split('\n'))},
            "integrations": {
                "registry": {"enabled": project_context.get("has_registry", False) if project_context else False},
                "pages": {"enabled": project_context.get("has_pages", False) if project_context else False},
            },
            "repo_profile": {
                "has_lfs": project_context.get("has_lfs", False) if project_context else False,
            },
        }
        return self.analyze_full_project(project_data)
    
    def analyze_full_project(
        self,
        project_data: dict,
    ) -> AIAnalysisResult | None:
        """
        Analyze a COMPLETE project for migration - not just CI.
        
        Args:
            project_data: Full project data including:
                - name: Project name
                - archived: Is archived
                - default_branch: Default branch name
                - repo_profile: {branches_count, tags_count, has_lfs, has_submodules}
                - ci_content: Raw .gitlab-ci.yml content
                - ci_profile: {total_lines, job_count, features, runner_hints}
                - issue_counts: {open, closed, total}
                - mr_counts: {open, merged, closed, total}
                - integrations: {registry, pages, webhooks, variables, protected_branches, releases}
            
        Returns:
            AIAnalysisResult with total migration estimate, or None if failed
        """
        if not self.is_available:
            logger.warning("AI analysis not available - Azure OpenAI not configured")
            return None
        
        try:
            client = self._get_client()
            
            # Build comprehensive prompt
            user_prompt = _build_full_analysis_prompt(project_data)
            
            # Call Azure OpenAI
            response = client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[
                    {"role": "system", "content": MIGRATION_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                extra_body={"max_completion_tokens": self.config.max_tokens},
            )
            
            # Extract and parse the response
            response_text = response.choices[0].message.content
            
            # Handle empty or None response
            if not response_text:
                finish_reason = response.choices[0].finish_reason
                logger.error(f"AI returned empty response. Finish reason: {finish_reason}")
                if response.choices[0].message.refusal:
                    logger.error(f"Refusal: {response.choices[0].message.refusal}")
                return None
            
            result = _parse_ai_response(response_text)
            
            if result:
                # Simple log
                not_supported_str = ""
                if result.get("not_supported"):
                    not_supported_str = f" | ⚠️ {', '.join(result['not_supported'][:3])}"
                
                logger.info(
                    f"AI: {result['hours_low']}-{result['hours_high']}h (risk: {result['risk']}){not_supported_str}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None
    
    def analyze_pipeline_batch(
        self,
        pipelines: list[tuple[str, str, dict | None]],
    ) -> dict[str, AIAnalysisResult | None]:
        """
        Analyze multiple pipelines.
        
        Args:
            pipelines: List of (project_id, ci_content, project_context) tuples
            
        Returns:
            Dictionary mapping project_id to analysis result
        """
        results = {}
        for project_id, ci_content, context in pipelines:
            results[project_id] = self.analyze_pipeline(ci_content, context)
        return results


def create_ai_analyzer() -> AIAnalyzer | None:
    """
    Factory function to create an AI analyzer if configured.
    
    Returns:
        AIAnalyzer instance if Azure OpenAI is configured, None otherwise
    """
    config = AIAnalyzerConfig.from_env()
    if config.is_configured:
        return AIAnalyzer(config)
    return None


# Fallback estimation when AI is not available
def estimate_without_ai(ci_profile: dict) -> AIAnalysisResult:
    """
    Provide a basic estimate without AI when Azure OpenAI is not configured.
    
    This uses the existing rule-based scoring as a fallback.
    """
    job_count = ci_profile.get("job_count", 0)
    features = ci_profile.get("features", {})
    runner_hints = ci_profile.get("runner_hints", {})
    
    # Calculate base hours from job count
    if job_count <= 3:
        base_low, base_high = 1.0, 2.0
    elif job_count <= 8:
        base_low, base_high = 2.0, 5.0
    elif job_count <= 15:
        base_low, base_high = 5.0, 10.0
    else:
        base_low, base_high = 10.0, 20.0
    
    # Adjust for features
    complexity_factors = []
    
    if features.get("include"):
        base_low += 2
        base_high += 4
        complexity_factors.append("Uses includes/templates")
    
    if features.get("needs"):
        base_low += 1
        base_high += 2
        complexity_factors.append("DAG dependencies (needs)")
    
    if features.get("matrix"):
        base_low += 1
        base_high += 3
        complexity_factors.append("Matrix builds")
    
    if features.get("trigger"):
        base_low += 2
        base_high += 5
        complexity_factors.append("Child pipeline triggers")
    
    if runner_hints.get("docker_in_docker"):
        base_low += 3
        base_high += 6
        complexity_factors.append("Docker-in-Docker setup")
    
    if runner_hints.get("uses_tags"):
        base_low += 1
        base_high += 3
        complexity_factors.append("Custom runner tags")
    
    # Determine risk
    if base_high > 15:
        risk = "high"
    elif base_high > 8:
        risk = "medium"
    else:
        risk = "low"
    
    return AIAnalysisResult(
        hours_low=round(base_low, 1),
        hours_high=round(min(base_high, base_low * 2), 1),  # Cap at 2x
        confidence="low",  # Rule-based is less confident
        complexity_factors=complexity_factors,
        migration_challenges=[
            "Manual review recommended - AI analysis not available"
        ],
        recommended_actions=[
            "Configure Azure OpenAI for more accurate estimates",
            "Review pipeline manually for edge cases",
        ],
        github_actions_equivalent=None,
        risk_assessment=risk,
    )
