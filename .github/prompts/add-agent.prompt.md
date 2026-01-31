# Add New Migration Agent

Create a new agent for the migration pipeline.

## Agent Requirements
- Extend `BaseAgent` from `backend/app/agents/base_agent.py`
- Implement the `execute()` method
- Return `AgentResult` with status, data, and artifacts
- Make operations idempotent (safe to retry)

## Reference Files
- [base_agent.py](../../backend/app/agents/base_agent.py) - Base class
- [discovery_agent.py](../../backend/app/agents/discovery_agent.py) - Example agent
- [orchestrator.py](../../backend/app/agents/orchestrator.py) - Agent coordination

## Agent Template
```python
from app.agents.base_agent import BaseAgent, AgentResult

class NewAgent(BaseAgent):
    """Description of what this agent does."""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.name = "new_agent"
    
    async def execute(self, context: dict) -> AgentResult:
        # Implementation here
        pass
```

## Checklist
1. [ ] Create agent class in `backend/app/agents/`
2. [ ] Register in orchestrator if part of pipeline
3. [ ] Add tests in `backend/tests/test_*_agent.py`
4. [ ] Document in `docs/` if user-facing
