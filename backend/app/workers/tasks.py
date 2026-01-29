"""Celery tasks using Microsoft Agent Framework agents"""

import asyncio
from datetime import datetime
from app.workers.celery_app import celery_app
from app.utils.logging import get_logger
from app.agents import (
    AgentOrchestrator,
    MigrationMode,
    DiscoveryAgent,
    ExportAgent,
    TransformAgent,
    PlanAgent,
    ApplyAgent,
    VerifyAgent
)

logger = get_logger(__name__)


@celery_app.task(name='app.workers.tasks.test_task')
def test_task(x: int, y: int):
    """Test task to verify Celery is working"""
    logger.info(f"Test task executing with x={x}, y={y}")
    result = x + y
    logger.info(f"Test task result: {result}")
    return result


@celery_app.task(name='app.workers.tasks.run_migration')
def run_migration(run_id: str, mode: str, config: dict):
    """
    Run complete migration workflow using Agent Orchestrator.
    
    This task uses Microsoft Agent Framework's orchestration patterns
    to coordinate multiple specialized agents.
    
    Args:
        run_id: Migration run ID
        mode: Migration mode (DISCOVER_ONLY, PLAN_ONLY, APPLY, FULL, etc.)
        config: Configuration including GitLab/GitHub credentials, settings
    """
    logger.info(f"Starting migration run {run_id} in {mode} mode")
    
    try:
        # Create orchestrator
        orchestrator = AgentOrchestrator()
        
        # Add run_id to config
        config["run_id"] = run_id
        
        # Run async workflow in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                orchestrator.run_migration(
                    mode=MigrationMode(mode),
                    config=config
                )
            )
        finally:
            loop.close()
        
        logger.info(f"Migration run {run_id} completed with status: {result.get('status')}")
        return result
        
    except Exception as e:
        logger.error(f"Migration run {run_id} failed: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "run_id": run_id
        }


