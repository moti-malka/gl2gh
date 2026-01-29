"""Integration tests for Transform Agent with complex scenarios"""

import pytest
import json
from pathlib import Path
from app.agents.transform_agent import TransformAgent


class TestTransformAgentIntegration:
    """Integration tests for complete transformation workflows"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.agent = TransformAgent()
    
    @pytest.mark.asyncio
    async def test_complex_gitlab_ci_transformation(self, tmp_path):
        """Test transformation of a complex GitLab CI configuration"""
        
        # Complex GitLab CI with many features
        gitlab_ci_yaml = """
stages:
  - build
  - test
  - deploy

variables:
  DATABASE_URL: postgres://localhost/test
  DOCKER_DRIVER: overlay2

before_script:
  - echo "Global before script"
  - apt-get update

.test_template:
  script:
    - pytest
  artifacts:
    paths:
      - coverage/
    reports:
      junit: report.xml

build:
  stage: build
  image: python:3.9
  services:
    - postgres:13
    - redis:6
  script:
    - pip install -r requirements.txt
    - python setup.py build
  cache:
    key: pip-cache
    paths:
      - .pip-cache/
  artifacts:
    name: build-artifacts
    paths:
      - dist/
      - build/
  only:
    - branches
  except:
    - tags
  tags:
    - docker

unit-tests:
  stage: test
  extends: .test_template
  needs:
    - build
  variables:
    PYTEST_ARGS: "-v --cov"
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: always
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: always

integration-tests:
  stage: test
  script:
    - pytest tests/integration
  needs:
    - build
  only:
    - merge_requests
    - main

deploy-staging:
  stage: deploy
  script:
    - ./deploy.sh staging
  environment:
    name: staging
    url: https://staging.example.com
  when: manual
  only:
    - main

deploy-production:
  stage: deploy
  script:
    - ./deploy.sh production
  environment:
    name: production
    url: https://production.example.com
  when: manual
  only:
    - tags
  needs:
    - build
    - unit-tests
    - integration-tests
