"""Migration Scoring - Calculate work estimates for migration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict, Literal

from .enrichment_types import (
    ConfidenceLevel,
    MigrationEstimateV2,
    ScopeFlags,
    HoursBreakdown,
    IntegrationsProfile,
    RiskFlags,
    PermissionsProfile,
    default_scope_flags,
    empty_risk_flags,
)


class RepoProfile(TypedDict):
    """Repository profile metrics."""
    branches_count: int | str  # int or "unknown"
    tags_count: int | str
    has_submodules: bool | str
    has_lfs: bool | str


class MigrationEstimate(TypedDict):
    """Migration effort estimate (v1 legacy)."""
    work_score: int  # 0-100
    bucket: str  # S/M/L/XL
    drivers: list[str]  # Human-readable reasons


# =============================================================================
# Hours Calculation Constants
# =============================================================================

# Baseline hours by repo type - tighter ranges for accuracy
HOURS_BASELINE = {
    "archived": (0.5, 0.75),
    "active_small": (1.0, 1.5),
    "active_medium": (1.5, 2.0),
    "active_large": (2.0, 2.5),
}

# CI conversion hours by complexity - tighter, more graduated ranges
HOURS_CI = {
    "none": (0.0, 0.0),
    "simple": (2.0, 3.0),       # Just basic jobs
    "medium": (4.0, 6.0),       # rules, artifacts, cache, variables
    "complex": (8.0, 12.0),     # needs, triggers, matrix, self-hosted
    "extreme": (15.0, 22.0),    # All of the above + includes + dind
}

# Issue migration hours - mostly automated, tighter ranges
HOURS_ISSUES = {
    "small": (0.0, 0.25),       # < 100 total
    "medium": (0.25, 0.5),      # 100-500 total
    "large": (0.5, 1.5),        # 500-2000 total
    "huge": (1.5, 3.0),         # > 2000 total (mostly bulk import)
}

# MR migration hours - mostly automated
HOURS_MRS = {
    "small": (0.0, 0.25),       # < 50 total
    "medium": (0.25, 0.5),      # 50-200 total
    "large": (0.5, 1.5),        # 200-1000 total
    "huge": (1.5, 3.0),         # > 1000 total
}

# Governance hours - tighter ranges
HOURS_GOVERNANCE = {
    "protected_branches": (0.5, 1.0),
    "codeowners": (0.25, 0.5),
}

# Integration hours - tighter ranges
HOURS_INTEGRATIONS = {
    "webhooks": (0.5, 1.0),
    "pages": (1.5, 2.5),
    "registry": (1.0, 2.0),
    "wiki": (0.5, 1.0),
    "releases": (0.25, 0.5),
}

# Unknown penalty (percentage added to high estimate) - reduced
UNKNOWN_PENALTY_PERCENT = 8


def calculate_migration_score(
    repo_profile: RepoProfile,
    ci_score: int,
    ci_factors: list[str],
    mr_counts: dict[str, int] | str,
    issue_counts: dict[str, int] | str,
    has_wiki: bool = False,
    archived: bool = False,
) -> MigrationEstimate:
    """
    Calculate migration work score and bucket.
    
    Scoring breakdown (0-100):
    - CI complexity: 0-50 points
    - Repository complexity: 0-25 points
    - Data volume (MRs/Issues): 0-15 points
    - Special features: 0-10 points
    
    Buckets:
    - S (Small): 0-20
    - M (Medium): 21-45
    - L (Large): 46-70
    - XL (Extra Large): 71-100
    
    Args:
        repo_profile: Repository metrics
        ci_score: CI complexity score (0-50)
        ci_factors: CI contributing factors
        mr_counts: MR counts dict or "unknown"
        issue_counts: Issue counts dict or "unknown"
        has_wiki: Whether project has wiki
        archived: Whether project is archived
        
    Returns:
        MigrationEstimate with score, bucket, and drivers
    """
    score = 0
    drivers: list[str] = []
    
    # === CI Complexity (0-50) ===
    score += ci_score
    drivers.extend(ci_factors)
    
    # === Repository Complexity (0-25) ===
    
    # Branches
    branches = repo_profile.get('branches_count', 'unknown')
    if isinstance(branches, int):
        if branches > 50:
            score += 8
            drivers.append(f"Many branches ({branches})")
        elif branches > 20:
            score += 4
            drivers.append(f"Moderate branches ({branches})")
        elif branches > 10:
            score += 2
    
    # Tags
    tags = repo_profile.get('tags_count', 'unknown')
    if isinstance(tags, int):
        if tags > 100:
            score += 5
            drivers.append(f"Many tags ({tags})")
        elif tags > 50:
            score += 3
        elif tags > 20:
            score += 1
    
    # Submodules
    has_submodules = repo_profile.get('has_submodules', 'unknown')
    if has_submodules is True:
        score += 8
        drivers.append("Uses Git submodules")
    
    # LFS
    has_lfs = repo_profile.get('has_lfs', 'unknown')
    if has_lfs is True:
        score += 7
        drivers.append("Uses Git LFS")
    
    # === Data Volume (0-15) ===
    
    # MR counts
    if isinstance(mr_counts, dict):
        total_mrs = mr_counts.get('total', 0)
        open_mrs = mr_counts.get('open', 0)
        
        if total_mrs > 1000:
            score += 8
            drivers.append(f"Large MR history ({total_mrs} MRs)")
        elif total_mrs > 500:
            score += 5
            drivers.append(f"Moderate MR history ({total_mrs} MRs)")
        elif total_mrs > 100:
            score += 3
        
        if open_mrs > 50:
            score += 3
            drivers.append(f"Many open MRs ({open_mrs})")
        elif open_mrs > 20:
            score += 2
    
    # Issue counts
    if isinstance(issue_counts, dict):
        total_issues = issue_counts.get('total', 0)
        open_issues = issue_counts.get('open', 0)
        
        if total_issues > 1000:
            score += 5
            drivers.append(f"Large issue history ({total_issues} issues)")
        elif total_issues > 500:
            score += 3
        elif total_issues > 100:
            score += 2
        
        if open_issues > 100:
            score += 2
            drivers.append(f"Many open issues ({open_issues})")
    
    # === Special Features (0-10) ===
    
    if has_wiki:
        score += 3
        drivers.append("Has wiki content")
    
    # === Adjustments ===
    
    # Archived projects are easier (less active maintenance)
    if archived:
        score = int(score * 0.7)
        drivers.insert(0, "Archived (reduced complexity)")
    
    # Determine bucket
    if score <= 20:
        bucket = "S"
    elif score <= 45:
        bucket = "M"
    elif score <= 70:
        bucket = "L"
    else:
        bucket = "XL"
    
    # Cap at 100
    score = min(score, 100)
    
    # If no drivers, add a default
    if not drivers:
        drivers.append("Simple repository with minimal migration requirements")
    
    return MigrationEstimate(
        work_score=score,
        bucket=bucket,
        drivers=drivers,
    )


def estimate_bucket_from_score(score: int) -> str:
    """Get bucket label from score."""
    if score <= 20:
        return "S"
    elif score <= 45:
        return "M"
    elif score <= 70:
        return "L"
    else:
        return "XL"


def get_bucket_description(bucket: str) -> str:
    """Get human-readable bucket description."""
    descriptions = {
        "S": "Small - Straightforward migration, minimal CI conversion needed",
        "M": "Medium - Standard migration, some CI features to convert",
        "L": "Large - Complex migration, significant CI/workflow changes",
        "XL": "Extra Large - Major migration effort, custom solutions needed",
    }
    return descriptions.get(bucket, "Unknown")


# =============================================================================
# v2 Hours-Based Estimation
# =============================================================================

def _classify_ci_complexity(
    ci_score: int,
    ci_features: dict | None = None,
    runner_hints: dict | None = None,
) -> str:
    """Classify CI complexity for hours estimation."""
    if ci_score == 0:
        return "none"
    
    # Check for extreme complexity markers
    has_dind = runner_hints and runner_hints.get("docker_in_docker")
    has_triggers = ci_features and ci_features.get("trigger")
    has_includes = ci_features and ci_features.get("include")
    has_needs = ci_features and ci_features.get("needs")
    has_matrix = ci_features and ci_features.get("matrix")
    has_self_hosted = runner_hints and runner_hints.get("uses_tags")
    
    extreme_markers = sum([
        bool(has_dind),
        bool(has_triggers),
        ci_score > 40,
    ])
    
    complex_markers = sum([
        bool(has_includes),
        bool(has_needs),
        bool(has_matrix),
        bool(has_self_hosted),
    ])
    
    if extreme_markers >= 2:
        return "extreme"
    elif ci_score > 30 or complex_markers >= 2:
        return "complex"
    elif ci_score > 15:
        return "medium"
    else:
        return "simple"


def _classify_issue_volume(issue_counts: dict | str) -> str:
    """Classify issue volume for hours estimation."""
    if issue_counts == "unknown" or not isinstance(issue_counts, dict):
        return "small"
    
    total = issue_counts.get("total", 0)
    if isinstance(total, str):
        # Handle ">1000" format
        if total.startswith(">"):
            return "huge"
        return "medium"
    
    if total > 2000:
        return "huge"
    elif total > 500:
        return "large"
    elif total > 100:
        return "medium"
    return "small"


def _classify_mr_volume(mr_counts: dict | str) -> str:
    """Classify MR volume for hours estimation."""
    if mr_counts == "unknown" or not isinstance(mr_counts, dict):
        return "small"
    
    total = mr_counts.get("total", 0)
    if isinstance(total, str):
        if total.startswith(">"):
            return "huge"
        return "medium"
    
    if total > 1000:
        return "huge"
    elif total > 200:
        return "large"
    elif total > 50:
        return "medium"
    return "small"


def calculate_migration_hours(
    *,
    repo_profile: RepoProfile,
    ci_score: int,
    ci_features: dict | None = None,
    runner_hints: dict | None = None,
    mr_counts: dict | str,
    issue_counts: dict | str,
    integrations: IntegrationsProfile | None = None,
    permissions: PermissionsProfile | None = None,
    archived: bool = False,
    scope_flags: ScopeFlags | None = None,
) -> MigrationEstimateV2:
    """
    Calculate detailed migration hours estimate.
    
    This produces a defensible hours estimate with:
    - hours_low / hours_high range
    - confidence level based on permissions
    - drivers explaining the biggest contributors
    - unknowns list
    - blockers list
    - scope_flags for pricing granularity
    
    Returns:
        MigrationEstimateV2 with all fields
    """
    scope = scope_flags or default_scope_flags()
    drivers: list[str] = []
    unknowns: list[str] = []
    blockers: list[str] = []
    
    hours_low = 0.0
    hours_high = 0.0
    
    # Track breakdown
    breakdown: dict[str, tuple[float, float]] = {
        "repo_transfer": (0.0, 0.0),
        "ci_conversion": (0.0, 0.0),
        "issues_migration": (0.0, 0.0),
        "mrs_migration": (0.0, 0.0),
        "governance": (0.0, 0.0),
        "integrations": (0.0, 0.0),
    }
    
    # === 1. Repo Transfer Baseline ===
    if archived:
        h = HOURS_BASELINE["archived"]
        drivers.append("Archived repository (minimal transfer)")
    else:
        # Determine size by branch/tag counts
        branches = repo_profile.get("branches_count", "unknown")
        tags = repo_profile.get("tags_count", "unknown")
        
        if isinstance(branches, int) and branches > 50:
            h = HOURS_BASELINE["active_large"]
        elif isinstance(branches, int) and branches > 20:
            h = HOURS_BASELINE["active_medium"]
        else:
            h = HOURS_BASELINE["active_small"]
        
        if isinstance(branches, int) and branches > 20:
            drivers.append(f"{branches} branches to migrate")
    
    breakdown["repo_transfer"] = h
    hours_low += h[0]
    hours_high += h[1]
    
    # Submodules blocker - tighter estimate
    if repo_profile.get("has_submodules") is True:
        blockers.append("Git submodules require manual verification")
        hours_low += 0.5
        hours_high += 1.0
    
    # LFS - tighter estimate
    if repo_profile.get("has_lfs") is True:
        drivers.append("Git LFS data migration")
        hours_low += 0.5
        hours_high += 1.0
    
    # === 2. CI Conversion ===
    if scope["migrate_ci"] and ci_score > 0:
        complexity = _classify_ci_complexity(ci_score, ci_features, runner_hints)
        h = HOURS_CI[complexity]
        breakdown["ci_conversion"] = h
        hours_low += h[0]
        hours_high += h[1]
        
        if complexity == "extreme":
            drivers.append("Extreme CI complexity (DinD, triggers, heavy includes)")
            blockers.append("CI requires significant rewrite for GitHub Actions")
        elif complexity == "complex":
            drivers.append("Complex CI (DAG, matrix, custom runners)")
        elif complexity == "medium":
            drivers.append("Medium CI complexity")
        else:
            drivers.append("Simple CI conversion")
        
        # Self-hosted runner warning
        if runner_hints and runner_hints.get("uses_tags"):
            blockers.append("Uses custom runner tags - may need self-hosted GitHub runners")
    
    # === 3. Issues Migration ===
    if scope["migrate_issues"]:
        vol = _classify_issue_volume(issue_counts)
        h = HOURS_ISSUES[vol]
        breakdown["issues_migration"] = h
        hours_low += h[0]
        hours_high += h[1]
        
        if vol in ("large", "huge"):
            total = issue_counts.get("total", "?") if isinstance(issue_counts, dict) else "?"
            drivers.append(f"Large issue history ({total} issues)")
    
    # === 4. MRs Migration ===
    if scope["migrate_mrs"]:
        vol = _classify_mr_volume(mr_counts)
        h = HOURS_MRS[vol]
        breakdown["mrs_migration"] = h
        hours_low += h[0]
        hours_high += h[1]
        
        if vol in ("large", "huge"):
            total = mr_counts.get("total", "?") if isinstance(mr_counts, dict) else "?"
            drivers.append(f"Large MR history ({total} MRs)")
    
    # === 5. Governance ===
    gov_low, gov_high = 0.0, 0.0
    
    if scope["migrate_protections"] and integrations:
        pb = integrations["protected_branches"]
        pb_count = pb.get("count", "unknown")
        
        if pb_count == "unknown":
            unknowns.append("Protected branches count unknown")
        elif isinstance(pb_count, int) and pb_count > 0:
            h = HOURS_GOVERNANCE["protected_branches"]
            gov_low += h[0]
            gov_high += h[1]
            drivers.append(f"{pb_count} protected branches")
        
        if pb.get("has_codeowners") is True:
            h = HOURS_GOVERNANCE["codeowners"]
            gov_low += h[0]
            gov_high += h[1]
            drivers.append("CODEOWNERS file")
    
    breakdown["governance"] = (gov_low, gov_high)
    hours_low += gov_low
    hours_high += gov_high
    
    # === 6. Integrations ===
    int_low, int_high = 0.0, 0.0
    
    if integrations:
        # Webhooks
        if scope["migrate_webhooks"]:
            wh_count = integrations["webhooks"].get("count", "unknown")
            if wh_count == "unknown":
                unknowns.append("Webhooks count unknown")
            elif isinstance(wh_count, int) and wh_count > 0:
                h = HOURS_INTEGRATIONS["webhooks"]
                int_low += h[0]
                int_high += h[1]
                drivers.append(f"{wh_count} webhooks")
        
        # Pages
        if scope["migrate_pages"]:
            pages = integrations["pages"]
            if pages.get("has_pages_job") or pages.get("has_public_folder") is True:
                h = HOURS_INTEGRATIONS["pages"]
                int_low += h[0]
                int_high += h[1]
                drivers.append("GitLab Pages migration")
        
        # Registry
        if scope["migrate_registry"]:
            reg = integrations["registry"]
            if reg.get("enabled") is True or reg.get("has_images") is True:
                h = HOURS_INTEGRATIONS["registry"]
                int_low += h[0]
                int_high += h[1]
                drivers.append("Container registry migration")
                blockers.append("Container images need manual push to GitHub Container Registry")
        
        # Releases
        if scope["migrate_releases"]:
            rel_count = integrations["releases"].get("releases_count", "unknown")
            if isinstance(rel_count, int) and rel_count > 0:
                h = HOURS_INTEGRATIONS["releases"]
                int_low += h[0]
                int_high += h[1]
    
    breakdown["integrations"] = (int_low, int_high)
    hours_low += int_low
    hours_high += int_high
    
    # === 7. Unknown Penalty ===
    # Cap penalty at 25% max to avoid huge ranges
    unknown_penalty_pct = min(len(unknowns) * UNKNOWN_PENALTY_PERCENT, 25)
    unknown_buffer = hours_high * (unknown_penalty_pct / 100.0)
    hours_high += unknown_buffer
    
    # === 8. Range Cap ===
    # Ensure the high estimate is at most 2x the low estimate to avoid unrealistic ranges
    if hours_high > hours_low * 2:
        hours_high = hours_low * 2
    
    # === Calculate Confidence ===
    critical_unknowns = sum([
        "CI" in str(unknowns),
        "variables" in str(unknowns).lower(),
        "protected" in str(unknowns).lower(),
    ])
    
    # Check permissions
    perm_issues = 0
    if permissions:
        if not permissions.get("can_read_ci"):
            perm_issues += 1
        if not permissions.get("can_read_variables"):
            perm_issues += 1
        if not permissions.get("can_read_protected_branches"):
            perm_issues += 1
    
    total_issues = len(unknowns) + perm_issues + critical_unknowns
    
    if total_issues == 0:
        confidence: ConfidenceLevel = "high"
    elif total_issues <= 2:
        confidence = "medium"
    else:
        confidence = "low"
    
    # === Calculate legacy work_score ===
    # Map hours to 0-100 score
    avg_hours = (hours_low + hours_high) / 2
    work_score = min(100, int(avg_hours * 3))  # Roughly 33 hours = 100
    
    bucket = estimate_bucket_from_score(work_score)
    
    # Keep only top 5 drivers
    top_drivers = drivers[:5] if drivers else ["Simple repository"]
    
    # Round hours
    hours_low = round(hours_low, 1)
    hours_high = round(hours_high, 1)
    
    return MigrationEstimateV2(
        work_score=work_score,
        bucket=bucket,
        hours_low=hours_low,
        hours_high=hours_high,
        confidence=confidence,
        drivers=top_drivers,
        unknowns=unknowns,
        blockers=blockers,
        scope_flags=scope,
        hours_breakdown=HoursBreakdown(
            repo_transfer=breakdown["repo_transfer"],
            ci_conversion=breakdown["ci_conversion"],
            issues_migration=breakdown["issues_migration"],
            mrs_migration=breakdown["mrs_migration"],
            governance=breakdown["governance"],
            integrations=breakdown["integrations"],
            unknowns_buffer=unknown_buffer,
        ),
    )