@celery_app.task(name='app.workers.tasks.run_discovery')
def run_discovery(run_id: str, config: dict):
    """
    Run discovery agent for a migration run using Microsoft Agent Framework.
    
    Enhanced to:
    - Detect all 14 component types
    - Store results in MongoDB via ArtifactService
    - Emit progress events via EventService
    - Store discovered projects in run_projects collection
    
    Args:
        run_id: Migration run ID
        config: Configuration for discovery
    """
    logger.info(f"Starting discovery for run {run_id}")
    
    try:
        # Import services
        from app.services import ArtifactService, EventService, RunService
        from app.models import RunProject
        from bson import ObjectId
        from pathlib import Path
        import json
        
        # Create discovery agent
        agent = DiscoveryAgent()
        
        # Add run_id to config
        config["run_id"] = run_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/discovery")
        
        # Create output directory
        Path(config["output_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Create service instances
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize services
            artifact_service = ArtifactService()
            event_service = EventService()
            run_service = RunService()
            
            # Emit start event
            loop.run_until_complete(
                event_service.create_event(
                    run_id=run_id,
                    level="INFO",
                    message="Discovery started",
                    agent="DiscoveryAgent",
                    scope="run"
                )
            )
            
            # Update run status
            loop.run_until_complete(
                run_service.update_run_status(
                    run_id=run_id,
                    status="RUNNING",
                    stage="DISCOVER"
                )
            )
            
            # Run agent
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
            
            if result.get("status") == "success":
                outputs = result.get("outputs", {})
                discovered_projects = outputs.get("discovered_projects", [])
                stats = outputs.get("stats", {})
                
                # Store artifacts in MongoDB
                artifacts = result.get("artifacts", [])
                for artifact_path in artifacts:
                    artifact_path_obj = Path(artifact_path)
                    artifact_type = artifact_path_obj.stem  # inventory, coverage, readiness, summary
                    
                    # Read file size
                    size_bytes = artifact_path_obj.stat().st_size if artifact_path_obj.exists() else None
                    
                    # Store artifact metadata
                    loop.run_until_complete(
                        artifact_service.store_artifact(
                            run_id=run_id,
                            artifact_type=artifact_type,
                            path=str(artifact_path_obj.relative_to(Path(f"artifacts/runs/{run_id}"))),
                            size_bytes=size_bytes,
                            metadata={"generated_by": "DiscoveryAgent"}
                        )
                    )
                
                # Store discovered projects as run_projects
                from app.db import get_database
                db = loop.run_until_complete(get_database())
                
                for project_data in discovered_projects:
                    # Create RunProject document
                    run_project = {
                        "run_id": ObjectId(run_id),
                        "gitlab_project_id": project_data["id"],
                        "path_with_namespace": project_data["path_with_namespace"],
                        "facts": {
                            "name": project_data["name"],
                            "description": project_data.get("description"),
                            "visibility": project_data.get("visibility"),
                            "archived": project_data.get("archived"),
                            "default_branch": project_data.get("default_branch"),
                            "components": project_data.get("components", {})
                        },
                        "readiness": {},  # Will be populated later
                        "stage_status": {
                            "discover": "DONE",
                            "export": "PENDING",
                            "transform": "PENDING",
                            "plan": "PENDING",
                            "apply": "PENDING",
                            "verify": "PENDING"
                        },
                        "errors": project_data.get("errors", []),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    
                    # Insert or update
                    loop.run_until_complete(
                        db["run_projects"].update_one(
                            {
                                "run_id": ObjectId(run_id),
                                "gitlab_project_id": project_data["id"]
                            },
                            {"$set": run_project},
                            upsert=True
                        )
                    )
                
                # Update run stats
                loop.run_until_complete(
                    run_service.update_run_stats(
                        run_id=run_id,
                        stats_updates=stats
                    )
                )
                
                # Set artifact root
                loop.run_until_complete(
                    run_service.set_artifact_root(
                        run_id=run_id,
                        artifact_root=f"artifacts/runs/{run_id}"
                    )
                )
                
                # Emit completion event
                loop.run_until_complete(
                    event_service.create_event(
                        run_id=run_id,
                        level="INFO",
                        message=f"Discovery completed: {stats.get('projects', 0)} projects discovered",
                        agent="DiscoveryAgent",
                        scope="run",
                        payload=stats
                    )
                )
                
                # Update run status
                loop.run_until_complete(
                    run_service.update_run_status(
                        run_id=run_id,
                        status="COMPLETED",
                        stage="DISCOVER"
                    )
                )
                
                logger.info(f"Discovery completed for run {run_id}: {stats}")
                return result
            else:
                # Handle failure
                error_msg = result.get("error", "Unknown error")
                
                # Emit error event
                loop.run_until_complete(
                    event_service.create_event(
                        run_id=run_id,
                        level="ERROR",
                        message=f"Discovery failed: {error_msg}",
                        agent="DiscoveryAgent",
                        scope="run"
                    )
                )
                
                # Update run status
                loop.run_until_complete(
                    run_service.update_run_status(
                        run_id=run_id,
                        status="FAILED",
                        stage="DISCOVER",
                        error={"message": error_msg}
                    )
                )
                
                return result
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Discovery failed for run {run_id}: {str(e)}")
        
        # Try to emit error event
        try:
            from app.services import EventService, RunService
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            event_service = EventService()
            run_service = RunService()
            
            loop.run_until_complete(
                event_service.create_event(
                    run_id=run_id,
                    level="ERROR",
                    message=f"Discovery task exception: {str(e)}",
                    agent="DiscoveryAgent",
                    scope="run"
                )
            )
            
            loop.run_until_complete(
                run_service.update_run_status(
                    run_id=run_id,
                    status="FAILED",
                    stage="DISCOVER",
                    error={"message": str(e)}
                )
            )
            
            loop.close()
        except Exception as inner_e:
            logger.error(f"Failed to emit error event: {str(inner_e)}")
        
        return {"status": "failed", "error": str(e), "run_id": run_id}


@celery_app.task(name='app.workers.tasks.run_export')
def run_export(run_id: str, project_id: int, config: dict):
    """
    Export project for migration using Microsoft Agent Framework.
    
    Args:
        run_id: Migration run ID
        project_id: GitLab project ID
        config: Export configuration
    """
    logger.info(f"Starting export for project {project_id} in run {run_id}")
    
    try:
        agent = ExportAgent()
        
        config["run_id"] = run_id
        config["project_id"] = project_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/export")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
        finally:
            loop.close()
        
        logger.info(f"Export completed for project {project_id}")
        return result
        
    except Exception as e:
        logger.error(f"Export failed for project {project_id}: {str(e)}")
        return {"status": "failed", "error": str(e), "project_id": project_id}


@celery_app.task(name='app.workers.tasks.run_transform')
def run_transform(run_id: str, project_id: int, config: dict):
    """
    Transform GitLab constructs to GitHub equivalents using Microsoft Agent Framework.
    
    Args:
        run_id: Migration run ID
        project_id: GitLab project ID
        config: Transform configuration
    """
    logger.info(f"Starting transform for project {project_id} in run {run_id}")
    
    try:
        agent = TransformAgent()
        
        config["run_id"] = run_id
        config["project_id"] = project_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/transform")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
        finally:
            loop.close()
        
        logger.info(f"Transform completed for project {project_id}")
        return result
        
    except Exception as e:
        logger.error(f"Transform failed for project {project_id}: {str(e)}")
        return {"status": "failed", "error": str(e), "project_id": project_id}


@celery_app.task(name='app.workers.tasks.run_plan')
def run_plan(run_id: str, config: dict):
    """
    Generate migration plan using Microsoft Agent Framework.
    
    Args:
        run_id: Migration run ID
        config: Plan configuration
    """
    logger.info(f"Starting plan generation for run {run_id}")
    
    try:
        agent = PlanAgent()
        
        config["run_id"] = run_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/plan")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
        finally:
            loop.close()
        
        logger.info(f"Plan generation completed for run {run_id}")
        return result
        
    except Exception as e:
        logger.error(f"Plan generation failed for run {run_id}: {str(e)}")
        return {"status": "failed", "error": str(e), "run_id": run_id}


@celery_app.task(name='app.workers.tasks.run_apply')
def run_apply(run_id: str, project_id: int, config: dict):
    """
    Apply migration to GitHub using Microsoft Agent Framework.
    
    Args:
        run_id: Migration run ID
        project_id: GitLab project ID
        config: Apply configuration
    """
    logger.info(f"Starting apply for project {project_id} in run {run_id}")
    
    try:
        agent = ApplyAgent()
        
        config["run_id"] = run_id
        config["project_id"] = project_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/apply")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
        finally:
            loop.close()
        
        logger.info(f"Apply completed for project {project_id}")
        return result
        
    except Exception as e:
        logger.error(f"Apply failed for project {project_id}: {str(e)}")
        return {"status": "failed", "error": str(e), "project_id": project_id}


@celery_app.task(name='app.workers.tasks.run_verify')
def run_verify(run_id: str, project_id: int, config: dict):
    """
    Verify migration results using Microsoft Agent Framework.
    
    Args:
        run_id: Migration run ID
        project_id: GitLab project ID
        config: Verification configuration
    """
    logger.info(f"Starting verify for project {project_id} in run {run_id}")
    
    try:
        agent = VerifyAgent()
        
        config["run_id"] = run_id
        config["project_id"] = project_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/verify")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
        finally:
            loop.close()
        
        logger.info(f"Verify completed for project {project_id}")
        return result
        
    except Exception as e:
        logger.error(f"Verify failed for project {project_id}: {str(e)}")
        return {"status": "failed", "error": str(e), "project_id": project_id}

