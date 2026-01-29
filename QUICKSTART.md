# gl2gh Platform - Quick Start Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- Ports available: 3000, 8000, 6379, 27017

## Quick Start (< 5 minutes)

### 1. Clone and Configure

```bash
git clone https://github.com/moti-malka/gl2gh.git
cd gl2gh

# Create environment file
cp .env.example .env

# IMPORTANT: Edit .env and change these security keys
# SECRET_KEY=<generate-a-random-secret-key>
# APP_MASTER_KEY=<generate-another-random-key>
```

### 2. Start the Platform

```bash
./start.sh
```

This command will:
- Build Docker images (first time only)
- Start MongoDB, Redis, Backend API, Celery Worker, and Frontend
- Run health checks

### 3. Verify Installation

```bash
./health-check.sh
```

### 4. Access the Platform

Once healthy, access:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Common Commands

```bash
# View logs
./start.sh logs

# Stop services
./start.sh stop

# Restart services
./start.sh restart

# Clean everything (removes data!)
./start.sh clean

# Check service status
./start.sh status

# Open backend shell
./start.sh shell-backend
```

## Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker ps

# Check logs
./start.sh logs

# Rebuild images
./start.sh build
```

### Port conflicts

If ports 3000, 8000, 6379, or 27017 are in use:
1. Stop conflicting services
2. Or edit `docker-compose.yml` to use different ports

### Backend API not responding

```bash
# Check backend logs
docker-compose logs backend

# Restart backend
docker-compose restart backend
```

## Next Steps

1. **Create a Migration Project**
   - Go to http://localhost:3000
   - Click "New Project"
   
2. **Add Credentials**
   - GitLab PAT with `read_api`, `read_repository` scopes
   - GitHub PAT with `repo`, `workflow` scopes

3. **Run Discovery**
   - Start with DISCOVER_ONLY mode
   - Review inventory and readiness report

4. **Plan Migration**
   - Switch to PLAN_ONLY mode (default)
   - Review CI conversion and plan

5. **Execute Migration**
   - When ready, use APPLY mode
   - Monitor progress in real-time

## Security Notes

⚠️ **Before production use:**

1. Change `SECRET_KEY` and `APP_MASTER_KEY` in `.env`
2. Use strong, randomly generated keys
3. Never commit `.env` to version control
4. Review CORS settings in `backend/app/config.py`

## Development Mode

The default setup includes hot-reload:
- Backend code changes reload automatically
- Frontend changes trigger React hot reload

Edit files in `backend/` or `frontend/` and see changes immediately.

## Architecture

```
┌─────────────┐
│  Frontend   │  React on :3000
│  (React)    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Backend    │  FastAPI on :8000
│  (FastAPI)  │
└──────┬──────┘
       │
       ├──────► MongoDB (:27017)
       ├──────► Redis (:6379)
       └──────► Celery Workers
```

## Support

- Issues: https://github.com/moti-malka/gl2gh/issues
- Documentation: See `README_PLATFORM.md` for full details
