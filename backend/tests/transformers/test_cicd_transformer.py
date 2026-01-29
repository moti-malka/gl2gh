"""Tests for CI/CD transformer"""

import pytest
import yaml
from app.utils.transformers import CICDTransformer


class TestCICDTransformer:
    """Test cases for GitLab CI to GitHub Actions transformation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.transformer = CICDTransformer()
    
    def test_simple_job_transformation(self):
        """Test transformation of a simple GitLab CI job"""
        gitlab_ci = {
            "stages": ["build", "test"],
            "build_job": {
                "stage": "build",
                "script": ["echo 'Building'", "make build"]
            },
            "test_job": {
                "stage": "test",
                "script": ["echo 'Testing'", "make test"]
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        assert "workflow" in result.data
        workflow = result.data["workflow"]
        
        # Check workflow structure
        assert "name" in workflow
        assert "on" in workflow
        assert "jobs" in workflow
        
        # Check jobs converted (sanitized names)
        job_names = list(workflow["jobs"].keys())
        assert "build_job" in job_names or "build-job" in job_names
        assert "test_job" in job_names or "test-job" in job_names
    
    def test_image_to_container(self):
        """Test image to container conversion"""
        gitlab_ci = {
            "test": {
                "image": "python:3.9",
                "script": ["pytest"]
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        workflow = result.data["workflow"]
        test_job = workflow["jobs"]["test"]
        
        assert "container" in test_job
        assert test_job["container"]["image"] == "python:3.9"
    
    def test_artifacts_conversion(self):
        """Test artifacts to upload-artifact conversion"""
        gitlab_ci = {
            "build": {
                "script": ["make build"],
                "artifacts": {
                    "name": "build-artifacts",
                    "paths": ["dist/", "build/"]
                }
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        workflow = result.data["workflow"]
        build_job = workflow["jobs"]["build"]
        
        # Find upload artifact step
        artifact_step = None
        for step in build_job["steps"]:
            if "upload-artifact" in str(step.get("uses", "")):
                artifact_step = step
                break
        
        assert artifact_step is not None
        assert "with" in artifact_step
        assert artifact_step["with"]["name"] == "build-artifacts"
    
    def test_cache_conversion(self):
        """Test cache to actions/cache conversion"""
        gitlab_ci = {
            "test": {
                "script": ["npm test"],
                "cache": {
                    "key": "npm-cache",
                    "paths": ["node_modules/"]
                }
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        workflow = result.data["workflow"]
        test_job = workflow["jobs"]["test"]
        
        # Find cache step
        cache_step = None
        for step in test_job["steps"]:
            if "actions/cache" in str(step.get("uses", "")):
                cache_step = step
                break
        
        assert cache_step is not None
        assert "with" in cache_step
    
    def test_services_conversion(self):
        """Test services to service containers conversion"""
        gitlab_ci = {
            "test": {
                "image": "python:3.9",
                "services": ["postgres:13", "redis:6"],
                "script": ["pytest"]
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        workflow = result.data["workflow"]
        test_job = workflow["jobs"]["test"]
        
        assert "services" in test_job
        assert "postgres" in test_job["services"]
        assert "redis" in test_job["services"]
    
    def test_variables_conversion(self):
        """Test variables to env conversion"""
        gitlab_ci = {
            "variables": {
                "DATABASE_URL": "postgres://localhost/test",
                "CUSTOM_VAR": "value"
            },
            "test": {
                "script": ["pytest"]
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        workflow = result.data["workflow"]
        
        assert "env" in workflow
        assert "CUSTOM_VAR" in workflow["env"]
        assert workflow["env"]["CUSTOM_VAR"] == "value"
    
    def test_conversion_gaps_tracking(self):
        """Test that conversion gaps are tracked"""
        gitlab_ci = {
            "test": {
                "script": ["pytest"],
                "tags": ["custom-runner"]
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        # Should track gap for custom runner tags
        assert len(result.metadata["conversion_gaps"]) > 0
        gap_types = [gap["type"] for gap in result.metadata["conversion_gaps"]]
        assert "runner_tags" in gap_types
    
    def test_invalid_yaml_handling(self):
        """Test handling of invalid YAML"""
        result = self.transformer.transform({"gitlab_ci_yaml": "invalid: yaml: :"})
        
        assert not result.success
        assert len(result.errors) > 0
    
    def test_job_name_sanitization(self):
        """Test job name sanitization for GitHub Actions"""
        gitlab_ci = {
            "Build & Test": {
                "script": ["make build"]
            }
        }
        
        result = self.transformer.transform({"gitlab_ci_yaml": gitlab_ci})
        
        assert result.success
        workflow = result.data["workflow"]
        
        # Job name should be sanitized
        assert "build-test" in workflow["jobs"] or "build-and-test" in workflow["jobs"]
