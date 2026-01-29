"""
SOW (Statement of Work) Generator using Azure OpenAI.

Generates professional SOW documents for GitLab → GitHub migration projects.
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Any, TypedDict, Optional
from dataclasses import dataclass, field

# Azure OpenAI SDK
try:
    from openai import AzureOpenAI
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False


# ============== Type Definitions ==============

class SOWOptions(TypedDict, total=False):
    """Options for SOW generation."""
    client_name: str
    target_github_org: str
    timezone: str
    timeline_start_date: str  # YYYY-MM-DD
    migration_mode: str  # "phased" or "bigbang"
    assumptions: list[str]


class SOWRequest(TypedDict):
    """Request body for SOW generation."""
    selected_project_ids: list[int]
    discovery: dict[str, Any]
    sow_options: SOWOptions


class SOWSummary(TypedDict):
    """Summary statistics for the generated SOW."""
    projects_count: int
    total_hours_low: float
    total_hours_high: float
    highest_bucket: str
    bucket_distribution: dict[str, int]
    key_blockers: list[str]
    data_gaps: list[str]


class SOWResponse(TypedDict):
    """Response from SOW generation."""
    markdown: str
    filename: str
    summary: SOWSummary


@dataclass
class ComputedMetrics:
    """Computed metrics from discovery data."""
    total_hours_low: float = 0.0
    total_hours_high: float = 0.0
    bucket_distribution: dict[str, int] = field(default_factory=lambda: {'S': 0, 'M': 0, 'L': 0, 'XL': 0})
    highest_bucket: str = 'S'
    ci_projects_count: int = 0
    archived_count: int = 0
    active_count: int = 0
    total_open_mrs: int = 0
    total_open_issues: int = 0
    unique_blockers: list[str] = field(default_factory=list)
    unique_unknowns: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    risky_projects: list[dict[str, Any]] = field(default_factory=list)
    scope_flags: dict[str, bool] = field(default_factory=dict)
    has_registry: bool = False
    has_pages: bool = False
    has_webhooks_unknown: bool = False
    has_self_hosted_runners: bool = False


def compute_metrics(projects: list[dict[str, Any]]) -> ComputedMetrics:
    """
    Compute aggregate metrics from selected projects.
    
    Args:
        projects: List of project dictionaries with estimate and facts.
        
    Returns:
        ComputedMetrics with aggregated statistics.
    """
    metrics = ComputedMetrics()
    bucket_order = {'S': 1, 'M': 2, 'L': 3, 'XL': 4}
    all_blockers = set()
    all_unknowns = set()
    project_risks = []
    
    for p in projects:
        estimate = p.get('estimate', {})
        facts = p.get('facts', {})
        enrichment = facts.get('enrichment', {})
        
        # Hours
        hours_low = estimate.get('hours_low', 0) or 0
        hours_high = estimate.get('hours_high', 0) or 0
        metrics.total_hours_low += hours_low
        metrics.total_hours_high += hours_high
        
        # Bucket distribution
        bucket = estimate.get('bucket') or facts.get('migration_estimate', {}).get('bucket', 'S')
        if bucket in metrics.bucket_distribution:
            metrics.bucket_distribution[bucket] += 1
            if bucket_order.get(bucket, 0) > bucket_order.get(metrics.highest_bucket, 0):
                metrics.highest_bucket = bucket
        
        # CI count
        if facts.get('has_ci'):
            metrics.ci_projects_count += 1
        
        # Archived vs active
        if p.get('archived'):
            metrics.archived_count += 1
        else:
            metrics.active_count += 1
        
        # MRs and Issues
        mr_counts = facts.get('mr_counts', {})
        issue_counts = facts.get('issue_counts', {})
        metrics.total_open_mrs += mr_counts.get('open', 0) or 0
        metrics.total_open_issues += issue_counts.get('open', 0) or 0
        
        # Blockers and unknowns
        for b in estimate.get('blockers', []) + p.get('readiness', {}).get('blockers', []):
            all_blockers.add(b)
        for u in estimate.get('unknowns', []):
            all_unknowns.add(u)
        
        # Integrations
        integrations = enrichment.get('integrations', {})
        if integrations.get('registry', {}).get('enabled'):
            metrics.has_registry = True
        if integrations.get('pages', {}).get('enabled'):
            metrics.has_pages = True
        if integrations.get('webhooks', {}).get('count') == 'unknown':
            metrics.has_webhooks_unknown = True
        
        # Self-hosted runners
        risk_flags = enrichment.get('risk_flags', {})
        if risk_flags.get('self_hosted_runner_hints'):
            metrics.has_self_hosted_runners = True
        
        # Data gaps (permissions)
        permissions = enrichment.get('permissions', {})
        if permissions.get('can_read_ci') is False:
            metrics.data_gaps.append(f"CI not readable: {p['path_with_namespace']}")
        if permissions.get('can_read_variables') is False:
            metrics.data_gaps.append(f"Variables not readable (403)")
        if permissions.get('can_read_webhooks') is False:
            metrics.data_gaps.append(f"Webhooks not readable (403)")
        
        # Risk score for ranking
        risk_score = hours_high
        if facts.get('ci_profile', {}).get('job_count', 0) > 10:
            risk_score += 20
        if (mr_counts.get('open', 0) or 0) > 10:
            risk_score += 10
        if (issue_counts.get('open', 0) or 0) > 50:
            risk_score += 15
        if risk_flags.get('self_hosted_runner_hints'):
            risk_score += 25
        if integrations.get('registry', {}).get('enabled'):
            risk_score += 10
        
        project_risks.append({
            'path': p['path_with_namespace'],
            'risk_score': risk_score,
            'hours_high': hours_high,
            'bucket': bucket,
            'reasons': estimate.get('drivers', [])[:3]
        })
    
    # Sort and get top risky
    project_risks.sort(key=lambda x: x['risk_score'], reverse=True)
    metrics.risky_projects = project_risks[:5]
    
    metrics.unique_blockers = sorted(list(all_blockers))
    metrics.unique_unknowns = sorted(list(all_unknowns))
    
    # Dedupe data gaps
    metrics.data_gaps = list(set(metrics.data_gaps))[:10]
    
    return metrics


def compress_project_for_llm(project: dict[str, Any]) -> dict[str, Any]:
    """
    Compress project data to essential fields for LLM context.
    
    Reduces token usage by removing unnecessary details.
    """
    estimate = project.get('estimate', {})
    facts = project.get('facts', {})
    enrichment = facts.get('enrichment', {})
    
    return {
        'name': project['path_with_namespace'],
        'archived': project.get('archived', False),
        'visibility': project.get('visibility', 'private'),
        'branch': project.get('default_branch', 'master'),
        'hours': {
            'low': estimate.get('hours_low', 0),
            'high': estimate.get('hours_high', 0)
        },
        'bucket': estimate.get('bucket') or facts.get('migration_estimate', {}).get('bucket', 'S'),
        'confidence': estimate.get('confidence', 'medium'),
        'ci': {
            'has_ci': facts.get('has_ci', False),
            'jobs': facts.get('ci_profile', {}).get('job_count', 0),
            'lines': facts.get('ci_profile', {}).get('total_lines', 0)
        },
        'lfs': facts.get('has_lfs', False),
        'mrs_open': facts.get('mr_counts', {}).get('open', 0),
        'issues_open': facts.get('issue_counts', {}).get('open', 0),
        'drivers': estimate.get('drivers', []),
        'blockers': estimate.get('blockers', []) + project.get('readiness', {}).get('blockers', []),
        'unknowns': estimate.get('unknowns', []),
        'registry': enrichment.get('integrations', {}).get('registry', {}).get('enabled', False),
        'pages': enrichment.get('integrations', {}).get('pages', {}).get('enabled', False),
        'protected_branches': enrichment.get('integrations', {}).get('protected_branches', {}).get('count', 0),
        'self_hosted_hints': enrichment.get('risk_flags', {}).get('self_hosted_runner_hints', False)
    }


# ============== LLM Prompt Templates ==============

SYSTEM_PROMPT = """You are a professional technical writer creating a Statement of Work (SOW) document for a GitLab to GitHub migration project.

