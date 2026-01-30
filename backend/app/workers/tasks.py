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


async def ensure_db_connection():
    """Ensure MongoDB is connected for worker tasks"""
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.config import settings
    import app.db as db_module
    
    # Always create a fresh connection for each task to avoid event loop issues
    db_module._client = AsyncIOMotorClient(settings.MONGO_URL)
    # Ping to verify connection
    await db_module._client.admin.command('ping')
    logger.info("MongoDB connection established for worker task")


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
    
    # Run async code in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Ensure MongoDB is connected
        loop.run_until_complete(ensure_db_connection())
        
        # Import services
        from app.services import RunService, EventService
        
        run_service = RunService()
        event_service = EventService()
        
        # Determine which stages will run based on mode
        mode_stages = {
            "DISCOVER_ONLY": ["DISCOVER"],
            "PLAN_ONLY": ["DISCOVER", "EXPORT", "TRANSFORM", "PLAN"],
            "APPLY": ["DISCOVER", "EXPORT", "TRANSFORM", "PLAN", "APPLY"],
            "FULL": ["DISCOVER", "EXPORT", "TRANSFORM", "PLAN", "APPLY", "VERIFY"],
        }
        components = mode_stages.get(mode, ["DISCOVER", "EXPORT", "TRANSFORM", "PLAN"])
        total_stages = len(components)
        completed_stages = 0
        
        # Helper to emit event and update progress
        async def emit_event(level: str, message: str, agent: str = None, event_type: str = None):
            await event_service.create_event(
                run_id=run_id,
                level=level,
                message=message,
                agent=agent,
                scope="run",
                payload={"type": event_type} if event_type else None
            )
        
        # Initialize run with components
        await_func = loop.run_until_complete
        await_func(
            run_service.db["runs"].update_one(
                {"_id": __import__('bson').ObjectId(run_id)},
                {"$set": {"components": components, "progress_percent": 0}}
            )
        )
        
        # Emit start event
        await_func(emit_event("INFO", f"Migration started in {mode} mode", event_type="run_started"))
        
        # Update run status to RUNNING
        await_func(
            run_service.update_run_status(
                run_id=run_id,
                status="RUNNING",
                stage="STARTING"
            )
        )
        
        # Create orchestrator
        orchestrator = AgentOrchestrator()
        
        # Add run_id to config
        config["run_id"] = run_id
        
        # Load component selection from run if available
        run = await_func(run_service.get_run(run_id))
        if run and run.selection:
            config["component_selection"] = run.selection
        
        # Define a callback to update status during workflow
        async def update_stage(stage: str):
            nonlocal completed_stages
            stage_upper = stage.upper()
            
            # Emit stage started event
            await emit_event("INFO", f"{stage_upper} stage started", agent=f"{stage}Agent", event_type="component_started")
            
            await run_service.update_run_status(
                run_id=run_id,
                status="RUNNING",
                stage=stage_upper
            )
        
        # Define a callback when stage completes
        async def complete_stage(stage: str, result: dict):
            nonlocal completed_stages
            stage_upper = stage.upper()
            completed_stages += 1
            progress = int((completed_stages / total_stages) * 100)
            
            # Emit stage completed event
            status = result.get("status", "success")
            if status == "success":
                await emit_event("INFO", f"{stage_upper} stage completed successfully", agent=f"{stage}Agent", event_type="component_completed")
            else:
                await emit_event("ERROR", f"{stage_upper} stage failed: {result.get('error', 'Unknown error')}", agent=f"{stage}Agent", event_type="error")
            
            # Update progress
            await run_service.db["runs"].update_one(
                {"_id": __import__('bson').ObjectId(run_id)},
                {"$set": {"progress_percent": progress}}
            )
        
        result = await_func(
            orchestrator.run_migration(
                mode=MigrationMode(mode),
                config=config,
                stage_callback=update_stage,
                complete_callback=complete_stage
            )
        )
        
        # Update final run status
        final_status = "COMPLETED" if result.get("status") == "success" else "FAILED"
        
        # Emit completion event
        if final_status == "COMPLETED":
            await_func(emit_event("INFO", "Migration completed successfully", event_type="run_completed"))
        else:
            error_msg = result.get("error", "Unknown error")
            await_func(emit_event("ERROR", f"Migration failed: {error_msg}", event_type="run_failed"))
        
        await_func(
            run_service.update_run_status(
                run_id=run_id,
                status=final_status,
                stage="DONE" if final_status == "COMPLETED" else "FAILED"
            )
        )
        
        # Set final progress
        await_func(
            run_service.db["runs"].update_one(
                {"_id": __import__('bson').ObjectId(run_id)},
                {"$set": {"progress_percent": 100 if final_status == "COMPLETED" else completed_stages * (100 // total_stages)}}
            )
        )
        
        logger.info(f"Migration run {run_id} completed with status: {result.get('status')}")
        return result
        
    except Exception as e:
        logger.error(f"Migration run {run_id} failed: {str(e)}")
        
        # Update run status to FAILED
        try:
            from app.services import RunService
            run_service = RunService()
            loop.run_until_complete(
                run_service.update_run_status(
                    run_id=run_id,
                    status="FAILED",
                    error={"message": str(e)}
                )
            )
        except Exception as update_error:
            logger.error(f"Failed to update run status: {update_error}")
        
        return {
            "status": "failed",
            "error": str(e),
            "run_id": run_id
        }
    finally:
        loop.close()


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
                
                # Build component inventory summary from discovered projects
                inventory_summary = {
                    "repository": {
                        "total_branches": 0,
                        "total_tags": 0,
                        "total_commits": 0,
                        "total_size_mb": 0,
                        "has_lfs": False
                    },
                    "ci_cd": {
                        "projects_with_ci": 0,
                        "total_variables": 0,
                        "total_environments": 0,
                        "total_schedules": 0
                    },
                    "issues": {
                        "total_open": 0,
                        "total_closed": 0,
                        "total_labels": 0,
                        "total_milestones": 0
                    },
                    "merge_requests": {
                        "total_open": 0,
                        "total_merged": 0,
                        "total_closed": 0
                    },
                    "wiki": {
                        "projects_with_wiki": 0,
                        "total_pages": 0
                    },
                    "releases": {
                        "total_releases": 0
                    },
                    "settings": {
                        "total_protected_branches": 0,
                        "total_members": 0,
                        "total_webhooks": 0,
                        "total_deploy_keys": 0
                    },
                    "projects": []
                }
                
                for project_data in discovered_projects:
                    components = project_data.get("components", {})
                    
                    # Add to summary
                    repo = components.get("repository", {})
                    inventory_summary["repository"]["total_branches"] += repo.get("branches_count", 0)
                    inventory_summary["repository"]["total_tags"] += repo.get("tags_count", 0)
                    inventory_summary["repository"]["total_commits"] += repo.get("commits_count", 0)
                    inventory_summary["repository"]["total_size_mb"] += repo.get("size_mb", 0)
                    if components.get("lfs", {}).get("detected"):
                        inventory_summary["repository"]["has_lfs"] = True
                    
                    ci_cd = components.get("ci_cd", {})
                    if ci_cd.get("has_gitlab_ci"):
                        inventory_summary["ci_cd"]["projects_with_ci"] += 1
                    inventory_summary["ci_cd"]["total_variables"] += ci_cd.get("variables_count", 0)
                    inventory_summary["ci_cd"]["total_environments"] += ci_cd.get("environments_count", 0)
                    inventory_summary["ci_cd"]["total_schedules"] += ci_cd.get("schedules_count", 0)
                    
                    issues = components.get("issues", {})
                    inventory_summary["issues"]["total_open"] += issues.get("opened_count", 0)
                    inventory_summary["issues"]["total_closed"] += issues.get("closed_count", 0)
                    inventory_summary["issues"]["total_labels"] += issues.get("labels_count", 0)
                    inventory_summary["issues"]["total_milestones"] += issues.get("milestones_count", 0)
                    
                    mrs = components.get("merge_requests", {})
                    inventory_summary["merge_requests"]["total_open"] += mrs.get("opened_count", 0)
                    inventory_summary["merge_requests"]["total_merged"] += mrs.get("merged_count", 0)
                    inventory_summary["merge_requests"]["total_closed"] += mrs.get("closed_count", 0)
                    
                    wiki = components.get("wiki", {})
                    if wiki.get("enabled") and wiki.get("pages_count", 0) > 0:
                        inventory_summary["wiki"]["projects_with_wiki"] += 1
                    inventory_summary["wiki"]["total_pages"] += wiki.get("pages_count", 0)
                    
                    releases = components.get("releases", {})
                    inventory_summary["releases"]["total_releases"] += releases.get("count", 0)
                    
                    settings = components.get("settings", {})
                    inventory_summary["settings"]["total_protected_branches"] += settings.get("protected_branches_count", 0)
                    inventory_summary["settings"]["total_members"] += settings.get("members_count", 0)
                    inventory_summary["settings"]["total_webhooks"] += settings.get("webhooks_count", 0)
                    inventory_summary["settings"]["total_deploy_keys"] += settings.get("deploy_keys_count", 0)
                    
                    # Add project summary to inventory
                    inventory_summary["projects"].append({
                        "id": project_data["id"],
                        "path_with_namespace": project_data["path_with_namespace"],
                        "components": components
                    })
                
                # Store inventory in run document
                loop.run_until_complete(
                    run_service.update_run_inventory(
                        run_id=run_id,
                        inventory=inventory_summary
                    )
                )
                
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


@celery_app.task(name='app.workers.tasks.run_batch_migration')
def run_batch_migration(
    batch_id: str,
    project_id: str,
    project_ids: list,
    mode: str,
    parallel_limit: int,
    base_config: dict,
    resume_from: str = None
):
    """
    Execute batch migration of multiple projects in parallel.
    
    This task uses the BatchOrchestrator to migrate multiple GitLab
    projects concurrently with configurable parallelism.
    
    Args:
        batch_id: Unique identifier for this batch operation
        project_id: GL2GH project ID (for settings/credentials)
        project_ids: List of GitLab project IDs to migrate
        mode: Migration mode (DISCOVER_ONLY, PLAN_ONLY, APPLY, FULL, etc.)
        parallel_limit: Maximum number of concurrent migrations
        base_config: Base configuration shared across all projects
        resume_from: Optional agent to resume from
    """
    logger.info(
        f"Starting batch migration {batch_id}: "
        f"{len(project_ids)} projects, parallelism={parallel_limit}"
    )
    
    try:
        from app.agents import BatchOrchestrator, MigrationMode, SharedResources
        from pathlib import Path
        
        # Create shared resources for the batch
        shared_resources = SharedResources(
            github_rate_limit=base_config.get("max_api_calls", 5000)
        )
        
        # Create batch orchestrator
        batch_orchestrator = BatchOrchestrator(shared_resources=shared_resources)
        
        # Prepare configs for each project
        project_configs = []
        for gitlab_project_id in project_ids:
            project_config = base_config.copy()
            project_config.update({
                "project_id": gitlab_project_id,
                "run_id": f"{batch_id}_{gitlab_project_id}",
                "output_dir": f"artifacts/runs/{batch_id}/{gitlab_project_id}"
            })
            
            # Create output directory
            Path(project_config["output_dir"]).mkdir(parents=True, exist_ok=True)
            
            project_configs.append(project_config)
        
        # Execute batch migration
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                batch_orchestrator.execute_batch_migration(
                    project_configs=project_configs,
                    mode=MigrationMode(mode),
                    parallel_limit=parallel_limit,
                    resume_from=resume_from
                )
            )
        finally:
            loop.close()
        
        # Log summary
        logger.info(
            f"Batch migration {batch_id} completed: "
            f"status={result.get('status')}, "
            f"successful={result.get('successful')}, "
            f"failed={result.get('failed')}"
        )
        
        # Store batch results (optional - could be saved to database)
        # For now, just return the results
        result["batch_id"] = batch_id
        return result
        
    except Exception as e:
        logger.error(f"Batch migration {batch_id} failed: {str(e)}")
        return {
            "batch_id": batch_id,
            "status": "failed",
            "error": str(e),
            "total_projects": len(project_ids)
        }


