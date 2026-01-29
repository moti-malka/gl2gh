"""Tests for CI parsing and migration scoring."""

import pytest

from discovery_agent.ci_parser import (
    parse_ci_content,
    get_ci_complexity_score,
    CIProfile,
)
from discovery_agent.scoring import (
    calculate_migration_score,
    estimate_bucket_from_score,
    get_bucket_description,
    RepoProfile,
)


class TestCIParser:
    """Test CI content parsing."""
    
    def test_parse_empty_content(self):
        """Empty content returns empty profile."""
        result = parse_ci_content("")
        assert result.features["include"] is False
        assert result.features["services"] is False
        assert result.runner_hints["uses_tags"] is False
    
    def test_parse_simple_ci(self):
        """Simple CI file is parsed correctly."""
        content = """
stages:
  - build
  - test

build:
  stage: build
  script:
    - echo "Building..."

test:
  stage: test
  script:
    - pytest
"""
        result = parse_ci_content(content)
        # Simple CI has no special features
        assert result.features["include"] is False
        assert result.features["services"] is False
    
    def test_parse_ci_with_include(self):
        """Include directive is detected."""
        content = """
include:
  - local: '.gitlab/ci/build.yml'
  - template: 'Docker.gitlab-ci.yml'

stages:
  - build
"""
        result = parse_ci_content(content)
        assert result.features["include"] is True
    
    def test_parse_ci_with_services(self):
        """Services are detected."""
        content = """
test:
  services:
    - postgres:13
    - redis:latest
  script:
    - pytest
"""
        result = parse_ci_content(content)
        assert result.features["services"] is True
    
    def test_parse_ci_with_artifacts(self):
        """Artifacts configuration is detected."""
        content = """
build:
  artifacts:
    paths:
      - dist/
    expire_in: 1 week
"""
        result = parse_ci_content(content)
        assert result.features["artifacts"] is True
    
    def test_parse_ci_with_cache(self):
        """Cache configuration is detected."""
        content = """
.cache: &global_cache
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - .npm/
      - node_modules/
"""
        result = parse_ci_content(content)
        assert result.features["cache"] is True
    
    def test_parse_ci_with_rules(self):
        """Rules are detected."""
        content = """
deploy:
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: manual
"""
        result = parse_ci_content(content)
        assert result.features["rules"] is True
    
    def test_parse_ci_with_needs(self):
        """Needs (DAG) is detected."""
        content = """
test:
  needs: ["build"]
  script:
    - pytest
"""
        result = parse_ci_content(content)
        assert result.features["needs"] is True
    
    def test_parse_ci_with_parallel(self):
        """Parallel jobs are detected."""
        content = """
test:
  parallel: 5
  script:
    - pytest
"""
        result = parse_ci_content(content)
        assert result.features["parallel"] is True
    
    def test_parse_ci_with_trigger(self):
        """Trigger (child pipelines) is detected."""
        content = """
deploy:
  trigger:
    include:
      - local: deploy/ci.yml
    strategy: depend
"""
        result = parse_ci_content(content)
        assert result.features["trigger"] is True
    
    def test_parse_ci_with_environments(self):
        """Environment deployments are detected."""
        content = """
deploy_prod:
  environment:
    name: production
    url: https://example.com
"""
        result = parse_ci_content(content)
        assert result.features["environments"] is True
    
    def test_parse_ci_with_manual_jobs(self):
        """Manual jobs are detected."""
        content = """
deploy:
  when: manual
  script:
    - ./deploy.sh
"""
        result = parse_ci_content(content)
        assert result.features["manual_jobs"] is True
    
    def test_parse_ci_with_extends(self):
        """Extends are detected."""
        content = """
.base:
  script:
    - echo "base"

job:
  extends: .base
"""
        result = parse_ci_content(content)
        assert result.features["extends"] is True
    
    def test_parse_ci_with_matrix(self):
        """Matrix builds are detected."""
        content = """
test:
  parallel:
    matrix:
      - PYTHON: ["3.9", "3.10", "3.11"]
"""
        result = parse_ci_content(content)
        assert result.features["matrix"] is True
    
    def test_parse_runner_hints_tags(self):
        """Runner tags are detected."""
        content = """
build:
  tags:
    - docker
    - linux
"""
        result = parse_ci_content(content)
        assert result.runner_hints["uses_tags"] is True
    
    def test_parse_runner_hints_self_hosted(self):
        """Self-hosted runner hints are detected."""
        content = """
build:
  tags:
    - self-hosted
    - my-runner
"""
        result = parse_ci_content(content)
        assert result.runner_hints["uses_tags"] is True
        assert result.runner_hints["possible_self_hosted"] is True
    
    def test_parse_runner_hints_dind(self):
        """Docker-in-Docker is detected."""
        content = """
build:
  services:
    - docker:dind
  script:
    - docker build .
"""
        result = parse_ci_content(content)
        assert result.runner_hints["docker_in_docker"] is True
    
    def test_parse_runner_hints_privileged(self):
        """Privileged mode is detected."""
        content = """
build:
  image: docker:latest
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_DRIVER: overlay2
  services:
    - name: docker:dind
      privileged: true
"""
        result = parse_ci_content(content)
        # privileged in the YAML context
        assert result.runner_hints["docker_in_docker"] is True


