"""
Integration example demonstrating batch migration usage.

This example shows how to use the BatchOrchestrator to migrate
multiple GitLab projects in parallel.
"""

import asyncio
from app.agents import BatchOrchestrator, MigrationMode, SharedResources


async def main():
    """
    Example: Batch migrate 10 GitLab projects in parallel.
    """
    print("=" * 70)
    print("Batch Migration Example - Parallel Migration of Multiple Projects")
    print("=" * 70)
    print()
    
    # Create shared resources for efficient resource usage
    shared_resources = SharedResources(github_rate_limit=5000)
    
    # Create batch orchestrator
    batch_orchestrator = BatchOrchestrator(shared_resources=shared_resources)
    
    # Prepare project configurations
    # In a real scenario, these would come from a database or API
    project_configs = []
    
    for project_id in range(100, 110):  # Projects 100-109
        config = {
            "project_id": project_id,
            "gitlab_url": "https://gitlab.example.com",
            "gitlab_token": "glpat-example-token",
            "github_token": "ghp_example-token",
            "github_org": "example-org",
            "output_dir": f"/tmp/migration/batch/{project_id}",
            "max_api_calls": 5000,
            "max_per_project_calls": 200,
            "include_archived": False
        }
        project_configs.append(config)
    
    print(f"Migrating {len(project_configs)} projects...")
    print(f"Mode: PLAN_ONLY")
    print(f"Parallel limit: 5")
    print()
    
    # Execute batch migration
    result = await batch_orchestrator.execute_batch_migration(
        project_configs=project_configs,
        mode=MigrationMode.PLAN_ONLY,
        parallel_limit=5
    )
    
    # Display results
    print()
    print("=" * 70)
    print("Batch Migration Results")
    print("=" * 70)
    print(f"Status: {result['status']}")
    print(f"Total projects: {result['total_projects']}")
    print(f"Successful: {result['successful']}")
    print(f"Failed: {result['failed']}")
    print(f"Started at: {result['started_at']}")
    print(f"Finished at: {result['finished_at']}")
    print()
    
    # Show per-project results
    print("Per-Project Results:")
    print("-" * 70)
    for project_result in result['results']:
        project_id = project_result.get('project_id')
        status = project_result.get('status')
        error = project_result.get('error', 'N/A')
        print(f"  Project {project_id}: {status}")
        if status == "failed":
            print(f"    Error: {error}")
    print()
    
    # Summary
    print("=" * 70)
    print("Benefits of Batch Migration:")
    print("  ✓ Parallel execution reduces total time")
    print("  ✓ Independent failure handling")
    print("  ✓ Shared resource management")
    print("  ✓ Configurable concurrency limit")
    print("  ✓ Aggregate progress tracking")
    print("=" * 70)


if __name__ == "__main__":
    """
    Note: This is an example that shows the structure.
    In a real deployment, you would:
    1. Fetch actual project configurations from your database
    2. Use real GitLab/GitHub credentials
    3. Monitor progress via the event system
    4. Store results in the database
    """
    print()
    print("This is an example demonstrating batch migration structure.")
    print("To run in production, integrate with your database and credentials.")
    print()
    
    # Uncomment to run the example:
    # asyncio.run(main())