OUTPUT REQUIREMENTS:
1. Output ONLY valid Markdown - no code fences, no extra commentary.
2. Use proper Markdown tables with aligned columns.
3. Be professional, concise, and specific.
4. All estimates must come from the provided data - do not invent numbers.
5. Timeline must be realistic based on total hours and team capacity.

STRUCTURE - You MUST include ALL these sections in order:
# Statement of Work (SOW) – GitLab → GitHub Migration
## 1. Executive Summary
## 2. Background & Context  
## 3. Objectives
## 4. In-Scope
## 5. Out-of-Scope
## 6. Project Portfolio Overview (Selected Projects)
## 7. Approach & Methodology
## 8. Detailed Work Breakdown (WBS)
## 9. Timeline (Detailed)
## 10. Roles & Responsibilities (RACI-lite)
## 11. Assumptions & Dependencies
## 12. Risks & Mitigations
## 13. Deliverables
## 14. Acceptance Criteria
## 15. Appendix

TABLE FORMAT for Section 6:
| Project | Bucket | Hours (Low–High) | Confidence | CI | Archived | Open MRs | Open Issues | Key Blockers |
|---------|--------|------------------|------------|-----|----------|----------|-------------|--------------|

TIMELINE TABLE FORMAT for Section 9:
| Week | Dates | Phase | Activities | Milestones |
|------|-------|-------|------------|------------|"""


def build_user_prompt(
    run_meta: dict[str, Any],
    projects: list[dict[str, Any]],
    metrics: ComputedMetrics,
    options: SOWOptions
) -> str:
    """Build the user prompt with all data for SOW generation."""
    
    # Compress projects
    compressed = [compress_project_for_llm(p) for p in projects]
    
    # Sort by bucket then name for deterministic output
    bucket_order = {'XL': 0, 'L': 1, 'M': 2, 'S': 3}
    compressed.sort(key=lambda x: (bucket_order.get(x['bucket'], 4), x['name']))
    
    prompt = f"""Generate a complete SOW document for this GitLab → GitHub migration:

