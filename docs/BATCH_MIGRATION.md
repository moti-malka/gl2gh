# Batch Migration - Parallel Migration Support

## Overview

The Batch Migration feature enables parallel migration of multiple GitLab projects simultaneously, significantly reducing the total time required for large-scale migrations.

## Key Features

### 1. **Parallel Execution**
- Migrate multiple projects concurrently
- Configurable parallelism limit (1-20 concurrent migrations)
- Efficient resource utilization

### 2. **Independent Failure Handling**
- One project failure doesn't stop others
- Each project result tracked separately
- Partial success supported

### 3. **Shared Resource Management**
- Shared rate limiting across parallel jobs
- User mapping cache shared between projects
- Prevents API throttling

### 4. **Aggregate Progress Tracking**
- Overall batch status
- Per-project results
- Success/failure counts

## Architecture

### Components

#### `BatchOrchestrator`
Main orchestrator for batch migrations. Coordinates parallel execution of multiple project migrations.

```python
from app.agents import BatchOrchestrator, MigrationMode, SharedResources

# Create shared resources
shared_resources = SharedResources(github_rate_limit=5000)

# Create orchestrator
orchestrator = BatchOrchestrator(shared_resources=shared_resources)

# Execute batch migration
result = await orchestrator.execute_batch_migration(
    project_configs=[...],
    mode=MigrationMode.PLAN_ONLY,
    parallel_limit=5
)
```

#### `SharedResources`
Manages resources shared across parallel migrations:
- User mapping cache
- Rate limiters (future enhancement)

```python
from app.agents import SharedResources

# Create shared resources
resources = SharedResources(github_rate_limit=5000)

# Access user mappings
mapping = await resources.get_user_mapping("gitlab_user_123")
await resources.set_user_mapping("gitlab_user_123", mapping_data)
```

## API Usage

### Batch Migration Endpoint

**Endpoint:** `POST /api/v1/projects/{project_id}/batch-migrate`

**Request Body:**
```json
{
  "project_ids": [123, 456, 789],
  "mode": "PLAN_ONLY",
  "parallel_limit": 5,
  "resume_from": null
}
```

**Response:**
```json
{
  "batch_id": "uuid-here",
  "total_projects": 3,
  "parallel_limit": 5,
  "status": "started",
  "message": "Batch migration started with 3 projects"
}
```

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_ids` | `List[int]` | Required | GitLab project IDs to migrate |
| `mode` | `string` | `"PLAN_ONLY"` | Migration mode (DISCOVER_ONLY, EXPORT_ONLY, PLAN_ONLY, APPLY, FULL) |
| `parallel_limit` | `int` | `5` | Maximum concurrent migrations (1-20) |
| `resume_from` | `string` | `null` | Agent to resume from (optional) |

### Example cURL Request

```bash
curl -X POST "https://gl2gh.example.com/api/v1/projects/my-project/batch-migrate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_ids": [100, 101, 102, 103, 104],
    "mode": "PLAN_ONLY",
    "parallel_limit": 3
  }'
