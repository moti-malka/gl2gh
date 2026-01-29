"""Celery tasks using Microsoft Agent Framework agents"""

import asyncio
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
    
    Args:
        run_id: Migration run ID
        config: Configuration for discovery
    """
    logger.info(f"Starting discovery for run {run_id}")
    
    try:
        # Create discovery agent
        agent = DiscoveryAgent()
        
        # Add run_id to config
        config["run_id"] = run_id
        config["output_dir"] = config.get("output_dir", f"artifacts/runs/{run_id}/discovery")
        
        # Run async agent in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                agent.run_with_retry(config)
            )
        finally:
            loop.close()
        
        logger.info(f"Discovery completed for run {run_id}")
        return result
        
    except Exception as e:
        logger.error(f"Discovery failed for run {run_id}: {str(e)}")
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