## RUN METADATA
- GitLab URL: {run_meta.get('base_url', 'N/A')}
- Root Group: {run_meta.get('root_group', 'N/A')}
- Discovery Date: {run_meta.get('started_at', 'N/A')[:10] if run_meta.get('started_at') else 'N/A'}

## CLIENT INFORMATION
- Client Name: {options.get('client_name', '[CLIENT NAME]')}
- Target GitHub Org: {options.get('target_github_org', '[GITHUB ORG]')}
- Migration Mode: {options.get('migration_mode', 'phased')}
- Timeline Start: {options.get('timeline_start_date', 'TBD')}

## COMPUTED METRICS
- Total Projects: {len(compressed)}
- Active: {metrics.active_count}, Archived: {metrics.archived_count}
- Total Hours: {metrics.total_hours_low:.0f} - {metrics.total_hours_high:.0f}
- Bucket Distribution: S={metrics.bucket_distribution['S']}, M={metrics.bucket_distribution['M']}, L={metrics.bucket_distribution['L']}, XL={metrics.bucket_distribution['XL']}
- Highest Complexity: {metrics.highest_bucket}
- Projects with CI/CD: {metrics.ci_projects_count}
- Total Open MRs: {metrics.total_open_mrs}
- Total Open Issues: {metrics.total_open_issues}
- Has Container Registry: {metrics.has_registry}
- Has GitLab Pages: {metrics.has_pages}
- Has Self-Hosted Runners: {metrics.has_self_hosted_runners}

## TOP 5 RISKY PROJECTS
{json.dumps(metrics.risky_projects, indent=2)}

## KEY BLOCKERS
{json.dumps(metrics.unique_blockers[:10], indent=2)}

## DATA GAPS / UNKNOWNS
{json.dumps(metrics.data_gaps + metrics.unique_unknowns[:5], indent=2)}

## ASSUMPTIONS (from client)
{json.dumps(options.get('assumptions', ['Standard business hours availability', 'Client will provide access credentials']), indent=2)}

## SELECTED PROJECTS DATA
{json.dumps(compressed, indent=2)}

