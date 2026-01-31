# GitHub Copilot Instructions for gl2gh

## Project Overview
gl2gh is a **GitLab to GitHub migration platform** built with a microservices architecture. It uses specialized AI agents (powered by Microsoft Agent Framework) to handle different stages of migration: Discovery, Export, Transform, Plan, Apply, and Verify.

## Tech Stack

### Backend (Python 3.11+)
- **Framework**: FastAPI with async/await patterns
- **Database**: MongoDB via Motor (async driver)
- **Queue**: Redis + Celery for background jobs
- **AI Framework**: Microsoft Agent Framework (`agent-framework-core`)
- **Authentication**: JWT with python-jose, passwords via passlib/bcrypt
- **HTTP Clients**: httpx (async), requests (sync)
- **Validation**: Pydantic v2 for models and settings

### Frontend (React 18)
- **Routing**: react-router-dom v6
- **HTTP**: axios for API calls
- **Real-time**: socket.io-client for WebSocket connections
- **Styling**: CSS with GitHub-inspired theme

### Infrastructure
- **Orchestration**: Docker Compose
- **Services**: MongoDB, Redis, Backend API, Celery Workers, Frontend

## Code Style and Conventions

### Python Backend
- Use **async/await** for all I/O operations (database, HTTP calls)
- Follow the existing service layer pattern: `app/services/` contains business logic
- API routes go in `app/api/` with proper dependency injection
- Models use Pydantic v2 with `model_validator` and `field_validator`
- All agents extend `BaseAgent` from `app/agents/base_agent.py`
- Use type hints everywhere
- Docstrings should be clear and describe purpose, args, and return values
- Tests use pytest with pytest-asyncio fixtures

### React Frontend
- Functional components with hooks
- Components in `src/components/`, pages in `src/pages/`
- Services for API calls in `src/services/`
- Use existing CSS classes from `styles/github-theme.css`

## Project Structure

```
backend/
├── app/
│   ├── agents/       # Migration agents (discovery, export, transform, plan, apply, verify)
│   ├── api/          # FastAPI route handlers
│   ├── clients/      # External API clients (GitLab, GitHub)
│   ├── db/           # Database connection and utilities
│   ├── models/       # Pydantic models for requests/responses
│   ├── services/     # Business logic layer
│   ├── utils/        # Shared utilities
│   └── workers/      # Celery task definitions
├── tests/            # pytest tests
└── scripts/          # Admin and setup scripts

frontend/
├── src/
│   ├── components/   # Reusable React components
│   ├── pages/        # Page-level components
│   ├── services/     # API service modules
│   └── styles/       # CSS files

docs/                 # Detailed documentation for features
```

## Key Patterns

### Agent Pattern
Each agent follows this pattern:
```python
class MyAgent(BaseAgent):
    async def execute(self, context: dict) -> AgentResult:
        # 1. Validate inputs
        # 2. Perform operations
        # 3. Store artifacts
        # 4. Return AgentResult with status and data
```

### Service Pattern
Services handle business logic and database operations:
```python
class MyService:
    def __init__(self, db):
        self.db = db
        self.collection = db["my_collection"]
    
    async def create(self, data: CreateModel) -> dict:
        # Validate, insert, return
```

### API Route Pattern
```python
@router.post("/resource", response_model=ResponseModel)
async def create_resource(
    data: CreateModel,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = MyService(db)
    return await service.create(data)
```

## Testing Guidelines
- Write tests in `backend/tests/` using pytest
- Use async fixtures from `conftest.py`
- Mock external APIs (GitLab, GitHub) with `pytest-mock` and `responses`
- Test file naming: `test_<module>.py`
- Run tests with: `cd backend && python -m pytest`

## Migration Components
The platform handles 14 component types:
1. Code (repositories)
2. CI/CD (GitLab CI → GitHub Actions)
3. Issues
4. Merge Requests → Pull Requests
5. Wiki
6. Releases
7. Packages
8. Settings
9. Webhooks
10. Branch protections
11. Environments
12. Variables/Secrets
13. User mappings
14. Attachments

## Important Files to Reference
- `docs/ARCHITECTURE.md` - System architecture
- `docs/PLAN_SCHEMA.md` - Migration plan structure
- `docs/MIGRATION_COVERAGE.md` - What gets migrated
- `backend/app/agents/README.md` - Agent system documentation
- `backend/app/config.py` - Configuration settings

## Environment Variables
Key environment variables (see `.env.example`):
- `MONGO_URL` - MongoDB connection string
- `REDIS_URL` - Redis connection string
- `APP_MASTER_KEY` - Encryption key for credentials
- `SECRET_KEY` - JWT signing key
- `AZURE_OPENAI_*` - Azure AI settings (optional)

## Common Tasks

### Adding a new API endpoint
1. Create/update model in `app/models/`
2. Add business logic in `app/services/`
3. Create route in `app/api/`
4. Register router in `app/main.py`
5. Add tests in `tests/`

### Adding a new agent capability
1. Extend or modify agents in `app/agents/`
2. Update orchestrator if needed
3. Add artifacts schema if new outputs
4. Document in `docs/`

### Modifying the frontend
1. Components go in `src/components/`
2. Use existing CSS classes where possible
3. API calls through `src/services/`
4. Update routes in `App.js` if adding pages
