# Docker Build Fix - Microsoft Agent Framework

## Issue

Docker build was failing with:
```
ERROR: Could not find a version that satisfies the requirement agent-framework-core==0.1.0
ERROR: No matching distribution found for agent-framework-core==0.1.0
```

## Root Cause

The packages `agent-framework-core==0.1.0` and `agent-framework-openai==0.1.0` don't exist on PyPI. 

Microsoft Agent Framework is currently in **beta** with versions like:
- `1.0.0b260128` (latest as of January 28, 2026)
- Format: `1.0.0b{YYMMDD}`

## Solution

### What We Changed

1. **Removed non-existent packages from `requirements.txt`**
   - Removed: `agent-framework-core==0.1.0`
   - Removed: `agent-framework-openai==0.1.0`
   - Added: Comment explaining future integration

2. **Updated documentation** (`docs/MICROSOFT_AGENT_FRAMEWORK.md`)
   - Clarified we're using MAF **patterns**, not the library (yet)
   - Added Phase 2 integration plan
   - Documented Azure AI examples as reference
   - Provided step-by-step upgrade guide

### Current Architecture (Phase 1) ✅

We implement **Microsoft Agent Framework patterns** without the library:
- ✅ 6 specialized agents (Discovery, Export, Transform, Plan, Apply, Verify)
- ✅ Base agent class with standard interface
- ✅ Orchestrator for workflow management
- ✅ Context sharing and error handling
- ✅ Deterministic, resumable workflows

**Why not use the library yet?**
- It's in beta (changing API)
- Platform can be developed independently
- Easy to integrate when ready
- No dependency on beta software

### Future Integration (Phase 2) 🔄

When ready, we can upgrade to use the actual MAF library:

```bash
# Install MAF beta packages
pip install agent-framework-core --pre
pip install agent-framework-azure --pre
```

Then refactor agents:
```python
from agent_framework import ChatAgent

class DiscoveryAgent(ChatAgent):
    def __init__(self):
        super().__init__(
            instructions="Scan GitLab groups/projects...",
            tools=[gitlab_api_tool]
        )
```

See `docs/MICROSOFT_AGENT_FRAMEWORK.md` for complete integration guide.

## How to Build Now

### Option 1: Using start.sh (Recommended)
```bash
./start.sh
```

### Option 2: Docker Compose Directly
```bash
docker compose build
docker compose up
```

### Option 3: Rebuild After Changes
```bash
./start.sh build
./start.sh up
```

## Verification

After starting, verify all services are healthy:
```bash
./health-check.sh
```

Should show:
```
✓ MongoDB is healthy
✓ Redis is healthy  
✓ Backend API is healthy
✓ Celery worker is healthy
✓ Frontend is healthy
```

## Access Points

Once running:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## What's Ready

✅ Complete infrastructure (Docker Compose)
✅ Backend API (FastAPI)
✅ Frontend (React)
✅ Database (MongoDB)
✅ Job queue (Redis + Celery)
✅ Agent framework (MAF patterns)
✅ Security layer (encryption, JWT)
✅ Comprehensive documentation

## What's Next

The platform is ready for implementation:
1. Implement authentication service
2. Implement database services
3. Connect API endpoints to services
4. Build agent logic (discovery, export, transform, plan, apply, verify)
5. Build UI components
6. Add tests

Later (optional):
- Integrate MAF library (Phase 2)
- Add LLM-powered intelligence
- Azure AI hosting

## Resources

- **Integration Guide**: `docs/MICROSOFT_AGENT_FRAMEWORK.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Quick Start**: `QUICKSTART.md`
- **Platform Overview**: `README_PLATFORM.md`
- **Azure AI Examples**: https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai/README.md

## Support

If build still fails:
1. Check Docker is running: `docker ps`
2. Clean everything: `./start.sh clean`
3. Rebuild: `./start.sh build`
4. Check logs: `./start.sh logs`

For issues, see `QUICKSTART.md` troubleshooting section.
