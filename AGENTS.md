# Agent Instructions for gl2gh

This file provides instructions for AI agents working on the gl2gh codebase.

## Project Context
gl2gh is a GitLab to GitHub migration platform. The codebase consists of:
- **Backend**: FastAPI + Python 3.11 (async everywhere)
- **Frontend**: React 18
- **Database**: MongoDB (via Motor async driver)
- **Queue**: Redis + Celery

## Critical Rules

### Never Do
- Don't use blocking I/O in async functions
- Don't hardcode credentials or tokens
- Don't skip type hints in Python code
- Don't modify migration agents without updating tests
- Don't commit `.env` files or secrets

### Always Do
- Use `async/await` for all database and HTTP operations
- Add type hints to all Python function signatures
- Write tests for new functionality
- Use Pydantic models for request/response validation
- Handle errors gracefully with proper HTTP status codes

## Code Generation Guidelines

### Python Files
```python
# Required imports pattern
from typing import Optional, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
```

### When Creating Services
1. Accept `db` as constructor parameter
2. Use async methods for all I/O
3. Return dictionaries or Pydantic models
4. Handle ObjectId conversion properly

### When Creating API Routes
1. Use FastAPI dependency injection
2. Include proper response_model
3. Use HTTPException for errors
4. Add docstrings for OpenAPI docs

### When Creating Agents
1. Extend `BaseAgent` class
2. Implement `execute()` method
3. Return `AgentResult` object
4. Store artifacts as JSON

## Testing Requirements
- All new code needs tests
- Use fixtures from `conftest.py`
- Mock external APIs (GitLab, GitHub)
- Use `@pytest.mark.asyncio` for async tests

## File Locations
- New models → `backend/app/models/`
- New services → `backend/app/services/`
- New routes → `backend/app/api/`
- New agents → `backend/app/agents/`
- Tests → `backend/tests/test_*.py`
- React components → `frontend/src/components/`
- React pages → `frontend/src/pages/`

## Before Submitting Changes
1. Run tests: `cd backend && python -m pytest`
2. Check for type errors
3. Ensure no hardcoded secrets
4. Update docs if needed