"""
        
        # Sample users data
        gitlab_users = [
            {"id": 1, "username": "alice", "email": "alice@example.com", "name": "Alice Smith"},
            {"id": 2, "username": "bob", "email": "bob@example.com", "name": "Bob Jones"},
            {"id": 3, "username": "charlie", "email": "charlie@other.com", "name": "Charlie Brown"}
        ]
        
        github_org_members = [
            {"login": "alice", "id": 101, "email": "alice@example.com", "name": "Alice Smith"},
            {"login": "bob-jones", "id": 102, "email": "bob@example.com", "name": "Bob Jones"}
        ]
        
        # Sample issues
        issues = [
            {
                "id": 1,
                "iid": 10,
                "title": "Fix login bug",
                "description": "The login page doesn't work. @alice can you take a look? Related to #5",
                "author": {"username": "bob", "name": "Bob Jones"},
                "created_at": "2024-01-15T10:00:00Z",
                "labels": ["bug", "high-priority"],
                "assignees": [{"username": "alice"}],
                "state": "opened",
                "web_url": "https://gitlab.com/test/project/issues/10"
            }
        ]
        
        # Sample merge requests
        merge_requests = [
            {
                "id": 2,
                "iid": 5,
                "title": "Add user authentication",
                "description": "This MR adds JWT authentication. Closes #10",
                "author": {"username": "alice", "name": "Alice Smith"},
                "created_at": "2024-01-20T10:00:00Z",
                "source_branch": "feature/auth",
                "target_branch": "main",
                "labels": ["enhancement"],
                "assignees": [{"username": "bob"}],
                "reviewers": [{"username": "charlie"}],
                "state": "opened",
                "web_url": "https://gitlab.com/test/project/merge_requests/5"
            }
        ]
        
        # Execute transformation
        result = await self.agent.execute({
            "run_id": "test-run-123",
            "export_data": {
                "gitlab_ci_yaml": gitlab_ci_yaml,
                "users": gitlab_users,
                "issues": issues,
                "merge_requests": merge_requests,
                "labels": ["bug", "enhancement", "high-priority"],
                "milestones": [{"id": 1, "title": "v1.0", "state": "active"}],
                "gitlab_features": ["epic", "time_tracking"]
            },
            "output_dir": str(tmp_path / "transform"),
            "gitlab_project": "test/project",
            "github_repo": "testorg/testrepo",
            "github_org_members": github_org_members
        })
        
        # Verify transformation succeeded
        assert result["status"] in ["success", "partial"]
        assert result["outputs"]["transform_complete"]
        
        # Check workflows generated
        workflows_count = result["outputs"]["workflows_count"]
        assert workflows_count >= 1
        
        workflows_dir = tmp_path / "transform" / "workflows"
        assert workflows_dir.exists()
        workflow_files = list(workflows_dir.glob("*.yml"))
        assert len(workflow_files) >= 1
        
        # Verify workflow content
        with open(workflow_files[0]) as f:
            workflow_content = f.read()
            assert "name: CI" in workflow_content
            assert "runs-on:" in workflow_content
            assert "steps:" in workflow_content
            # Check some job names were converted
            assert "build" in workflow_content or "unit-tests" in workflow_content
        
        # Check user mappings
        users_mapped = result["outputs"]["users_mapped"]
        assert users_mapped >= 2  # At least alice and bob should be mapped
        
        user_mappings_file = tmp_path / "transform" / "user_mappings.json"
        assert user_mappings_file.exists()
        
        with open(user_mappings_file) as f:
            user_mappings_data = json.load(f)
            assert "mappings" in user_mappings_data
            assert "stats" in user_mappings_data
            # Verify at least 2 users mapped with high confidence
            assert user_mappings_data["stats"]["high_confidence"] >= 2
        
        # Check issues transformed
        issues_transformed = result["outputs"]["issues_transformed"]
        assert issues_transformed == 1
        
        issues_file = tmp_path / "transform" / "issues_transformed.json"
        assert issues_file.exists()
        
        with open(issues_file) as f:
            issues_data = json.load(f)
            assert len(issues_data) == 1
            issue = issues_data[0]
            assert issue["title"] == "Fix login bug"
            # Check attribution added
            assert "Originally created" in issue["body"]
            # Check mentions transformed
            assert "@alice" in issue["body"]
            # Check cross-reference transformed
            assert "#5" in issue["body"] or "testorg/testrepo#5" in issue["body"]
        
        # Check MRs transformed
        mrs_transformed = result["outputs"]["mrs_transformed"]
        assert mrs_transformed == 1
        
        mrs_file = tmp_path / "transform" / "pull_requests_transformed.json"
        assert mrs_file.exists()
        
        with open(mrs_file) as f:
            mrs_data = json.load(f)
            assert len(mrs_data) == 1
            mr = mrs_data[0]
            assert mr["title"] == "Add user authentication"
            assert mr["head"] == "feature/auth"
            assert mr["base"] == "main"
        
        # Check gap analysis
        conversion_gaps = result["outputs"]["conversion_gaps"]
        assert conversion_gaps >= 0  # May have gaps
        
        gaps_file = tmp_path / "transform" / "conversion_gaps.json"
        assert gaps_file.exists()
        
        with open(gaps_file) as f:
            gaps_data = json.load(f)
            assert "gaps" in gaps_data
            assert "summary" in gaps_data
            
            # Verify gap analysis included GitLab features
            gap_types = [g["type"] for g in gaps_data["gaps"]]
            # Should detect epic and time_tracking as feature gaps
            assert any("epic" in str(g) or "feature" in g for g in gap_types)
        
        # Check gap report generated
        gaps_report_file = tmp_path / "transform" / "conversion_gaps.md"
        assert gaps_report_file.exists()
        
        with open(gaps_report_file) as f:
            report = f.read()
            assert "# Migration Conversion Gaps Report" in report
            assert "Summary" in report
    
    @pytest.mark.asyncio
    async def test_empty_export_data_handling(self, tmp_path):
        """Test graceful handling of empty export data"""
        
        result = await self.agent.execute({
            "run_id": "test-run-empty",
            "export_data": {},
            "output_dir": str(tmp_path / "transform")
        })
        
        # Should succeed but with no transformations
        assert result["status"] == "success"
        assert result["outputs"]["transform_complete"]
        assert result["outputs"]["workflows_count"] == 0
        assert result["outputs"]["users_mapped"] == 0
        assert result["outputs"]["issues_transformed"] == 0
    
    @pytest.mark.asyncio
    async def test_minimal_cicd_transformation(self, tmp_path):
        """Test transformation of minimal GitLab CI config"""
        
        gitlab_ci_yaml = {
            "test": {
                "script": ["echo 'Hello World'", "pytest"]
            }
        }
        
        result = await self.agent.execute({
            "run_id": "test-run-minimal",
            "export_data": {
                "gitlab_ci_yaml": gitlab_ci_yaml
            },
            "output_dir": str(tmp_path / "transform")
        })
        
        assert result["status"] == "success"
        assert result["outputs"]["workflows_count"] >= 1
        
        # Verify workflow file exists and is valid
        workflows_dir = tmp_path / "transform" / "workflows"
        workflow_files = list(workflows_dir.glob("*.yml"))
        assert len(workflow_files) >= 1
        
        # Parse YAML to ensure it's valid
        import yaml
        with open(workflow_files[0]) as f:
            workflow = yaml.safe_load(f)
            assert "jobs" in workflow
            assert "test" in workflow["jobs"]