---
Generate the complete SOW now. Remember:
- Include ALL 15 sections
- Use actual numbers from the data
- Create realistic timeline based on {metrics.total_hours_low:.0f}-{metrics.total_hours_high:.0f} total hours
- Assume ~40 productive hours/week for timeline calculation
- Wave approach: Wave 0 (setup), Wave 1 (S bucket), Wave 2 (M bucket), Wave 3 (L/XL bucket)
"""
    return prompt


# ============== Azure OpenAI Integration ==============

class AzureOpenAIClient:
    """Wrapper for Azure OpenAI API calls."""
    
    def __init__(self):
        self.endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
        self.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
        
        if not AZURE_OPENAI_AVAILABLE:
            raise RuntimeError("Azure OpenAI SDK not installed. Run: pip install openai")
        
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
            )
        
        print(f"[LLM] Connecting to Azure OpenAI: {self.endpoint}")
        print(f"[LLM] Deployment: {self.deployment}")
        
        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
            timeout=120.0  # 2 minute timeout
        )
    
    def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8000,
        temperature: float = 0.3
    ) -> str:
        """
        Generate completion from Azure OpenAI.
        
        Args:
            system_prompt: System message for context
            user_prompt: User message with data
            max_tokens: Maximum tokens in response
            temperature: Creativity parameter (lower = more deterministic)
            
        Returns:
            Generated text content
        """
        max_retries = 2
        last_error = None
        
        # Estimate input tokens to warn if too large
        input_tokens = (len(system_prompt) + len(user_prompt)) // 4
        print(f"[LLM] Request: ~{input_tokens} input tokens, max_output={max_tokens}")
        
        for attempt in range(max_retries + 1):
            try:
                params = {
                    "model": self.deployment,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_completion_tokens": max_tokens
                }
                
                print(f"[LLM] Calling Azure OpenAI (attempt {attempt + 1})...")
                response = self.client.chat.completions.create(**params)
                
                print(f"[LLM] Response: choices={len(response.choices)}")
                
                if not response.choices:
                    raise RuntimeError("Azure OpenAI returned no choices")
                
                choice = response.choices[0]
                print(f"[LLM] finish_reason: {choice.finish_reason}")
                
                content = choice.message.content
                
                if content is None or content.strip() == '':
                    if choice.finish_reason == 'length':
                        raise RuntimeError(f"Input too large - no room for output (input ~{input_tokens} tokens)")
                    raise RuntimeError("Azure OpenAI returned empty content")
                
                print(f"[LLM] Success: {len(content)} chars generated")
                return content
                
            except Exception as e:
                last_error = e
                print(f"[LLM] Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Azure OpenAI failed after {max_retries + 1} attempts: {last_error}")


def generate_sow_markdown(
    selected_projects: list[dict[str, Any]],
    run_meta: dict[str, Any],
    options: SOWOptions,
    use_mock: bool = False
) -> tuple[str, SOWSummary]:
    """
    Generate SOW markdown using Azure OpenAI.
    
    Args:
        selected_projects: List of project dictionaries
        run_meta: Run metadata from discovery
        options: SOW generation options
        use_mock: If True, return mock data (for testing without API)
        
    Returns:
        Tuple of (markdown_content, summary)
    """
    # Compute metrics
    metrics = compute_metrics(selected_projects)
    
    # Build summary
    summary: SOWSummary = {
        'projects_count': len(selected_projects),
        'total_hours_low': round(metrics.total_hours_low, 1),
        'total_hours_high': round(metrics.total_hours_high, 1),
        'highest_bucket': metrics.highest_bucket,
        'bucket_distribution': metrics.bucket_distribution,
        'key_blockers': metrics.unique_blockers[:5],
        'data_gaps': metrics.data_gaps[:5]
    }
    
    if use_mock:
        # Return mock markdown for testing
        markdown = generate_mock_sow(selected_projects, run_meta, metrics, options)
        return markdown, summary
    
    # Use Azure OpenAI
    client = AzureOpenAIClient()
    
    # Build prompts
    user_prompt = build_user_prompt(run_meta, selected_projects, metrics, options)
    
    # Check token limit - if too large, use chunked approach
    estimated_tokens = len(user_prompt) // 4  # Rough estimate
    system_tokens = len(SYSTEM_PROMPT) // 4
    total_input_tokens = estimated_tokens + system_tokens
    
    print(f"[LLM] Estimated input tokens: {total_input_tokens} (user: {estimated_tokens}, system: {system_tokens})")
    print(f"[LLM] Projects in prompt: {len(selected_projects)}")
    
    # Use chunked approach for large requests or many projects
    # gpt-4o-mini: 128K context, 16K output - but we need room for output
    # Rule: if input > 8K tokens OR > 15 projects, use chunked approach
    if total_input_tokens > 8000 or len(selected_projects) > 15:
        print(f"[LLM] Using chunked approach (input tokens: {total_input_tokens}, projects: {len(selected_projects)})")
        try:
            markdown = generate_chunked_sow(client, run_meta, selected_projects, metrics, options)
        except Exception as e:
            print(f"[LLM] Chunked approach failed: {e}")
            print(f"[LLM] Falling back to mock generator")
            markdown = generate_mock_sow(selected_projects, run_meta, metrics, options)
    else:
        # Single call - only for small requests
        print(f"[LLM] Using single-call approach")
        try:
            markdown = client.generate_completion(SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            print(f"[LLM] Single-call failed: {e}")
            print(f"[LLM] Falling back to mock generator")
            markdown = generate_mock_sow(selected_projects, run_meta, metrics, options)
    
    # Clean up markdown (remove any code fences if model added them)
    markdown = markdown.strip()
    if markdown.startswith('```markdown'):
        markdown = markdown[11:]
    if markdown.startswith('```'):
        markdown = markdown[3:]
    if markdown.endswith('```'):
        markdown = markdown[:-3]
    
    return markdown.strip(), summary


def generate_chunked_sow(
    client: AzureOpenAIClient,
    run_meta: dict[str, Any],
    projects: list[dict[str, Any]],
    metrics: ComputedMetrics,
    options: SOWOptions
) -> str:
    """
    Generate SOW in chunks for large project sets.
    
    Strategy: Generate summary sections with metrics only (no full project list),
    then generate the project table separately.
    """
    print(f"[LLM] Chunked: Generating sections 1-5, 7-15 (summary)")
    
    # First call: Everything EXCEPT the project table (section 6)
    summary_prompt = f"""Generate a SOW document for GitLab → GitHub migration.
