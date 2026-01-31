---
applyTo: "backend/app/agents/**/*.py"
---
# Agent Development Instructions

## Agent Architecture
All agents extend `BaseAgent` and implement the Microsoft Agent Framework patterns.

## Creating a New Agent
```python
from app.agents.base_agent import BaseAgent, AgentResult

class MyAgent(BaseAgent):
    """Description of what this agent does."""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.name = "my_agent"
    
    async def execute(self, context: dict) -> AgentResult:
        """
        Execute the agent's main task.
        
        Args:
            context: Dictionary containing:
                - run_id: Current migration run ID
                - project_id: Migration project ID
                - gitlab_*: GitLab connection details
                - github_*: GitHub connection details
                - artifacts_path: Where to store outputs
        
        Returns:
            AgentResult with status, data, and any errors
        """
        try:
            # 1. Extract required context
            run_id = context["run_id"]
            
            # 2. Perform agent-specific work
            result_data = await self._do_work(context)
            
            # 3. Store artifacts
            await self._store_artifact(context, "output.json", result_data)
            
            # 4. Return success
            return AgentResult(
                status="completed",
                data=result_data,
                artifacts=["output.json"]
            )
        except Exception as e:
            self.logger.error(f"Agent failed: {e}")
            return AgentResult(
                status="failed",
                error=str(e)
            )
```

## Agent Execution Flow
1. **Discovery** → Scans GitLab, produces inventory
2. **Export** → Downloads repositories, CI files, issues, etc.
3. **Transform** → Converts GitLab CI to GitHub Actions
4. **Plan** → Creates migration plan with all operations
5. **Apply** → Executes plan against GitHub API
6. **Verify** → Validates migration success

## Best Practices
- Make agents idempotent (safe to retry)
- Store checkpoints for long-running operations
- Use exponential backoff for API rate limits
- Log progress events for UI visibility
- Keep artifacts as JSON for debugging
- Handle partial failures gracefully

## Context Variables
Common context keys agents should expect:
- `run_id`, `project_id` - Identifiers
- `gitlab_url`, `gitlab_token` - GitLab connection
- `github_org`, `github_token` - GitHub connection
- `artifacts_path` - Storage location
- `mode` - "plan_only" or "execute"
- `options` - Agent-specific configuration
