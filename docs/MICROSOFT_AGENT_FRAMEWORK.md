# Microsoft Agent Framework Integration

## Overview

The gl2gh migration platform now uses **Microsoft Agent Framework (MAF)** for agent implementation and orchestration. This provides enterprise-grade AI agent capabilities with robust patterns for building production-ready migration agents.

## What is Microsoft Agent Framework?

Microsoft Agent Framework is an open-source framework for building production-ready AI agents with:

- **Agent Abstractions**: Specialized AI entities with reasoning and tool-calling capabilities
- **Workflow Orchestration**: Sequential, parallel, and conditional agent coordination
- **Tool Integration**: Connect agents to APIs, databases, and external systems
- **Context Management**: Share state and memory across agent interactions
- **Enterprise Features**: Observability, security, and robust error handling

## Agent Architecture

### Base Agent Pattern

All migration agents inherit from `BaseAgent` which implements MAF patterns:

```python
from app.agents.base_agent import BaseAgent, AgentResult

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="MyAgent",
            instructions="You are specialized in..."
        )
    
    def validate_inputs(self, inputs: Dict) -> bool:
        # Validate inputs
        pass
    
    async def execute(self, inputs: Dict) -> Dict:
        # Main agent logic
        pass
    
    def generate_artifacts(self, data: Dict) -> Dict:
        # Generate output files
        pass
```

### Key Features

#### 1. Context Awareness
Agents maintain context across operations:
```python
agent.update_context("discovered_projects", projects)
projects = agent.get_context("discovered_projects")
```

#### 2. Retry Logic
Built-in retry with exponential backoff:
```python
result = await agent.run_with_retry(
    inputs,
    max_retries=3,
    retry_delay=5
)
```

#### 3. Structured Logging
All operations logged with structured data:
```python
agent.log_event("INFO", "Processing project", {
    "project_id": 123,
    "status": "started"
})
```

#### 4. Deterministic Results
Standard result format across all agents:
```python
AgentResult(
    status="success",  # or "failed", "partial"
    outputs={...},
    artifacts=[...],
    errors=[...]
)
```

## Implemented Agents

### 1. DiscoveryAgent

**Purpose**: Scan GitLab groups and projects

**Inputs**:
- `gitlab_url`: GitLab instance URL
- `gitlab_token`: Personal Access Token
- `root_group`: Optional root group to scan
- `max_api_calls`: API budget
- `deep`: Enable deep analysis

**Outputs**:
- `inventory`: Complete project inventory
- `stats`: Discovery statistics
- `discovered_projects`: List of projects
- `discovered_groups`: List of groups

**Artifacts**:
- `inventory.json`: Full inventory
- `summary.txt`: Summary report
- `coverage.json`: Component coverage

### 2. ExportAgent

**Purpose**: Export GitLab project data

**Inputs**:
- `gitlab_url`, `gitlab_token`
- `project_id`: Project to export
- `output_dir`: Export destination

**Outputs**:
- `export_complete`: Boolean
- `project_id`: Exported project ID

**Artifacts**:
- `export_manifest.json`: Export metadata
- `repo.bundle`: Git repository bundle
- `issues.json`: Issues data
- `mrs.json`: Merge requests data

### 3. TransformAgent

**Purpose**: Convert GitLab → GitHub formats

**Inputs**:
- `project_id`: Project to transform
- `export_data`: Exported data
- `output_dir`: Transform destination

**Outputs**:
- `transform_complete`: Boolean
- `conversion_gaps`: List of unmappable features

**Artifacts**:
- `workflows/*.yml`: GitHub Actions workflows
- `conversion_gaps.json`: Gap analysis
- `user_mapping.json`: User identity mappings

### 4. PlanAgent

**Purpose**: Generate executable migration plan

**Inputs**:
- `transform_data`: Transformed data
- `output_dir`: Plan destination

**Outputs**:
- `plan`: Complete migration plan
- `plan_complete`: Boolean

**Artifacts**:
- `plan.json`: Executable plan
- `plan.md`: Human-readable plan

### 5. ApplyAgent

**Purpose**: Execute migration on GitHub

**Inputs**:
- `github_token`: GitHub PAT
- `plan`: Migration plan to execute
- `output_dir`: Apply destination

**Outputs**:
- `apply_complete`: Boolean
- `actions_executed`: Count of completed actions

**Artifacts**:
- `apply_report.json`: Execution report
- `apply_log.md`: Detailed log

### 6. VerifyAgent

**Purpose**: Validate migration results

**Inputs**:
- `github_token`: GitHub PAT
- `github_repo`: Repository to verify
- `expected_state`: Expected state
- `output_dir`: Verify destination

**Outputs**:
- `verification_results`: Per-component results
- `verify_complete`: Boolean

**Artifacts**:
- `verify_report.json`: Verification report
- `verify_summary.md`: Summary

## Agent Orchestrator