SKIP section 6 (Project Portfolio table) - just put "[PROJECT TABLE WILL BE INSERTED HERE]" placeholder.

## CONTEXT
- Client: {options.get('client_name', '[CLIENT]')}
- Target GitHub Org: {options.get('target_github_org', '[GITHUB ORG]')}
- GitLab: {run_meta.get('base_url', 'N/A')} / {run_meta.get('root_group', 'N/A')}
- Migration Mode: {options.get('migration_mode', 'phased')}
- Start Date: {options.get('timeline_start_date', 'TBD')}

## KEY METRICS
- Total Projects: {len(projects)} ({metrics.active_count} active, {metrics.archived_count} archived)
- Estimated Hours: {metrics.total_hours_low:.0f} - {metrics.total_hours_high:.0f}
- Buckets: S={metrics.bucket_distribution['S']}, M={metrics.bucket_distribution['M']}, L={metrics.bucket_distribution['L']}, XL={metrics.bucket_distribution['XL']}
- Highest Complexity: {metrics.highest_bucket}
- Projects with CI/CD: {metrics.ci_projects_count}
- Open MRs: {metrics.total_open_mrs}, Open Issues: {metrics.total_open_issues}
- Has Container Registry: {metrics.has_registry}
- Has GitLab Pages: {metrics.has_pages}

## TOP 5 RISKY PROJECTS
{json.dumps(metrics.risky_projects[:5], indent=2)}

## KEY BLOCKERS
{json.dumps(metrics.unique_blockers[:5])}

Generate ALL sections (1-15) but use placeholder for section 6."""

    summary_md = client.generate_completion(SYSTEM_PROMPT, summary_prompt, max_tokens=8000)
    
    print(f"[LLM] Chunked: Generating project table (section 6)")
    
    # Build project table manually (no LLM needed for this)
    table_rows = []
    for p in sorted(projects, key=lambda x: x['path_with_namespace']):
        est = p.get('estimate', {})
        facts = p.get('facts', {})
        bucket = est.get('bucket') or facts.get('migration_estimate', {}).get('bucket', 'S')
        hours_low = est.get('hours_low', 0) or 0
        hours_high = est.get('hours_high', 0) or 0
        confidence = est.get('confidence', '-')
        has_ci = '✓' if facts.get('has_ci') else '-'
        archived = '✓' if p.get('archived') else '-'
        open_mrs = facts.get('mr_counts', {}).get('open', 0) or 0
        open_issues = facts.get('issue_counts', {}).get('open', 0) or 0
        blockers = ', '.join((est.get('blockers', []) or [])[:2]) or '-'
        
        table_rows.append(
            f"| {p['path_with_namespace']} | {bucket} | {hours_low:.0f}–{hours_high:.0f} | "
            f"{confidence} | {has_ci} | {archived} | {open_mrs} | {open_issues} | {blockers} |"
        )
    
    project_table = f"""## 6. Project Portfolio Overview (Selected Projects)

| Project | Bucket | Hours (Low–High) | Confidence | CI | Archived | Open MRs | Open Issues | Key Blockers |
|---------|--------|------------------|------------|-----|----------|----------|-------------|--------------|
{chr(10).join(table_rows)}