class TestCIComplexityScore:
    """Test CI complexity scoring."""
    
    def test_empty_features_zero_score(self):
        """Empty features with no CI gives zero score."""
        features = {k: False for k in [
            "include", "services", "artifacts", "cache", "rules",
            "needs", "parallel", "trigger", "environments", "manual_jobs",
            "variables", "extends", "matrix"
        ]}
        runner_hints = {k: False for k in [
            "uses_tags", "possible_self_hosted", "docker_in_docker", "privileged"
        ]}
        
        # present=False means no CI
        profile = CIProfile(present=False, features=features, runner_hints=runner_hints)
        score, factors = get_ci_complexity_score(profile)
        assert score == 0
        assert factors == []
    
    def test_minimal_ci_base_score(self):
        """Minimal CI file with no features gets base score."""
        features = {k: False for k in [
            "include", "services", "artifacts", "cache", "rules",
            "needs", "parallel", "trigger", "environments", "manual_jobs",
            "variables", "extends", "matrix"
        ]}
        runner_hints = {k: False for k in [
            "uses_tags", "possible_self_hosted", "docker_in_docker", "privileged"
        ]}
        
        # present=True means CI exists
        profile = CIProfile(present=True, features=features, runner_hints=runner_hints)
        score, factors = get_ci_complexity_score(profile)
        assert score == 5  # Base score for having CI
        assert len(factors) == 1
    
    def test_include_adds_points(self):
        """Include feature adds points."""
        features = {"include": True, "services": False, "artifacts": False, 
                   "cache": False, "rules": False, "needs": False, "parallel": False,
                   "trigger": False, "environments": False, "manual_jobs": False,
                   "variables": False, "extends": False, "matrix": False}
        runner_hints = {"uses_tags": False, "possible_self_hosted": False,
                       "docker_in_docker": False, "privileged": False}
        
        profile = CIProfile(present=True, features=features, runner_hints=runner_hints)
        score, factors = get_ci_complexity_score(profile)
        assert score > 5  # More than base score
        assert any("include" in f.lower() for f in factors)
    
    def test_complex_ci_high_score(self):
        """Complex CI with many features scores high."""
        features = {
            "include": True,
            "services": True,
            "artifacts": True,
            "cache": True,
            "rules": True,
            "needs": True,
            "parallel": True,
            "trigger": True,
            "environments": True,
            "manual_jobs": True,
            "variables": True,
            "extends": True,
            "matrix": True,
        }
        runner_hints = {
            "uses_tags": True,
            "possible_self_hosted": True,
            "docker_in_docker": True,
            "privileged": True,
        }
        
        profile = CIProfile(present=True, features=features, runner_hints=runner_hints)
        score, factors = get_ci_complexity_score(profile)
        assert score >= 30  # Should be relatively high
        assert len(factors) > 5
    
    def test_score_capped_at_50(self):
        """Score is capped at 50."""
        # Even with everything enabled, score shouldn't exceed 50
        features = {k: True for k in [
            "include", "services", "artifacts", "cache", "rules",
            "needs", "parallel", "trigger", "environments", "manual_jobs",
            "variables", "extends", "matrix"
        ]}
        runner_hints = {k: True for k in [
            "uses_tags", "possible_self_hosted", "docker_in_docker", "privileged"
        ]}
        
        profile = CIProfile(present=True, features=features, runner_hints=runner_hints)
        score, _ = get_ci_complexity_score(profile)
        assert score <= 50


