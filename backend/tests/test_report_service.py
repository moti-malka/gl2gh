"""Tests for migration report service"""

import pytest
from pathlib import Path
import json
import tempfile
from bson import ObjectId

from app.services.report_service import MigrationReportGenerator
from app.services import RunService, ArtifactService


@pytest.mark.asyncio
async def test_generate_json_report(db, test_project):
    """Test generating a JSON format report"""
    run_service = RunService(db)
    artifact_service = ArtifactService(db)
    
    # Create a run
    run = await run_service.create_run(
        project_id=str(test_project.id),
        mode="FULL",
        config={"test": "config"}
    )
    
    # Update run status to completed
    run = await run_service.update_run_status(
        run_id=str(run.id),
        status="COMPLETED",
        stage="VERIFY"
    )
    
    # Create temp artifact root
    temp_dir = tempfile.mkdtemp()
    await run_service.set_artifact_root(str(run.id), temp_dir)
    
    try:
        # Add some run projects
        await db["run_projects"].insert_many([
            {
                "run_id": ObjectId(str(run.id)),
                "gitlab_project_id": 123,
                "path_with_namespace": "myorg/project1",
                "bucket": "M",
                "facts": {"webhook_count": 2},
                "readiness": {"has_ci_variables": True},
                "stage_status": {
                    "discover": "COMPLETED",
                    "export": "COMPLETED",
                    "transform": "COMPLETED",
                    "plan": "COMPLETED",
                    "apply": "COMPLETED",
                    "verify": "COMPLETED"
                },
                "errors": []
            }
        ])
        
        # Create sample apply_report artifact
        apply_report_path = Path(temp_dir) / "apply_report_123.json"
        apply_report_data = {
            "project": "myorg/project1",
            "results": {
                "issues": [
                    {"id": 1, "success": True},
                    {"id": 2, "success": True},
                    {"id": 3, "success": False}
                ],
                "pull_requests": [
                    {"id": 1, "success": True},
                    {"id": 2, "success": True}
                ],
                "workflows": [
                    {"id": 1, "success": True}
                ],
                "releases": [
                    {"id": 1, "success": True},
                    {"id": 2, "success": True}
                ]
            }
        }
        apply_report_path.write_text(json.dumps(apply_report_data))
        
        # Store artifact metadata
        await artifact_service.store_artifact(
            run_id=str(run.id),
            artifact_type="apply_report",
            path="apply_report_123.json",
            gitlab_project_id=123,
            size_bytes=len(json.dumps(apply_report_data)),
            metadata={"path_with_namespace": "myorg/project1"}
        )
        
        # Generate report
        generator = MigrationReportGenerator(db)
        report = await generator.generate(str(run.id), format="json")
        
        # Verify report structure
        assert report["run_id"] == str(run.id)
        assert report["status"] == "COMPLETED"
        assert report["mode"] == "FULL"
        assert "project" in report
        assert "summary" in report
        assert "manual_actions" in report
        assert "migration_details" in report
        assert "generated_at" in report
        
        # Verify summary contains expected components
        assert "components" in report["summary"]
        assert "issues" in report["summary"]["components"]
        assert "merge_requests_to_prs" in report["summary"]["components"]
        
        # Verify statistics from apply_report
        assert report["summary"]["components"]["issues"]["migrated"] == 2
        assert report["summary"]["components"]["issues"]["failed"] == 1
        assert report["summary"]["components"]["pull_requests"]["migrated"] == 2
        
    finally:
        # Cleanup temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_generate_markdown_report(db, test_project):
    """Test generating a Markdown format report"""
    run_service = RunService(db)
    
    run = await run_service.create_run(
        project_id=str(test_project.id),
        mode="FULL",
        config={"test": "config"}
    )
    
    await run_service.update_run_status(
        run_id=str(run.id),
        status="COMPLETED",
        stage="VERIFY"
    )
    
    temp_dir = tempfile.mkdtemp()
    await run_service.set_artifact_root(str(run.id), temp_dir)
    
    try:
        await db["run_projects"].insert_many([
            {
                "run_id": ObjectId(str(run.id)),
                "gitlab_project_id": 123,
                "path_with_namespace": "myorg/project1",
                "stage_status": {"verify": "COMPLETED"},
                "errors": []
            }
        ])
        
        # Generate report
        generator = MigrationReportGenerator(db)
        report = await generator.generate(str(run.id), format="markdown")
        
        # Verify report structure
        assert report["format"] == "markdown"
        assert "content" in report
        
        content = report["content"]
        
        # Verify markdown contains expected sections
        assert "# Migration Report" in content
        assert "## Summary" in content
        assert "## Projects" in content
        assert "✅" in content  # Completed status
        
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_generate_html_report(db, test_project):
    """Test generating an HTML format report"""
    run_service = RunService(db)
    
    run = await run_service.create_run(
        project_id=str(test_project.id),
        mode="FULL",
        config={"test": "config"}
    )
    
    await run_service.update_run_status(
        run_id=str(run.id),
        status="COMPLETED",
        stage="VERIFY"
    )
    
    temp_dir = tempfile.mkdtemp()
    await run_service.set_artifact_root(str(run.id), temp_dir)
    
    try:
        await db["run_projects"].insert_many([
            {
                "run_id": ObjectId(str(run.id)),
                "gitlab_project_id": 123,
                "path_with_namespace": "myorg/project1",
                "stage_status": {"verify": "COMPLETED"},
                "errors": []
            }
        ])
        
        # Generate report
        generator = MigrationReportGenerator(db)
        report = await generator.generate(str(run.id), format="html")
        
        # Verify report structure
        assert report["format"] == "html"
        assert "content" in report
        
        content = report["content"]
        
        # Verify HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html>" in content
        assert "<h1>Migration Report</h1>" in content
        assert "<table>" in content
        
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_invalid_format(db, test_project):
    """Test error handling for invalid format"""
    run_service = RunService(db)
    
    run = await run_service.create_run(
        project_id=str(test_project.id),
        mode="FULL"
    )
    
    generator = MigrationReportGenerator(db)
    with pytest.raises(ValueError, match="Invalid format"):
        await generator.generate(str(run.id), format="invalid")


@pytest.mark.asyncio
async def test_invalid_run_id(db):
    """Test error handling for invalid run ID"""
    generator = MigrationReportGenerator(db)
    
    with pytest.raises(ValueError, match="Run not found"):
        await generator.generate("000000000000000000000000", format="json")