**Portfolio Totals:**
- Total Hours: **{metrics.total_hours_low:.0f} – {metrics.total_hours_high:.0f}**
- Bucket Distribution: S: {metrics.bucket_distribution['S']}, M: {metrics.bucket_distribution['M']}, L: {metrics.bucket_distribution['L']}, XL: {metrics.bucket_distribution['XL']}
"""
    
    # Replace placeholder with actual table
    if "[PROJECT TABLE WILL BE INSERTED HERE]" in summary_md:
        final_md = summary_md.replace("[PROJECT TABLE WILL BE INSERTED HERE]", project_table)
    else:
        # Insert after section 5 if placeholder not found
        parts = summary_md.split("## 7")
        if len(parts) == 2:
            final_md = parts[0] + project_table + "\n\n## 7" + parts[1]
        else:
            final_md = summary_md + "\n\n" + project_table
    
    return final_md
    
    return first_half.strip() + "\n\n" + second_half.strip()


def generate_mock_sow(
    projects: list[dict[str, Any]],
    run_meta: dict[str, Any],
    metrics: ComputedMetrics,
    options: SOWOptions
) -> str:
    """Generate a mock SOW for testing without Azure OpenAI."""
    
    # Build project table rows
    table_rows = []
    for p in sorted(projects, key=lambda x: x['path_with_namespace']):
        est = p.get('estimate', {})
        facts = p.get('facts', {})
        bucket = est.get('bucket') or facts.get('migration_estimate', {}).get('bucket', 'S')
        hours_low = est.get('hours_low', 0)
        hours_high = est.get('hours_high', 0)
        confidence = est.get('confidence', '-')
        has_ci = '✓' if facts.get('has_ci') else '-'
        archived = '✓' if p.get('archived') else '-'
        open_mrs = facts.get('mr_counts', {}).get('open', 0)
        open_issues = facts.get('issue_counts', {}).get('open', 0)
        blockers = ', '.join(est.get('blockers', [])[:2]) or '-'
        
        table_rows.append(
            f"| {p['path_with_namespace']} | {bucket} | {hours_low:.0f}–{hours_high:.0f} | "
            f"{confidence} | {has_ci} | {archived} | {open_mrs} | {open_issues} | {blockers} |"
        )
    
    project_table = '\n'.join(table_rows)
    
    # Calculate timeline weeks
    avg_hours = (metrics.total_hours_low + metrics.total_hours_high) / 2
    weeks_needed = max(2, int(avg_hours / 40) + 1)
    
    start_date = options.get('timeline_start_date', datetime.now().strftime('%Y-%m-%d'))
    
    return f"""# Statement of Work (SOW) – GitLab → GitHub Migration

**Client:** {options.get('client_name', '[CLIENT NAME]')}  
**Target Organization:** {options.get('target_github_org', '[GITHUB ORG]')}  
**Document Date:** {datetime.now().strftime('%Y-%m-%d')}  
**Version:** 1.0

---

## 1. Executive Summary

This Statement of Work defines the scope, approach, and deliverables for migrating {len(projects)} GitLab repositories from **{run_meta.get('root_group', 'N/A')}** to GitHub Enterprise. The migration encompasses code repositories, CI/CD pipelines (GitLab CI to GitHub Actions), issues, merge requests, and associated metadata.

**Key Metrics:**
- **Total Projects:** {len(projects)} ({metrics.active_count} active, {metrics.archived_count} archived)
- **Estimated Effort:** {metrics.total_hours_low:.0f} – {metrics.total_hours_high:.0f} hours
- **Complexity Distribution:** S: {metrics.bucket_distribution['S']}, M: {metrics.bucket_distribution['M']}, L: {metrics.bucket_distribution['L']}, XL: {metrics.bucket_distribution['XL']}

---

## 2. Background & Context

The client currently operates a GitLab instance at **{run_meta.get('base_url', 'N/A')}** with the root group **{run_meta.get('root_group', 'N/A')}**. This migration aims to consolidate source code management onto GitHub Enterprise while preserving history, workflows, and development practices.

**Current State:**
- {len(projects)} repositories identified for migration
- {metrics.ci_projects_count} projects with CI/CD pipelines requiring conversion
- {metrics.total_open_mrs} open merge requests to address
- {metrics.total_open_issues} open issues to migrate

---

## 3. Objectives

1. Migrate all selected repositories with full git history to GitHub
2. Convert GitLab CI/CD pipelines to GitHub Actions workflows
3. Migrate issues and merge requests (or define cutover strategy)
4. Establish branch protection rules and CODEOWNERS
5. Configure GitHub-native integrations (Actions, Pages, Packages)
6. Document migration runbooks and provide knowledge transfer

---

## 4. In-Scope

The following items are included in this migration:

- **Code & History:** All branches, tags, and commit history
- **CI/CD:** GitLab CI YAML → GitHub Actions conversion
- **Issues:** Open and closed issues with labels and comments
- **Merge Requests:** MR history (as reference) or conversion to PRs
- **Branch Protection:** Protected branch rules and CODEOWNERS
- **Secrets:** CI/CD variables → GitHub Secrets (manual recreation)
- **Webhooks:** Reconfiguration for GitHub events
- **Wiki:** Migration of GitLab wiki repositories
{"- **Container Registry:** Migration to GitHub Container Registry (ghcr.io)" if metrics.has_registry else ""}
{"- **GitLab Pages:** Conversion to GitHub Pages" if metrics.has_pages else ""}