class TestMigrationScoring:
    """Test migration effort scoring."""
    
    def test_simple_project_low_score(self):
        """Simple project gets low score."""
        repo_profile = RepoProfile(
            branches_count=1,
            tags_count=0,
            has_submodules=False,
            has_lfs=False,
        )
        
        result = calculate_migration_score(
            repo_profile=repo_profile,
            ci_score=0,
            ci_factors=[],
            mr_counts={"open": 0, "merged": 5, "closed": 1, "total": 6},
            issue_counts={"open": 0, "closed": 2, "total": 2},
        )
        
        assert result["work_score"] < 20
        assert result["bucket"] == "S"
    
    def test_complex_project_high_score(self):
        """Complex project gets high score."""
        repo_profile = RepoProfile(
            branches_count=100,
            tags_count=200,
            has_submodules=True,
            has_lfs=True,
        )
        
        result = calculate_migration_score(
            repo_profile=repo_profile,
            ci_score=40,
            ci_factors=["Uses include", "Uses services", "Complex rules"],
            mr_counts={"open": 100, "merged": 2000, "closed": 500, "total": 2600},
            issue_counts={"open": 200, "closed": 1500, "total": 1700},
            has_wiki=True,
        )
        
        assert result["work_score"] >= 50
        assert result["bucket"] in ("L", "XL")
        assert len(result["drivers"]) > 3
    
    def test_archived_reduces_score(self):
        """Archived projects get reduced score."""
        repo_profile = RepoProfile(
            branches_count=50,
            tags_count=100,
            has_submodules=True,
            has_lfs=True,
        )
        
        # Without archived
        result_active = calculate_migration_score(
            repo_profile=repo_profile,
            ci_score=30,
            ci_factors=["Complex CI"],
            mr_counts={"open": 50, "merged": 500, "closed": 100, "total": 650},
            issue_counts={"open": 50, "closed": 500, "total": 550},
            archived=False,
        )
        
        # With archived
        result_archived = calculate_migration_score(
            repo_profile=repo_profile,
            ci_score=30,
            ci_factors=["Complex CI"],
            mr_counts={"open": 50, "merged": 500, "closed": 100, "total": 650},
            issue_counts={"open": 50, "closed": 500, "total": 550},
            archived=True,
        )
        
        assert result_archived["work_score"] < result_active["work_score"]
        assert "Archived" in result_archived["drivers"][0]
    
    def test_unknown_values_handled(self):
        """Unknown values don't crash scoring."""
        repo_profile = RepoProfile(
            branches_count="unknown",
            tags_count="unknown",
            has_submodules="unknown",
            has_lfs="unknown",
        )
        
        result = calculate_migration_score(
            repo_profile=repo_profile,
            ci_score=10,
            ci_factors=["Basic CI"],
            mr_counts="unknown",
            issue_counts="unknown",
        )
        
        # Should still produce valid result
        assert 0 <= result["work_score"] <= 100
        assert result["bucket"] in ("S", "M", "L", "XL")
    
    def test_bucket_thresholds(self):
        """Test bucket assignment thresholds."""
        assert estimate_bucket_from_score(0) == "S"
        assert estimate_bucket_from_score(20) == "S"
        assert estimate_bucket_from_score(21) == "M"
        assert estimate_bucket_from_score(45) == "M"
        assert estimate_bucket_from_score(46) == "L"
        assert estimate_bucket_from_score(70) == "L"
        assert estimate_bucket_from_score(71) == "XL"
        assert estimate_bucket_from_score(100) == "XL"
    
    def test_bucket_descriptions(self):
        """Bucket descriptions are provided."""
        for bucket in ("S", "M", "L", "XL"):
            desc = get_bucket_description(bucket)
            assert desc != "Unknown"
            assert len(desc) > 10
    
    def test_submodules_add_score(self):
        """Submodules add to score."""
        base_profile = RepoProfile(
            branches_count=5,
            tags_count=5,
            has_submodules=False,
            has_lfs=False,
        )
        
        submodule_profile = RepoProfile(
            branches_count=5,
            tags_count=5,
            has_submodules=True,
            has_lfs=False,
        )
        
        result_no_sub = calculate_migration_score(
            repo_profile=base_profile,
            ci_score=0,
            ci_factors=[],
            mr_counts={"open": 0, "merged": 0, "closed": 0, "total": 0},
            issue_counts={"open": 0, "closed": 0, "total": 0},
        )
        
        result_with_sub = calculate_migration_score(
            repo_profile=submodule_profile,
            ci_score=0,
            ci_factors=[],
            mr_counts={"open": 0, "merged": 0, "closed": 0, "total": 0},
            issue_counts={"open": 0, "closed": 0, "total": 0},
        )
        
        assert result_with_sub["work_score"] > result_no_sub["work_score"]
        assert any("submodule" in d.lower() for d in result_with_sub["drivers"])
    
    def test_lfs_adds_score(self):
        """LFS adds to score."""
        base_profile = RepoProfile(
            branches_count=5,
            tags_count=5,
            has_submodules=False,
            has_lfs=False,
        )
        
        lfs_profile = RepoProfile(
            branches_count=5,
            tags_count=5,
            has_submodules=False,
            has_lfs=True,
        )
        
        result_no_lfs = calculate_migration_score(
            repo_profile=base_profile,
            ci_score=0,
            ci_factors=[],
            mr_counts={"open": 0, "merged": 0, "closed": 0, "total": 0},
            issue_counts={"open": 0, "closed": 0, "total": 0},
        )
        
        result_with_lfs = calculate_migration_score(
            repo_profile=lfs_profile,
            ci_score=0,
            ci_factors=[],
            mr_counts={"open": 0, "merged": 0, "closed": 0, "total": 0},
            issue_counts={"open": 0, "closed": 0, "total": 0},
        )
        
        assert result_with_lfs["work_score"] > result_no_lfs["work_score"]
        assert any("lfs" in d.lower() for d in result_with_lfs["drivers"])
    
    def test_score_deterministic(self):
        """Same inputs produce same outputs."""
        repo_profile = RepoProfile(
            branches_count=25,
            tags_count=50,
            has_submodules=True,
            has_lfs=False,
        )
        
        results = []
        for _ in range(3):
            result = calculate_migration_score(
                repo_profile=repo_profile,
                ci_score=20,
                ci_factors=["Uses include", "Uses services"],
                mr_counts={"open": 10, "merged": 100, "closed": 20, "total": 130},
                issue_counts={"open": 5, "closed": 50, "total": 55},
            )
            results.append(result)
        
        # All results should be identical
        assert all(r["work_score"] == results[0]["work_score"] for r in results)
        assert all(r["bucket"] == results[0]["bucket"] for r in results)
