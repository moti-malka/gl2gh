# gl2gh - GitLab to GitHub Agentic Migration Platform

![Architecture](https://img.shields.io/badge/architecture-microservices-blue)
![Status](https://img.shields.io/badge/status-development-yellow)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)

> **A comprehensive, agent-based platform for migrating GitLab groups and projects to GitHub with intelligent CI/CD conversion, validation, and safe execution.**

## 🌟 Overview

gl2gh is an end-to-end migration platform that helps you migrate from GitLab to GitHub with confidence. It uses specialized AI agents to handle different aspects of the migration process, ensuring deterministic, resumable, and safe migrations.

### Key Features

- 🔍 **Smart Discovery**: Scan GitLab groups and assess migration readiness
- 📦 **Export**: Extract repositories, CI configurations, and metadata
- 🔄 **Transform**: Convert GitLab CI to GitHub Actions automatically
- 📋 **Plan**: Generate executable migration plans with gap analysis
- ✅ **Apply**: Execute migrations with idempotency and safety checks
- 🔐 **Verify**: Validate migration success with comprehensive checks
- 🎯 **Safe by Default**: Runs in PLAN_ONLY mode by default
- 🔁 **Resumable**: Continue from where you left off after failures
- 📊 **Real-time Monitoring**: Track progress through web UI

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React UI  │────▶│  FastAPI    │────▶│  MongoDB    │
│  (Frontend) │     │  (Backend)  │     │  (Database) │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ├────▶┌─────────────┐
                           │     │    Redis    │
                           │     │ (Queue/Cache)│
                           │     └─────────────┘
                           │
                           └────▶┌─────────────┐
                                 │   Celery    │
                                 │  (Workers)  │
                                 └─────────────┘
                                       │
                            ┌──────────┴──────────┐
                            │                     │
                       Agents                 Storage
                    ┌─────────┐           ┌──────────┐
                    │Discovery│           │Artifacts │
                    │ Export  │           │  JSON    │
                    │Transform│           │ Workflows│
                    │  Plan   │           │  Logs    │
                    │  Apply  │           └──────────┘
                    │ Verify  │
                    └─────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Git
- 4GB+ RAM recommended

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/moti-malka/gl2gh.git
   cd gl2gh
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and set your SECRET_KEY and APP_MASTER_KEY
   nano .env
   ```

3. **Start the platform:**
   ```bash
   ./start.sh
   ```

That's it! The platform will start all services automatically.

### Access the Platform

Once started, access these endpoints:

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### View Logs

```bash
./start.sh logs
```

### Stop the Platform

```bash
./start.sh stop
```

## 📚 Usage

### 1. Create a Migration Project

Navigate to http://localhost:3000 and:
1. Click "New Project"
2. Enter project details
3. Configure GitLab and GitHub settings

### 2. Add Credentials

- Add GitLab Personal Access Token (PAT) with `read_api` and `read_repository` scopes
- Add GitHub PAT with `repo`, `workflow`, and `admin:org` scopes

### 3. Run Discovery

Start with a DISCOVER_ONLY run to:
- Scan GitLab groups and projects
- Assess migration readiness
- Identify blockers and complexity

### 4. Generate Plan

Run in PLAN_ONLY mode (default) to:
- Convert GitLab CI to GitHub Actions
- Generate gap analysis
- Create executable migration plan
- Review before applying

### 5. Execute Migration

When ready, switch to APPLY mode to:
- Create GitHub repositories
- Push code and workflows
- Set up branch protections
- Configure environments

### 6. Verify Results

Run verification to:
- Validate repositories exist
- Check branch/tag counts
- Verify workflows are valid
- Generate success report

## 🛠️ Development

### Project Structure

```
gl2gh/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # REST API endpoints
│   │   ├── agents/      # Migration agents
│   │   ├── db/          # Database layer
│   │   ├── models/      # Data models
│   │   ├── services/    # Business logic
│   │   ├── workers/     # Celery tasks
│   │   └── utils/       # Utilities
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/            # React frontend
│   ├── src/
│   │   ├── pages/      # Page components
│   │   ├── components/ # Reusable components
│   │   └── api/        # API client
│   ├── Dockerfile
│   └── package.json
├── discovery_agent/     # Existing discovery agent
├── shared/              # Shared schemas and docs
├── artifacts/           # Migration artifacts (generated)
├── docker-compose.yml   # Service orchestration
├── start.sh            # Start script
└── .env.example        # Environment template
```

### Running in Development Mode

The docker-compose setup includes hot-reload for both frontend and backend:

```bash
# Start in development mode (default)
./start.sh up

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f worker
docker-compose logs -f frontend

# Restart a specific service
docker-compose restart backend

# Open shell in backend
./start.sh shell-backend

# Open shell in worker
./start.sh shell-worker
```

### Running Tests

```bash
# Backend tests
docker-compose exec backend pytest

# Frontend tests
docker-compose exec frontend npm test

# Run existing discovery agent tests
pytest tests/
```

## 🔐 Security

### Token Storage

- All PATs are encrypted using `APP_MASTER_KEY`
- Only last 4 characters stored in plain text
- Tokens never logged or displayed

### Secret Masking

- Automatic redaction of tokens in logs
- Pattern-based masking for GitLab/GitHub PATs
- Structured logging with sensitive data protection

### RBAC

Three roles supported:
- **Admin**: Full platform access
- **Operator**: Can create and run migrations
- **Viewer**: Read-only access

## 🤖 Agents

### Discovery Agent
Scans GitLab groups and projects, assesses complexity, detects CI/CD, LFS, and generates readiness reports.

### Export Agent
Exports git repositories (as bundles), CI files, branch protections, and variables metadata.

### Transform Agent
Converts GitLab CI to GitHub Actions, maps variables to secrets, and generates conversion gap reports.

### Plan Agent
Creates ordered, executable migration plans with dependencies and manual steps identified.

### Apply Agent
Executes the plan: creates repos, pushes code, adds workflows, sets protections, creates environments.

### Verify Agent
Validates migration: checks repo exists, compares ref counts, verifies workflows, optional smoke tests.

## 📊 Migration Stages

```
DISCOVER → EXPORT → TRANSFORM → PLAN → APPLY → VERIFY
    ↓         ↓         ↓         ↓       ↓       ↓
 inventory  bundles  workflows  plan.json GitHub  report
```

Each stage:
- Produces deterministic JSON artifacts
- Tracks progress per project
- Handles errors gracefully
- Supports resume on failure

## ⚙️ Configuration

### Environment Variables

See `.env.example` for all configuration options. Key variables:

```bash
# Security (REQUIRED - change these!)
SECRET_KEY=your-jwt-secret-key
APP_MASTER_KEY=your-encryption-master-key

# Database
MONGO_URL=mongodb://mongo:27017
REDIS_URL=redis://redis:6379/0

# Rate Limiting
MAX_API_CALLS=5000
MAX_PER_PROJECT_CALLS=200

# Concurrency
MAX_CONCURRENT_PROJECTS=5
```

## 🔧 API Reference

Full API documentation available at http://localhost:8000/docs when the platform is running.

### Key Endpoints

- `POST /api/auth/login` - Authenticate
- `POST /api/projects` - Create migration project
- `POST /api/projects/{id}/connections/gitlab` - Add GitLab credentials
- `POST /api/projects/{id}/connections/github` - Add GitHub credentials
- `POST /api/projects/{id}/runs` - Start migration run
- `GET /api/runs/{id}` - Get run status
- `GET /api/runs/{id}/events` - Stream events

## 📖 Documentation

- [Architecture Guide](docs/architecture.md) - System design and components
- [Agent Framework](docs/agents.md) - Agent roles and responsibilities  
- [API Reference](http://localhost:8000/docs) - OpenAPI documentation
- [Development Guide](docs/development.md) - Contributing and extending

## 🗺️ Roadmap

### Phase 1: Core Platform (Current)
- [x] Project structure and infrastructure
- [x] Database models and API skeleton
- [x] Docker Compose setup
- [ ] Authentication and authorization
- [ ] Agent integration
- [ ] Basic UI

### Phase 2: Agent Implementation
- [ ] Discovery Agent integration
- [ ] Export Agent
- [ ] Transform Agent (CI conversion)
- [ ] Plan Agent
- [ ] Apply Agent (GitHub writes)
- [ ] Verify Agent

### Phase 3: Advanced Features
- [ ] WebSocket real-time updates
- [ ] Resume functionality
- [ ] Partial migrations
- [ ] Rollback support
- [ ] Advanced CI conversion
- [ ] LFS migration

### Phase 4: Production Ready
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Security audit
- [ ] Monitoring and observability
- [ ] Multi-tenancy
- [ ] Cloud deployment guides

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built with FastAPI, React, MongoDB, and Celery
- Inspired by the need for safe, deterministic GitLab → GitHub migrations
- Uses Microsoft Agent Framework concepts for orchestration

## 💬 Support

- Issues: https://github.com/moti-malka/gl2gh/issues
- Discussions: https://github.com/moti-malka/gl2gh/discussions

---

**Built with ❤️ for the migration community**
