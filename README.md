# gl2gh - GitLab to GitHub Agentic Migration Platform

![Architecture](https://img.shields.io/badge/architecture-microservices-blue)
![Status](https://img.shields.io/badge/status-development-yellow)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)

> **A comprehensive, agent-based platform for migrating GitLab groups and projects to GitHub with intelligent CI/CD conversion, validation, and safe execution.**

Powered by **Microsoft Agent Framework** for enterprise-grade AI agent orchestration.

## 🌟 Key Features

### Migration Platform
- 🤖 **6 Specialized Agents**: Discovery, Export, Transform, Plan, Apply, Verify
- 🔄 **Complete Migration Pipeline**: From GitLab scan to GitHub validation
- 🎯 **14 Component Types**: Code, CI/CD, Issues, MRs→PRs, Wiki, Releases, Packages, Settings, Webhooks, and more
- 📋 **Safe by Default**: Runs in PLAN_ONLY mode - no GitHub writes without explicit confirmation
- 🔁 **Resumable Operations**: Continue from any failure point
- 🌐 **Web UI**: Real-time monitoring and control through React interface
- 📊 **REST API**: Complete API for programmatic control (FastAPI + OpenAPI)

### Discovery Agent (Built-in)
- 🔍 **Deep Group Scanning**: Recursively scans all subgroups under a root group
- 📊 **Project Inventory**: Collects detailed information about each project
- ✅ **Migration Readiness**: Evaluates complexity and identifies blockers
- 🎯 **Deep Analysis**: Calculates work scores (0-100) and buckets (S/M/L/XL)
- 🔄 **CI/CD Detection**: Identifies projects with GitLab CI configuration
- 📦 **LFS Detection**: Detects Git LFS usage

### CI/CD Conversion
- ⚙️ **GitLab CI → GitHub Actions**: Intelligent conversion of workflows
- 🔑 **Variable Mapping**: Convert CI variables to GitHub secrets/vars
- 🛡️ **Branch Protections**: Map GitLab protections to GitHub rulesets
- 🌍 **Environments**: Create and configure GitHub environments
- 📝 **Gap Analysis**: Detailed report of unsupported features

### Security & Reliability
- 🔐 **Encrypted Credentials**: All PATs encrypted at rest (Fernet)
- 🎭 **Secret Masking**: Automatic token redaction in logs
- 🔒 **RBAC**: Admin, Operator, and Viewer roles
- ⏱️ **Rate Limit Handling**: Exponential backoff for GitLab and GitHub APIs
- 🔄 **Idempotent Operations**: Safe to retry any step
- 📄 **Deterministic Output**: Same inputs → same outputs

## 🏗️ Architecture

The platform uses a microservices architecture powered by Microsoft Agent Framework:

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
                     Agents (MAF)            Storage
                  ┌─────────────┐        ┌──────────┐
                  │ Discovery   │        │Artifacts │
                  │ Export      │        │  JSON    │
                  │ Transform   │        │ Workflows│
                  │ Plan        │        │  Logs    │
                  │ Apply       │        │ Reports  │
                  │ Verify      │        └──────────┘
                  └─────────────┘
```

### Components

1. **React Frontend**: Web UI for project management and monitoring
2. **FastAPI Backend**: REST API with async Python 3.11
3. **MongoDB**: Persistent storage for projects, runs, and events
4. **Redis**: Message queue and caching
5. **Celery Workers**: Background job processing
6. **Microsoft Agent Framework**: AI agent orchestration and workflow management
7. **Artifact Storage**: File system storage for migration artifacts

### Data Flow

```
User → UI → API → Database → Queue → Worker → Agent → Storage
                      ↓                         ↓
                   Events ←──────────────── Progress
```

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- 4GB+ RAM recommended
- Git
- Ports available: 3000, 8000, 6379, 27017

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

### Common Commands

```bash
# View logs
./start.sh logs

# Stop services
./start.sh stop

# Restart services
./start.sh restart

# Check health
./health-check.sh

# Open backend shell
./start.sh shell-backend
```

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

## 🎯 Migration Workflow

### Complete Migration Pipeline

```
DISCOVER → EXPORT → TRANSFORM → PLAN → APPLY → VERIFY
    ↓         ↓         ↓          ↓       ↓       ↓
 inventory  bundles  workflows  plan.json GitHub  report
```

### 1. Discovery Phase
Scan GitLab to understand what needs migrating:
- List all groups and projects
- Assess complexity and readiness
- Detect CI/CD, LFS, issues, MRs
- Generate inventory and scores

### 2. Export Phase
Download everything from GitLab:
- Git repository (as bundle)
- CI configuration files
- Issues and merge requests
- Wiki pages and releases
- Settings and permissions

### 3. Transform Phase
Convert GitLab concepts to GitHub equivalents:
- GitLab CI → GitHub Actions workflows
- Variables → Secrets/Environment variables
- Branch protections → GitHub rulesets
- User mapping (GitLab → GitHub)
- Generate conversion gap analysis

### 4. Plan Phase
Create executable migration plan:
- Ordered list of actions
- Dependency resolution
- Idempotency keys
- Manual steps identified
- Review before execution

### 5. Apply Phase (Optional)
Execute the plan on GitHub:
- Create repositories
- Push code and workflows
- Import issues and PRs
- Set up protections and environments
- Configure webhooks

### 6. Verify Phase
Validate migration success:
- Check repository exists
- Verify branch/tag counts
- Validate workflows (YAML syntax)
- Compare settings
- Generate success report

### Running Migrations

#### Web UI (Recommended)

1. Navigate to http://localhost:3000
2. Create a new Migration Project
3. Add GitLab and GitHub credentials
4. Configure migration settings
5. Start a run (choose mode: DISCOVER_ONLY, PLAN_ONLY, APPLY, FULL)
6. Monitor progress in real-time

#### API (Programmatic)

```bash
# Create project
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My Migration", "settings": {...}}'

# Add credentials
curl -X POST http://localhost:8000/api/projects/{id}/connections/gitlab \
  -H "Content-Type: application/json" \
  -d '{"token": "glpat-xxx", "base_url": "https://gitlab.com"}'

# Start migration run
curl -X POST http://localhost:8000/api/projects/{id}/runs \
  -H "Content-Type: application/json" \
  -d '{"mode": "PLAN_ONLY"}'

# Check status
curl http://localhost:8000/api/runs/{run_id}
```

See full API documentation at http://localhost:8000/docs

## 🤖 Microsoft Agent Framework Integration

The platform uses Microsoft Agent Framework (MAF) for enterprise-grade agent orchestration:

### 6 Specialized Agents

#### 1. Discovery Agent
- **Purpose**: Scan GitLab groups and assess migration readiness
- **Outputs**: `inventory.json`, `summary.txt`, `readiness_report.json`
- **Features**: Deep analysis, complexity scoring, blocker detection

#### 2. Export Agent
- **Purpose**: Extract all data from GitLab
- **Exports**: Repo bundles, CI files, issues, MRs, wiki, releases, settings
- **Outputs**: `export_manifest.json`, organized export folder structure

#### 3. Transform Agent
- **Purpose**: Convert GitLab concepts to GitHub equivalents
- **Transforms**: CI workflows, variables, protections, user mappings
- **Outputs**: GitHub Actions workflows, `conversion_gaps.json`

#### 4. Plan Agent
- **Purpose**: Generate executable migration plan
- **Creates**: Ordered actions with dependencies and idempotency keys
- **Outputs**: `plan.json`, `plan.md` (human-readable)

#### 5. Apply Agent
- **Purpose**: Execute migration plan on GitHub
- **Actions**: Create repos, push code, set protections, configure CI/CD
- **Outputs**: `apply_report.json`, `apply_log.md`

#### 6. Verify Agent
- **Purpose**: Validate migration results
- **Checks**: Repo existence, ref counts, workflow validity, settings
- **Outputs**: `verify_report.json`, `verify_summary.md`

### Agent Orchestration

Agents work together through the orchestrator:

```python
from app.agents import AgentOrchestrator, MigrationMode

orchestrator = AgentOrchestrator()
result = await orchestrator.run_migration(
    mode=MigrationMode.FULL,
    config={
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "glpat-xxx",
        "github_token": "ghp-xxx",
        "github_org": "my-org"
    }
)
```

See [Microsoft Agent Framework Documentation](docs/MICROSOFT_AGENT_FRAMEWORK.md) for details.

## 📊 Migration Scope

The platform migrates **14 component types** from GitLab to GitHub:

1. **Repository & Git Data** - Code, branches, tags, submodules, history
2. **Git LFS** - Large file storage objects and configuration
3. **CI/CD** - Workflows, environments, schedules, variables/secrets
4. **Merge Requests → Pull Requests** - With discussions and reviews
5. **Issues** - With comments, attachments, cross-references
6. **Wiki** - Pages, history, attachments
7. **Releases** - With assets and release notes
8. **Packages/Registry** - Container, NPM, Maven, PyPI, Generic packages
9. **Settings & Governance** - Branch protections, permissions, members
10. **Variables/Secrets** - CI/CD variables with environment scoping
11. **Webhooks & Integrations** - Event subscriptions
12. **CI Schedules** - Cron-based pipeline triggers
13. **Pipeline History** - Preserved as artifacts
14. **Boards/Epics** - Mapped to GitHub Projects

Each component follows the complete Export → Transform → Apply → Verify chain.

See [Migration Coverage](docs/MIGRATION_COVERAGE.md) for detailed specifications.

## 📁 Output & Artifacts

The platform generates comprehensive artifacts for each migration:

### Discovery Artifacts

**`inventory.json`** - Complete project inventory:

```json
{
  "run": {
    "started_at": "2024-01-15T10:00:00+00:00",
    "finished_at": "2024-01-15T10:15:00+00:00",
    "base_url": "https://gitlab.com",
    "root_group": "my-organization",
    "stats": {
      "groups": 5,
      "projects": 42,
      "errors": 2,
      "api_calls": 350
    }
  },
  "groups": [
    {
      "id": 12345,
      "full_path": "my-organization",
      "projects": [1, 2, 3]
    }
  ],
  "projects": [
    {
      "id": 1,
      "path_with_namespace": "my-organization/my-project",
      "default_branch": "main",
      "archived": false,
      "visibility": "private",
      "facts": {
        "has_ci": true,
        "has_lfs": false,
        "mr_counts": {"open": 5, "merged": 100, "closed": 10, "total": 115},
        "issue_counts": {"open": 20, "closed": 80, "total": 100},
        "repo_profile": {
          "branches_count": 15,
          "tags_count": 42,
          "has_submodules": false,
          "has_lfs": false
        },
        "ci_profile": {
          "present": true,
          "total_lines": 120,
          "features": {"include": true, "services": true, "rules": true},
          "runner_hints": {"uses_tags": true, "docker_in_docker": true}
        },
        "migration_estimate": {
          "work_score": 45,
          "bucket": "M",
          "drivers": ["Has GitLab CI configuration", "Uses includes", "Uses services"]
        }
      },
      "readiness": {
        "complexity": "medium",
        "blockers": ["Has GitLab CI/CD pipeline - requires conversion to GitHub Actions"],
        "notes": ["Consider renaming default branch from 'master' to 'main'"]
      },
      "errors": []
    }
  ]
}
```

```

**`summary.txt`** - Human-readable summary of the discovery run

### Transform Artifacts

- **`workflows/`** - Generated GitHub Actions workflows
- **`conversion_gaps.json`** - Unsupported features and manual steps
- **`user_mapping.json`** - GitLab ↔ GitHub user identity mapping

### Plan Artifacts

- **`plan.json`** - Executable migration plan with ordered actions
- **`plan.md`** - Human-readable plan description

### Apply Artifacts

- **`apply_report.json`** - What was created/modified in GitHub
- **`apply_log.md`** - Detailed execution log

### Verify Artifacts

- **`verify_report.json`** - Validation results per component
- **`verify_summary.md`** - Overall migration success assessment

All artifacts are stored in `artifacts/runs/{run_id}/` with deterministic, schema-validated JSON.

## 🔐 Security & Token Requirements

### GitLab Personal Access Token

Required scopes:
- `read_api` - List groups, projects, merge requests, issues
- `read_repository` - Read `.gitlab-ci.yml`, `.gitattributes` files

### GitHub Personal Access Token

Required scopes:
- `repo` - Create and manage repositories
- `workflow` - Create and update workflows
- `admin:org` - Manage organization teams and permissions

### Token Security

- All PATs encrypted at rest using `APP_MASTER_KEY` (Fernet encryption)
- Automatic secret masking in logs (glpat-*, ghp-*)
- Only last 4 characters stored in plain text for display
- Tokens never logged or exposed in API responses

## ⚙️ Configuration

### Environment Variables

Key variables in `.env`:

```bash
# Security (REQUIRED - change these!)
SECRET_KEY=your-jwt-secret-key
APP_MASTER_KEY=your-encryption-master-key

# Database
MONGO_URL=mongodb://mongo:27017
REDIS_URL=redis://redis:6379/0

# API Limits
MAX_API_CALLS=5000
MAX_PER_PROJECT_CALLS=200

# Concurrency
MAX_CONCURRENT_PROJECTS=5
CELERY_WORKER_CONCURRENCY=4
```

See `.env.example` for all configuration options.

## 🧪 Running Tests

```bash
# Backend tests
docker-compose exec backend pytest

# Frontend tests  
docker-compose exec frontend npm test

# Discovery agent tests (standalone)
pytest tests/

# Run all tests
./run-tests.sh
```

## 🛠️ Development

### Project Structure

```
gl2gh/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── agents/      # MAF-based migration agents
│   │   ├── api/         # REST API endpoints
│   │   ├── db/          # Database layer
│   │   ├── models/      # Pydantic models
│   │   ├── services/    # Business logic
│   │   ├── workers/     # Celery tasks
│   │   └── utils/       # Utilities
│   └── requirements.txt
├── frontend/            # React frontend
│   ├── src/
│   │   ├── pages/      # Page components
│   │   └── components/ # Reusable components
│   └── package.json
├── discovery_agent/     # Standalone discovery module
├── docs/               # Documentation
│   ├── ARCHITECTURE.md
│   ├── MIGRATION_COVERAGE.md
│   ├── USER_MAPPING.md
│   ├── PLAN_SCHEMA.md
│   └── MICROSOFT_AGENT_FRAMEWORK.md
├── artifacts/          # Generated migration artifacts
├── docker-compose.yml  # Service orchestration
└── start.sh           # Platform control script
```

### Running Standalone Discovery Agent

The discovery agent can still be run independently:

```bash
# Install dependencies
pip install -e ".[dev]"

# Run discovery
python -m discovery_agent \
  --base-url https://gitlab.com \
  --token glpat-xxxxxxxxxxxxxxxxxxxx \
  --root-group my-organization \
  --out ./output

# Deep analysis mode
python -m discovery_agent --deep --deep-top-n 50

# Serve web dashboard
python -m discovery_agent serve --port 8080 --dir ./output
```

See the standalone agent section below for detailed CLI options.

## 📖 Documentation

Comprehensive documentation is available:

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[README_PLATFORM.md](README_PLATFORM.md)** - Detailed platform overview
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and components
- **[MICROSOFT_AGENT_FRAMEWORK.md](docs/MICROSOFT_AGENT_FRAMEWORK.md)** - MAF integration guide
- **[MIGRATION_COVERAGE.md](docs/MIGRATION_COVERAGE.md)** - All 14 components specifications
- **[USER_MAPPING.md](docs/USER_MAPPING.md)** - Identity resolution algorithms
- **[PLAN_SCHEMA.md](docs/PLAN_SCHEMA.md)** - Plan format and execution model
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Development roadmap

API documentation is auto-generated and available at http://localhost:8000/docs when running.

## 🗺️ Roadmap & Status

### ✅ Phase 1: Foundation (Complete)
- [x] Docker Compose infrastructure
- [x] FastAPI backend with MongoDB
- [x] React frontend
- [x] Security layer (encryption, JWT, masking)
- [x] Microsoft Agent Framework integration
- [x] Comprehensive specifications (82KB documentation)

### 🚧 Phase 2: Agent Implementation (In Progress)
- [x] Discovery Agent (integrated from standalone)
- [ ] Export Agent (80 hours estimated)
- [ ] Transform Agent (100 hours estimated)
- [ ] Plan Agent (60 hours estimated)
- [ ] Apply Agent (120 hours estimated)
- [ ] Verify Agent (60 hours estimated)

### 📅 Phase 3: Advanced Features (Planned)
- [ ] WebSocket real-time updates
- [ ] Resume functionality
- [ ] Partial migrations
- [ ] Advanced CI conversion
- [ ] LFS migration automation

### 🎯 Phase 4: Production Ready (Planned)
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Security audit
- [ ] Monitoring and observability
- [ ] Multi-tenancy support

**Total Estimated Effort**: 730 hours | **Critical Path (MVP)**: 460 hours

## 🔧 Standalone Discovery Agent

The original discovery agent is still available as a standalone CLI tool:

### Installation

```bash
pip install -e ".[dev]"
```

### Usage

```bash
# Scan a specific group
python -m discovery_agent \
  --base-url https://gitlab.com \
  --token glpat-xxxxxxxxxxxxxxxxxxxx \
  --root-group my-organization \
  --out ./output

# Scan ALL accessible groups
python -m discovery_agent \
  --base-url https://gitlab.com \
  --token glpat-xxxxxxxxxxxxxxxxxxxx \
  --out ./output

# Deep analysis mode
python -m discovery_agent --deep --deep-top-n 50

# Web dashboard
python -m discovery_agent serve --port 8080 --dir ./output
```

### CLI Options

```
usage: discovery_agent [-h] [--version] [--base-url URL] [--token TOKEN]
                       [--root-group GROUP] [--out DIR] [--max-api-calls N]
                       [--max-per-project-calls N] [--deep] [--deep-top-n N]
                       [-v] [-q]

options:
  --base-url URL        GitLab instance URL (e.g., https://gitlab.com)
  --token TOKEN         Personal Access Token for authentication
  --root-group GROUP    Root group to scan (omit to scan ALL accessible groups)
  --out DIR             Output directory for inventory.json (default: ./output)
  --max-api-calls N     Maximum total API calls (default: 5000)
  --max-per-project-calls N
                        Maximum API calls per project (default: 200)
  --deep                Enable deep analysis with migration scoring
  --deep-top-n N        Limit deep analysis to top N projects (default: 20, 0=all)
  -v, --verbose         Enable verbose (debug) logging
  -q, --quiet           Suppress all output except errors
```

### Environment Variables for Standalone Mode

```bash
# .env
GITLAB_BASE_URL=https://gitlab.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_ROOT_GROUP=my-organization  # Optional
OUTPUT_DIR=./output
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for development priorities.

## 💬 Support

- **Issues**: https://github.com/moti-malka/gl2gh/issues
- **Discussions**: https://github.com/moti-malka/gl2gh/discussions
- **Security**: See [SECURITY_ADVISORY.md](SECURITY_ADVISORY.md)

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built with **FastAPI**, **React**, **MongoDB**, **Celery**, and **Redis**
- Powered by **Microsoft Agent Framework** for enterprise-grade agent orchestration
- Inspired by the need for safe, deterministic GitLab → GitHub migrations

---

**Built with ❤️ for the migration community**

*Transform your GitLab projects to GitHub with confidence using intelligent agents.*