```

## Configuration

### Parallelism Limits

Choose your `parallel_limit` based on:
- Available system resources
- API rate limits
- Network bandwidth
- Desired completion time

**Recommendations:**
- **Small organizations (< 10 projects):** Use `parallel_limit: 3`
- **Medium organizations (10-50 projects):** Use `parallel_limit: 5`
- **Large organizations (50+ projects):** Use `parallel_limit: 10`

### Resource Requirements

For each parallel migration, expect:
- **Memory:** ~200-500 MB per project
- **CPU:** ~0.5-1 core per project
- **Network:** ~10-50 MB/s per project

## Migration Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `DISCOVER_ONLY` | Scan GitLab projects | Initial assessment |
| `EXPORT_ONLY` | Export GitLab data | Data backup |
| `TRANSFORM_ONLY` | Convert to GitHub format | Preparation |
| `PLAN_ONLY` | Generate migration plan | Planning phase |
| `APPLY` | Execute on GitHub | Migration |
| `FULL` | Complete end-to-end migration | One-step migration |

## Best Practices

### 1. Start Small
Begin with a small batch (3-5 projects) to validate configuration:
```json
{
  "project_ids": [123, 456, 789],
  "mode": "DISCOVER_ONLY",
  "parallel_limit": 3
}
```

### 2. Use PLAN_ONLY First
Always run PLAN_ONLY mode before APPLY:
```json
{
  "project_ids": [...],
  "mode": "PLAN_ONLY",
  "parallel_limit": 5
}
```

### 3. Monitor Progress
Use the event system to monitor real-time progress of each project.

### 4. Handle Failures
Review failed projects and retry individually or in smaller batches.

### 5. Respect Rate Limits
- GitHub API: 5,000 requests/hour (authenticated)
- GitLab API: 300-600 requests/minute (varies by plan)

Configure `parallel_limit` to stay within limits:
- **Conservative:** 3-5 parallel projects
- **Moderate:** 5-10 parallel projects
- **Aggressive:** 10-20 parallel projects (requires monitoring)

## Result Handling

### Batch Result Structure

```python
{
    "batch_id": "uuid-here",
    "status": "success" | "partial_success" | "failed",
    "mode": "PLAN_ONLY",
    "started_at": "2024-01-01T00:00:00Z",
    "finished_at": "2024-01-01T00:30:00Z",
    "total_projects": 10,
    "successful": 8,
    "failed": 2,
    "parallel_limit": 5,
    "results": [
        {
            "project_id": 123,
            "index": 0,
            "status": "success",
            "started_at": "...",
            "finished_at": "...",
            "agents": {...}
        },
        {
            "project_id": 456,
            "index": 1,
            "status": "failed",
            "error": "Connection timeout",
            "started_at": "...",
            "finished_at": "..."
        }
    ]
}
```

### Status Values

- **`success`**: All projects migrated successfully
- **`partial_success`**: Some projects succeeded, some failed
- **`failed`**: All projects failed

## Performance Considerations

### Time Savings Example

**Sequential Migration:**
- 100 projects × 5 minutes each = 500 minutes (~8.3 hours)

**Parallel Migration (5 concurrent):**
- 100 projects ÷ 5 × 5 minutes = 100 minutes (~1.7 hours)

**Time Saved:** 6.6 hours (80% reduction)

### Scaling Recommendations

| Projects | Parallel Limit | Est. Time (per project: 5min) |
|----------|----------------|------------------------------|
| 10 | 3 | ~17 minutes |
| 50 | 5 | ~50 minutes |
| 100 | 10 | ~50 minutes |
| 500 | 20 | ~125 minutes |

## Troubleshooting

### Common Issues

#### 1. Rate Limit Exceeded
**Symptom:** Many projects failing with rate limit errors

**Solution:**
- Reduce `parallel_limit`
- Add delays between API calls
- Increase API rate limits (if possible)

#### 2. Out of Memory
**Symptom:** System crashes during batch migration

**Solution:**
- Reduce `parallel_limit`
- Increase system memory
- Migrate in smaller batches

#### 3. Network Timeouts
**Symptom:** Projects failing with timeout errors

**Solution:**
- Check network connectivity
- Increase timeout values
- Reduce `parallel_limit`

## Implementation Details

### Semaphore-Based Concurrency Control

The batch orchestrator uses Python's `asyncio.Semaphore` to limit concurrent executions:

```python
semaphore = asyncio.Semaphore(parallel_limit)

async def migrate_one_project(config):
    async with semaphore:
        # Only parallel_limit projects run at once
        return await orchestrator.run_migration(...)
```

### Exception Handling

Each project migration is wrapped in try-except to prevent one failure from stopping others:

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Resource Sharing

Shared resources use async locks to prevent race conditions:

```python
async with self._lock:
    self.user_mapping_cache[user_id] = mapping
```

## Future Enhancements

Planned improvements:
- [ ] Real-time progress dashboard
- [ ] Dynamic parallelism adjustment
- [ ] Priority-based scheduling
- [ ] Resume from partial completion
- [ ] Batch result persistence
- [ ] Advanced rate limiting strategies

## Support

For issues or questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review batch migration logs
3. Open a GitHub issue with:
   - Batch configuration used
   - Error messages
   - System specifications