The `AgentOrchestrator` coordinates multi-agent workflows using MAF patterns:

### Sequential Workflows

Execute agents in order with data flow:

```python
from app.agents import AgentOrchestrator, MigrationMode

orchestrator = AgentOrchestrator()

result = await orchestrator.run_migration(
    mode=MigrationMode.FULL,
    config={
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "glpat-xxx",
        "github_token": "ghp_xxx",
        "run_id": "123"
    }
)
```

### Migration Modes

- **DISCOVER_ONLY**: Run discovery only
- **EXPORT_ONLY**: Discovery + Export
- **TRANSFORM_ONLY**: Discovery + Export + Transform
- **PLAN_ONLY**: Everything except Apply (safe mode)
- **APPLY**: Full migration with GitHub writes
- **VERIFY**: Verification only
- **FULL**: All agents (Discover → Export → Transform → Plan → Apply → Verify)

### Context Sharing

Agents share data through orchestrator's shared context:

```python
# DiscoveryAgent outputs
{"discovered_projects": [...]}

# Available to ExportAgent as
config["discovered_projects"]

# TransformAgent receives
config["export_data"]

# And so on...
```

### Parallel Execution

Run multiple agents concurrently for different projects:

```python
results = await orchestrator.run_parallel_agents([
    {"agent": "export", "inputs": {...}},
    {"agent": "export", "inputs": {...}},
    {"agent": "export", "inputs": {...}}
])
```

## Celery Task Integration

All agents are exposed as Celery tasks:

```python
from app.workers.tasks import (
    run_migration,  # Full orchestrated workflow
    run_discovery,  # Individual agents
    run_export,
    run_transform,
    run_plan,
    run_apply,
    run_verify
)

# Run complete migration
result = run_migration.delay(
    run_id="123",
    mode="PLAN_ONLY",
    config={...}
)

# Or run individual agent
result = run_discovery.delay(
    run_id="123",
    config={...}
)
```

## Error Handling

### Automatic Retry

All agents support automatic retry with configurable attempts:

```python
result = await agent.run_with_retry(
    inputs,
    max_retries=3,
    retry_delay=5  # seconds
)
```

### Partial Success

Agents can report partial success:

```python
AgentResult(
    status="partial",
    outputs={...},  # What succeeded
    errors=[...]     # What failed
)
```

### Resume Support

Resume from specific agent:

```python
result = await orchestrator.run_migration(
    mode=MigrationMode.FULL,
    config={...},
    resume_from="transform"  # Skip discovery and export
)
```

## Future Enhancements

### LLM Integration

In future iterations, agents can leverage MAF's ChatAgent for intelligent decision-making:

```python
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

agent = ChatAgent(
    chat_client=OpenAIChatClient(),
    instructions="Analyze this GitLab CI file and suggest GitHub Actions mapping..."
)

result = await agent.run("Convert this pipeline...")
```

### Function Calling

Agents can use MAF's function calling for tool integration:

```python
@agent.function_tool
def get_gitlab_project(project_id: int):
    """Fetch project from GitLab API"""
    return gitlab_client.get_project(project_id)
```

### Memory Providers

Long-term memory for agents:

```python
agent.memory.store("user_mapping", {
    "gitlab_user_123": "github_user_456"
})

mapping = agent.memory.recall("user_mapping")
```

## Dependencies

Required packages (already in requirements.txt):

```txt
agent-framework-core==0.1.0
agent-framework-openai==0.1.0  # For future LLM integration
```

## Testing

Test agents individually:

```python
import pytest
from app.agents import DiscoveryAgent

@pytest.mark.asyncio
async def test_discovery_agent():
    agent = DiscoveryAgent()
    
    inputs = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "test-token",
        "output_dir": "/tmp/test"
    }
    
    result = await agent.execute(inputs)
    
    assert result["status"] == "success"
    assert "discovered_projects" in result["outputs"]
```

## Benefits of MAF Integration

1. **Enterprise Ready**: Production-grade patterns out of the box
2. **Scalable**: Support for parallel execution and distributed agents
3. **Observable**: Built-in logging and event tracking
4. **Extensible**: Easy to add new agents and tools
5. **Resumable**: Workflow checkpointing and recovery
6. **Deterministic**: Same inputs → same outputs
7. **Maintainable**: Clear separation of concerns
8. **Testable**: Each agent independently testable

## Migration from Previous Implementation

The new MAF-based agents are backward compatible. The Celery tasks expose the same interface, just with improved internal implementation using MAF patterns.

## References

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/en-us/agent-framework/)
- [GitHub Repository](https://github.com/microsoft/agent-framework)
- [Python Quick Start](https://learn.microsoft.com/en-us/agent-framework/tutorials/quick-start)

## Support

For issues or questions about agent implementation:
1. Review agent code in `backend/app/agents/`
2. Check Celery task logs
3. Enable DEBUG logging for detailed traces
4. Consult MAF documentation for patterns
