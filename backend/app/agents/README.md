# Agent Stubs - To be implemented

This directory will contain the agent implementations:

- `discovery_agent.py` - Integration wrapper for existing discovery agent
- `export_agent.py` - Repository and metadata export
- `transform_agent.py` - GitLab CI to GitHub Actions conversion
- `plan_agent.py` - Migration plan generation
- `apply_agent.py` - GitHub resource creation
- `verify_agent.py` - Post-migration verification

Each agent will follow the contract:
- Clear input/output schemas
- Deterministic behavior
- Error handling with retries
- Progress tracking via events