---

## 5. Out-of-Scope

- GitLab instance decommissioning
- Third-party integration reconfiguration (beyond webhooks)
- Custom GitLab CI runner infrastructure setup on GitHub side
- Historical pipeline run logs migration
- User account provisioning in GitHub

---

## 6. Project Portfolio Overview (Selected Projects)

| Project | Bucket | Hours (Low–High) | Confidence | CI | Archived | Open MRs | Open Issues | Key Blockers |
|---------|--------|------------------|------------|-----|----------|----------|-------------|--------------|
{project_table}

**Portfolio Totals:**
- Total Hours: **{metrics.total_hours_low:.0f} – {metrics.total_hours_high:.0f}**
- Bucket Distribution: S: {metrics.bucket_distribution['S']}, M: {metrics.bucket_distribution['M']}, L: {metrics.bucket_distribution['L']}, XL: {metrics.bucket_distribution['XL']}

**Top 3 High-Risk Projects:**
{chr(10).join([f"1. **{p['path']}** - {p['hours_high']:.0f}h max, reasons: {', '.join(p['reasons'][:2])}" for p in metrics.risky_projects[:3]])}

---

## 7. Approach & Methodology

### Migration Strategy: {options.get('migration_mode', 'Phased').title()}

**Wave 0 - Foundation (Week 1)**
- GitHub organization setup and team structure
- Repository naming conventions and visibility settings
- Branch protection templates
- GitHub Actions self-hosted runner setup (if applicable)

**Wave 1 - Pilot ({metrics.bucket_distribution['S']} S-bucket projects)**
- Migrate simple repositories with minimal CI
- Validate migration scripts and procedures
- Establish baseline quality gates

**Wave 2 - Medium Complexity ({metrics.bucket_distribution['M']} M-bucket projects)**
- CI/CD conversion with testing
- Issues and MR migration strategy execution
- Protected branches and CODEOWNERS

**Wave 3 - High Complexity ({metrics.bucket_distribution['L'] + metrics.bucket_distribution['XL']} L/XL-bucket projects)**
- Complex CI pipeline conversions
- Registry and Pages migration
- Extended validation and cutover planning

### Default Branch Strategy
- Rename `master` → `main` where applicable
- Update CI/CD references
- Communicate changes to development teams

---

## 8. Detailed Work Breakdown (WBS)

### A. Discovery Validation
- Review and confirm project list
- Validate access permissions
- Identify data gaps

### B. Repository Migration
- Git history migration using gh-cli/git
- LFS object migration (if applicable)
- Submodule reference updates

### C. Issues/MRs Strategy
- Migrate open issues with labels
- Close/document open MRs pre-migration
- Set up issue templates

### D. CI/CD Conversion
- Analyze GitLab CI YAML files
- Convert to GitHub Actions workflows
- Test pipeline execution

### E. Runner Strategy
- Evaluate GitHub-hosted vs self-hosted
- Configure runner groups and labels
- Migrate build scripts

{"### F. GitLab Pages → GitHub Pages" if metrics.has_pages else ""}
{"- Configure GitHub Pages settings" if metrics.has_pages else ""}
{"- Migrate static content and build workflow" if metrics.has_pages else ""}

{"### G. Container Registry → GHCR" if metrics.has_registry else ""}
{"- Export images from GitLab Registry" if metrics.has_registry else ""}
{"- Push to GitHub Container Registry" if metrics.has_registry else ""}
{"- Update CI/CD image references" if metrics.has_registry else ""}

### H. Verification & Cutover
- Run automated validation checks
- Perform manual smoke tests
- Execute cutover with stakeholder approval

### I. Documentation & Handover
- Migration runbook
- GitHub Actions best practices guide
- Knowledge transfer sessions

---

## 9. Timeline (Detailed)

| Week | Dates | Phase | Activities | Milestones |
|------|-------|-------|------------|------------|
| 1 | {start_date} | Wave 0 | Setup & Planning | GitHub org ready |
| 2-3 | +1-2 weeks | Wave 1 | Pilot migrations (S) | First repos live |
| 4-5 | +3-4 weeks | Wave 2 | Medium complexity (M) | CI/CD validated |
| 6-{weeks_needed} | +5-{weeks_needed-1} weeks | Wave 3 | High complexity (L/XL) | Full migration |
| {weeks_needed+1} | Final | Cutover | Validation & Handover | Project complete |

