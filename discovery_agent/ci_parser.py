"""CI Profile Parser - Extract features from .gitlab-ci.yml content."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, TypedDict


class CIFeatures(TypedDict):
    """Features detected in GitLab CI configuration."""
    include: bool
    services: bool
    artifacts: bool
    cache: bool
    rules: bool
    needs: bool
    parallel: bool
    trigger: bool
    environments: bool
    manual_jobs: bool
    variables: bool
    extends: bool
    matrix: bool


class RunnerHints(TypedDict):
    """Hints about runner requirements."""
    uses_tags: bool
    possible_self_hosted: bool
    docker_in_docker: bool
    privileged: bool


@dataclass
class CIProfile:
    """Complete CI profile for a project."""
    present: bool | str = "unknown"
    features: CIFeatures = field(default_factory=lambda: CIFeatures(
        include=False,
        services=False,
        artifacts=False,
        cache=False,
        rules=False,
        needs=False,
        parallel=False,
        trigger=False,
        environments=False,
        manual_jobs=False,
        variables=False,
        extends=False,
        matrix=False,
    ))
    runner_hints: RunnerHints = field(default_factory=lambda: RunnerHints(
        uses_tags=False,
        possible_self_hosted=False,
        docker_in_docker=False,
        privileged=False,
    ))
    job_count: int = 0
    stage_count: int = 0
    include_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "present": self.present,
            "features": dict(self.features),
            "runner_hints": dict(self.runner_hints),
            "job_count": self.job_count,
            "stage_count": self.stage_count,
            "include_count": self.include_count,
        }


# Reserved GitLab CI keys (not job names)
RESERVED_KEYS = {
    'default', 'include', 'stages', 'variables', 'workflow',
    'before_script', 'after_script', 'image', 'services', 'cache',
    'pages', '.pre', '.post'
}


def parse_ci_content(content: str) -> CIProfile:
    """
    Parse .gitlab-ci.yml content and extract CI profile.
    
    Uses regex-based parsing to avoid YAML library dependency issues
    and handle malformed YAML gracefully.
    
    Args:
        content: Raw content of .gitlab-ci.yml file
        
    Returns:
        CIProfile with detected features
    """
    profile = CIProfile(present=True)
    
    if not content or not content.strip():
        profile.present = False
        return profile
    
    lines = content.split('\n')
    
    # Track top-level keys
    top_level_keys: set[str] = set()
    current_job: str | None = None
    jobs: set[str] = set()
    stages: set[str] = set()
    
    for line in lines:
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Detect top-level keys (no leading whitespace)
        if not line.startswith((' ', '\t')) and ':' in line:
            key = line.split(':')[0].strip()
            if key and not key.startswith('.'):
                top_level_keys.add(key)
                if key not in RESERVED_KEYS and not key.startswith('.'):
                    jobs.add(key)
                    current_job = key
            elif key.startswith('.'):
                # Template/hidden job
                current_job = key
        
        # Feature detection via patterns
        lower_line = stripped.lower()
        
        # Include detection
        if stripped.startswith('include:') or re.match(r'^include\s*:', stripped):
            profile.features['include'] = True
        
        # Count includes
        if re.match(r'^\s*-\s*(local|remote|project|template|file):', stripped):
            profile.include_count += 1
        if re.match(r'^\s*-\s+[\'"]?/', stripped):  # Simple local include
            profile.include_count += 1
        
        # Services detection
        if 'services:' in stripped:
            profile.features['services'] = True
        
        # Docker-in-docker detection
        if 'docker:' in lower_line and ('dind' in lower_line or 'docker' in lower_line):
            profile.runner_hints['docker_in_docker'] = True
            profile.runner_hints['possible_self_hosted'] = True
        
        # Privileged detection
        if 'privileged' in lower_line and 'true' in lower_line:
            profile.runner_hints['privileged'] = True
            profile.runner_hints['possible_self_hosted'] = True
        
        # Artifacts detection
        if 'artifacts:' in stripped:
            profile.features['artifacts'] = True
        
        # Cache detection
        if re.match(r'^\s*cache:', stripped):
            profile.features['cache'] = True
        
        # Rules detection (modern)
        if re.match(r'^\s*rules:', stripped):
            profile.features['rules'] = True
        
        # only/except detection (legacy, but still rules)
        if re.match(r'^\s*(only|except):', stripped):
            profile.features['rules'] = True
        
        # Needs detection (DAG)
        if re.match(r'^\s*needs:', stripped):
            profile.features['needs'] = True
        
        # Parallel detection
        if re.match(r'^\s*parallel:', stripped):
            profile.features['parallel'] = True
        
        # Matrix detection
        if 'matrix:' in stripped:
            profile.features['matrix'] = True
            profile.features['parallel'] = True
        
        # Trigger detection (multi-project pipelines)
        if re.match(r'^\s*trigger:', stripped):
            profile.features['trigger'] = True
        
        # Environment detection
        if re.match(r'^\s*environment:', stripped):
            profile.features['environments'] = True
        
        # Manual jobs detection
        if re.match(r'^\s*when:\s*manual', stripped):
            profile.features['manual_jobs'] = True
        
        # Variables detection
        if stripped.startswith('variables:'):
            profile.features['variables'] = True
        
        # Extends detection
        if re.match(r'^\s*extends:', stripped):
            profile.features['extends'] = True
        
        # Tags detection
        if re.match(r'^\s*tags:', stripped):
            profile.runner_hints['uses_tags'] = True
            profile.runner_hints['possible_self_hosted'] = True
        
        # Stages detection
        if stripped.startswith('stages:'):
            # Count stages in subsequent lines
            pass
        if re.match(r'^\s+-\s+\w+', stripped) and 'stages:' in '\n'.join(lines[:lines.index(line)]):
            stage_match = re.match(r'^\s+-\s+(\w+)', stripped)
            if stage_match:
                stages.add(stage_match.group(1))
    
    # Set counts
    profile.job_count = len(jobs)
    profile.stage_count = len(stages) if stages else (1 if jobs else 0)
    
    # Ensure include_count is at least 1 if include feature detected
    if profile.features['include'] and profile.include_count == 0:
        profile.include_count = 1
    
    return profile


def get_ci_complexity_score(profile: CIProfile) -> tuple[int, list[str]]:
    """
    Calculate CI complexity score based on features.
    
    Returns:
        Tuple of (score 0-50, list of contributing factors)
    """
    score = 0
    factors = []
    
    if profile.present != True:
        return 0, []
    
    # Base score for having CI
    score += 5
    factors.append("Has GitLab CI configuration")
    
    # Feature scores
    if profile.features['include']:
        score += 8
        factors.append(f"Uses includes ({profile.include_count} includes)")
    
    if profile.features['services']:
        score += 5
        factors.append("Uses services")
    
    if profile.features['artifacts']:
        score += 3
        factors.append("Uses artifacts")
    
    if profile.features['cache']:
        score += 2
        factors.append("Uses cache")
    
    if profile.features['rules']:
        score += 5
        factors.append("Uses rules/only/except")
    
    if profile.features['needs']:
        score += 7
        factors.append("Uses DAG (needs)")
    
    if profile.features['parallel']:
        score += 5
        factors.append("Uses parallel/matrix")
    
    if profile.features['trigger']:
        score += 10
        factors.append("Uses multi-project triggers")
    
    if profile.features['environments']:
        score += 5
        factors.append("Uses environments")
    
    if profile.features['manual_jobs']:
        score += 3
        factors.append("Has manual jobs")
    
    if profile.features['extends']:
        score += 4
        factors.append("Uses extends (templates)")
    
    # Runner hints
    if profile.runner_hints['uses_tags']:
        score += 8
        factors.append("Uses custom runner tags")
    
    if profile.runner_hints['docker_in_docker']:
        score += 10
        factors.append("Uses Docker-in-Docker")
    
    if profile.runner_hints['privileged']:
        score += 8
        factors.append("Requires privileged mode")
    
    # Job count factor
    if profile.job_count > 20:
        score += 10
        factors.append(f"Large pipeline ({profile.job_count} jobs)")
    elif profile.job_count > 10:
        score += 5
        factors.append(f"Medium pipeline ({profile.job_count} jobs)")
    elif profile.job_count > 5:
        score += 2
        factors.append(f"Small pipeline ({profile.job_count} jobs)")
    
    return min(score, 50), factors  # Cap at 50 for CI portion
