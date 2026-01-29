"""
Enrichment Types - v2 schema for migration pricing.

This module defines the complete type structure for the enriched
migration discovery output, supporting accurate hour estimates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict, Literal


# =============================================================================
# Permission Tracking
# =============================================================================

class PermissionsProfile(TypedDict):
    """Track what we could read for confidence calculation."""
    can_read_repo: bool
    can_read_ci: bool
    can_read_variables: bool
    can_read_protected_branches: bool
    can_read_webhooks: bool
    can_read_registry: bool


def empty_permissions() -> PermissionsProfile:
    """Create default permissions (all False)."""
    return PermissionsProfile(
        can_read_repo=False,
        can_read_ci=False,
        can_read_variables=False,
        can_read_protected_branches=False,
        can_read_webhooks=False,
        can_read_registry=False,
    )


# =============================================================================
# Integration Discovery
# =============================================================================

class ProtectedBranchesInfo(TypedDict):
    """Protected branches summary."""
    count: int | str  # int or "unknown"
    has_codeowners: bool | str


class VariablesInfo(TypedDict):
    """CI/CD variables summary (counts only, no values)."""
    project_count: int | str
    group_count: int | str  # "unknown" if no group access


class WebhooksInfo(TypedDict):
    """Webhooks summary."""
    count: int | str


class RegistryInfo(TypedDict):
    """Container registry summary."""
    enabled: bool | str
    has_images: bool | str  # Hint based on repo files


class PagesInfo(TypedDict):
    """GitLab Pages summary."""
    enabled: bool | str
    has_pages_job: bool  # Detected in CI
    has_public_folder: bool | str


class ReleasesInfo(TypedDict):
    """Releases/tags summary."""
    tags_count: int | str
    releases_count: int | str


class IntegrationsProfile(TypedDict):
    """All integration data for a project."""
    protected_branches: ProtectedBranchesInfo
    variables: VariablesInfo
    webhooks: WebhooksInfo
    registry: RegistryInfo
    pages: PagesInfo
    releases: ReleasesInfo


def empty_integrations() -> IntegrationsProfile:
    """Create default integrations profile."""
    return IntegrationsProfile(
        protected_branches=ProtectedBranchesInfo(
            count="unknown",
            has_codeowners="unknown",
        ),
        variables=VariablesInfo(
            project_count="unknown",
            group_count="unknown",
        ),
        webhooks=WebhooksInfo(count="unknown"),
        registry=RegistryInfo(
            enabled="unknown",
            has_images="unknown",
        ),
        pages=PagesInfo(
            enabled="unknown",
            has_pages_job=False,
            has_public_folder="unknown",
        ),
        releases=ReleasesInfo(
            tags_count="unknown",
            releases_count="unknown",
        ),
    )


# =============================================================================
# Risk Flags
# =============================================================================

class RiskFlags(TypedDict):
    """Risk indicators that affect estimates."""
    big_issue_backlog: bool  # open>100 or total>1000
    big_mr_backlog: bool  # open>20 or total>500
    exceeded_limits: bool  # Any count reported as ">N"
    missing_default_branch: bool
    self_hosted_runner_hints: bool
    complex_ci: bool  # CI score > 30


def empty_risk_flags() -> RiskFlags:
    """Create default risk flags."""
    return RiskFlags(
        big_issue_backlog=False,
        big_mr_backlog=False,
        exceeded_limits=False,
        missing_default_branch=False,
        self_hosted_runner_hints=False,
        complex_ci=False,
    )


# =============================================================================
# Migration Scope Flags
# =============================================================================

class ScopeFlags(TypedDict):
    """What to migrate - boolean switches for pricing."""
    migrate_code: bool
    migrate_branches: bool
    migrate_tags: bool
    migrate_issues: bool
    migrate_mrs: bool
    migrate_wiki: bool
    migrate_ci: bool
    migrate_secrets: bool
    migrate_protections: bool
    migrate_webhooks: bool
    migrate_releases: bool
    migrate_registry: bool
    migrate_pages: bool


def default_scope_flags() -> ScopeFlags:
    """Create default scope - migrate everything detectable."""
    return ScopeFlags(
        migrate_code=True,
        migrate_branches=True,
        migrate_tags=True,
        migrate_issues=True,
        migrate_mrs=True,
        migrate_wiki=True,
        migrate_ci=True,
        migrate_secrets=True,
        migrate_protections=True,
        migrate_webhooks=True,
        migrate_releases=True,
        migrate_registry=True,
        migrate_pages=True,
    )


# =============================================================================
# Hours Estimation (v2)
# =============================================================================

ConfidenceLevel = Literal["high", "medium", "low"]


class HoursBreakdown(TypedDict):
    """Breakdown of hours by category."""
    repo_transfer: tuple[float, float]  # (low, high)
    ci_conversion: tuple[float, float]
    issues_migration: tuple[float, float]
    mrs_migration: tuple[float, float]
    governance: tuple[float, float]
    integrations: tuple[float, float]
    unknowns_buffer: float  # Percentage added to high estimate


class MigrationEstimateV2(TypedDict):
    """Complete migration estimate for pricing."""
    # Legacy v1 fields (backward compat)
    work_score: int  # 0-100
    bucket: str  # S/M/L/XL
    
    # New v2 fields
    hours_low: float
    hours_high: float
    confidence: ConfidenceLevel
    drivers: list[str]  # Top 5 reasons for estimate
    unknowns: list[str]  # Things we couldn't determine
    blockers: list[str]  # Known blockers
    scope_flags: ScopeFlags
    hours_breakdown: HoursBreakdown | None  # Detailed breakdown (optional)


# =============================================================================
# Complete Enrichment Profile
# =============================================================================

@dataclass
class EnrichmentProfile:
    """Complete enrichment data for a project (v2)."""
    permissions: PermissionsProfile = field(default_factory=empty_permissions)
    integrations: IntegrationsProfile = field(default_factory=empty_integrations)
    risk_flags: RiskFlags = field(default_factory=empty_risk_flags)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "permissions": dict(self.permissions),
            "integrations": {
                "protected_branches": dict(self.integrations["protected_branches"]),
                "variables": dict(self.integrations["variables"]),
                "webhooks": dict(self.integrations["webhooks"]),
                "registry": dict(self.integrations["registry"]),
                "pages": dict(self.integrations["pages"]),
                "releases": dict(self.integrations["releases"]),
            },
            "risk_flags": dict(self.risk_flags),
        }


# =============================================================================
# Risk Score Calculation (for deep analysis selection)
# =============================================================================

def calculate_risk_score(
    has_ci: bool | str,
    archived: bool,
    default_branch: str | None,
    mr_counts: dict | str,
    issue_counts: dict | str,
    last_activity: str | None = None,
) -> int:
    """
    Calculate risk score for selecting projects for deep analysis.
    
    Higher score = more complex/risky = higher priority for deep scan.
    
    Score components:
    - has_ci: +30 (most important for migration)
    - issues_open > 100: +10
    - mrs_open > 20: +10
    - archived: -10 (less risky)
    - default_branch null: +10 (weird state)
    - recent activity: +5
    
    Returns:
        Risk score (higher = more risky/complex)
    """
    score = 0
    
    # CI is the biggest migration factor
    if has_ci is True:
        score += 30
    
    # Archived projects are simpler
    if archived:
        score -= 10
    
    # Missing default branch is risky
    if not default_branch:
        score += 10
    
    # Large issue backlog
    if isinstance(issue_counts, dict):
        open_issues = issue_counts.get("open", 0)
        if isinstance(open_issues, int) and open_issues > 100:
            score += 10
        elif isinstance(open_issues, str) and open_issues.startswith(">"):
            score += 15  # Unknown large number is extra risky
    
    # Large MR backlog
    if isinstance(mr_counts, dict):
        open_mrs = mr_counts.get("open", 0)
        if isinstance(open_mrs, int) and open_mrs > 20:
            score += 10
        elif isinstance(open_mrs, str) and open_mrs.startswith(">"):
            score += 15
    
    # TODO: Add last_activity check if needed
    
    return score
