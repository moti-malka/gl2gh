# Add New API Endpoint

Create a new API endpoint following the gl2gh patterns.

## Requirements
- Use FastAPI with async/await
- Add Pydantic models for request/response
- Include proper error handling
- Add tests for the new endpoint

## Checklist
1. [ ] Create/update model in `backend/app/models/`
2. [ ] Add service logic in `backend/app/services/`  
3. [ ] Create route in `backend/app/api/`
4. [ ] Register router in `backend/app/main.py`
5. [ ] Add tests in `backend/tests/`

## Reference Files
- [main.py](../../backend/app/main.py) - Router registration
- [auth.py](../../backend/app/api/auth.py) - Auth patterns
- [projects.py](../../backend/app/api/projects.py) - CRUD patterns
- [conftest.py](../../backend/tests/conftest.py) - Test fixtures