**Total Duration:** ~{weeks_needed + 1} weeks

---

## 10. Roles & Responsibilities (RACI-lite)

| Activity | Vendor | Client |
|----------|--------|--------|
| Migration execution | R | I |
| Access provisioning | C | R |
| CI/CD conversion | R | C |
| Validation testing | R | A |
| Cutover approval | I | R |
| Documentation | R | A |

*R = Responsible, A = Accountable, C = Consulted, I = Informed*

---

## 11. Assumptions & Dependencies

### Assumptions
- Client provides admin access to GitLab and GitHub
- Standard business hours availability for coordination
- Development teams notified of migration schedule
- No active development freeze required during migration

### Dependencies
- GitHub organization provisioned with appropriate licenses
- Network connectivity between environments
- CI/CD secrets documented for recreation

### Data Gaps
{chr(10).join([f"- {gap}" for gap in (metrics.data_gaps + metrics.unique_unknowns)[:5]]) or "- None identified"}

---

## 12. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| CI/CD conversion complexity | High | Medium | Phased approach, extensive testing |
| Open MR conflicts | Medium | Medium | Close or merge MRs before migration |
| Self-hosted runner dependencies | High | {'High' if metrics.has_self_hosted_runners else 'Low'} | Document runner requirements early |
| Access permission gaps | Medium | Medium | Request elevated access proactively |
| Large repository timeouts | Medium | Low | Use git-lfs, chunked migration |

**Key Blockers Identified:**
{chr(10).join([f"- {b}" for b in metrics.unique_blockers[:5]]) or "- None"}

---

## 13. Deliverables

1. **Migrated Repositories** - All {len(projects)} projects in GitHub
2. **GitHub Actions Workflows** - Converted CI/CD pipelines for {metrics.ci_projects_count} projects
3. **Migration Report** - Summary of migrated assets and validation results
4. **Runbook** - Step-by-step migration procedures for future use
5. **Knowledge Transfer** - 2-hour session with development team

---

## 14. Acceptance Criteria

- [ ] All selected repositories migrated with full git history
- [ ] GitHub Actions workflows execute successfully
- [ ] Branch protection rules configured per requirements
- [ ] Issues migrated with labels and assignees
- [ ] Documentation delivered and reviewed
- [ ] Knowledge transfer completed
- [ ] Stakeholder sign-off obtained

---

## 15. Appendix

### A. Data Gaps
The following information could not be retrieved during discovery (typically due to permission restrictions):
{chr(10).join([f"- {gap}" for gap in metrics.data_gaps]) or "- None"}

### B. Projects with Unknown CI Status
Projects where CI configuration could not be validated:
{chr(10).join([f"- {p['path_with_namespace']}" for p in projects if p.get('facts', {}).get('has_ci') == 'unknown'][:10]) or "- None"}

### C. Glossary
- **Bucket:** Complexity classification (S=Small, M=Medium, L=Large, XL=Extra Large)
- **CI/CD:** Continuous Integration/Continuous Deployment
- **MR:** Merge Request (GitLab equivalent of GitHub Pull Request)
- **GHCR:** GitHub Container Registry

---

*Document generated by GitLab Discovery Agent*  
*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""


# ============== Main Entry Point ==============

def generate_sow(request: SOWRequest, use_mock: bool = False) -> SOWResponse:
    """
    Main entry point for SOW generation.
    
    Args:
        request: SOW request with selected projects and options
        use_mock: If True, use mock generator instead of Azure OpenAI
        
    Returns:
        SOWResponse with markdown, filename, and summary
    """
    discovery = request['discovery']
    selected_ids = set(request['selected_project_ids'])
    options = request.get('sow_options', {})
    
    # Validate
    if not selected_ids:
        raise ValueError("No projects selected. Please select at least one project.")
    
    # Filter projects
    all_projects = discovery.get('projects', [])
    selected_projects = [p for p in all_projects if p['id'] in selected_ids]
    
    if not selected_projects:
        raise ValueError(f"None of the selected project IDs were found in discovery data.")
    
    # Get run metadata
    run_meta = discovery.get('run', {})
    
    # Generate markdown
    markdown, summary = generate_sow_markdown(
        selected_projects=selected_projects,
        run_meta=run_meta,
        options=options,
        use_mock=use_mock
    )
    
    # Generate filename
    root_group = run_meta.get('root_group', 'migration').replace('/', '-')
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"SOW_{root_group}_{date_str}.md"
    
    return {
        'markdown': markdown,
        'filename': filename,
        'summary': summary
    }
