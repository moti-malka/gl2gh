# Architecture Documentation

## System Overview

gl2gh is a microservices-based migration platform built with:

- **Backend**: FastAPI (Python 3.11+)
- **Database**: MongoDB (NoSQL)
- **Queue**: Redis + Celery
- **Frontend**: React 18
- **Orchestration**: Docker Compose

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (React)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Login   │  │ Projects │  │   Runs   │  │ Artifacts│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  API Layer                                             │ │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐   │ │
│  │  │ Auth │ │ Proj │ │ Runs │ │ Conn │ │ Events   │   │ │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Services Layer                                        │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │ │
│  │  │Project │ │  Run   │ │  Event │ │ Conn   │        │ │
│  │  │Service │ │Service │ │Service │ │Service │        │ │
│  │  └────────┘ └────────┘ └────────┘ └────────┘        │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────┬────────────────────────┬───────────────────┘
                 │                        │
                 ▼                        ▼
        ┌────────────────┐      ┌────────────────┐
        │    MongoDB     │      │  Redis/Celery  │
        │                │      │                │
        │  • users       │      │  • Task Queue  │
        │  • projects    │      │  • Results     │
        │  • runs        │      │  • Cache       │
        │  • events      │      └────────────────┘
        │  • artifacts   │               │
        └────────────────┘               │
                                         ▼
                                ┌────────────────┐
                                │ Celery Workers │
                                │                │
                                │  ┌──────────┐  │
                                │  │  Agents  │  │
                                │  └──────────┘  │
                                │  • Discovery   │
                                │  • Export      │
                                │  • Transform   │
                                │  • Plan        │
                                │  • Apply       │
                                │  • Verify      │
                                └────────────────┘
                                         │
                                         ▼
                                ┌────────────────┐
                                │   Artifacts    │
                                │   Storage      │
                                │                │
                                │  • JSON files  │
                                │  • Workflows   │
                                │  • Reports     │
                                │  • Logs        │
                                └────────────────┘
```

## Data Flow

### 1. User Creates Migration Project

```
User → Frontend → API (POST /api/projects)
                → Services (ProjectService)
                → MongoDB (projects collection)
```

### 2. User Starts Migration Run

```
User → Frontend → API (POST /api/projects/{id}/runs)
                → Services (RunService)
                → MongoDB (runs collection)
                → Celery (enqueue discovery task)
                → Worker picks up task
                → Agent executes
                → Events → MongoDB (events collection)
                → Artifacts → Filesystem
                → Status updates → MongoDB
                → WebSocket → Frontend (real-time)
```

### 3. Agent Execution Flow

```
Orchestrator
    ↓
Discovery Agent → MongoDB (projects discovered)
    ↓
Export Agent → Artifacts (repo bundles, CI files)
    ↓
Transform Agent → Artifacts (workflows, conversion gaps)
    ↓
Plan Agent → Artifacts (migration plan)
    ↓
Apply Agent → GitHub API (create resources)
    ↓
Verify Agent → GitHub API (validate) → Report
```

## Database Schema

### Collections

#### users
```javascript
{
  _id: ObjectId,
  email: string,
  username: string,
  hashed_password: string,
  role: "admin" | "operator" | "viewer",
  is_active: boolean,
  created_at: datetime,
  updated_at: datetime
}
```

#### migration_projects
```javascript
{
  _id: ObjectId,
  name: string,
  description: string?,
  created_by: ObjectId (ref: users),
  created_at: datetime,
  updated_at: datetime,
  settings: {
    gitlab: {
      base_url: string,
      root_group: string?
    },
    github: {
      org: string
    },
    budgets: {
      max_api_calls: int,
      max_per_project_calls: int
    },
    behavior: {
      default_run_mode: string,
      rename_default_branch_to: string?,
      include_archived: boolean
    }
  },
  status: "active" | "archived"
}
```

#### connections
```javascript
{
  _id: ObjectId,
  project_id: ObjectId (ref: migration_projects),
  type: "gitlab" | "github",
  base_url: string?,
  token_encrypted: string,  // Fernet encrypted
  token_last4: string,       // For display only
  created_at: datetime,
  updated_at: datetime
}
```

#### migration_runs
```javascript
{
  _id: ObjectId,
  project_id: ObjectId (ref: migration_projects),
  mode: "FULL" | "PLAN_ONLY" | "DISCOVER_ONLY" | "APPLY" | "VERIFY",
  status: "CREATED" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELED",
  stage: "DISCOVER" | "EXPORT" | "TRANSFORM" | "PLAN" | "APPLY" | "VERIFY"?,
  started_at: datetime?,
  finished_at: datetime?,
  stats: {
    groups: int,
    projects: int,
    errors: int,
    api_calls: int
  },
  config_snapshot: object,
  artifact_root: string?,
  error: {
    message: string,
    stack: string
  }?,
  created_at: datetime
}
```

#### run_projects
```javascript
{
  _id: ObjectId,
  run_id: ObjectId (ref: migration_runs),
  gitlab_project_id: int,
  path_with_namespace: string,
  bucket: "S" | "M" | "L" | "XL"?,
  facts: object,
  readiness: object,
  stage_status: {
    discover: "PENDING" | "DONE" | "FAILED",
    export: "PENDING" | "DONE" | "FAILED",
    transform: "PENDING" | "DONE" | "FAILED",
    plan: "PENDING" | "DONE" | "FAILED",
    apply: "PENDING" | "DONE" | "FAILED",
    verify: "PENDING" | "DONE" | "FAILED"
  },
  errors: array,
  created_at: datetime,
  updated_at: datetime
}
```

#### events
```javascript
{
  _id: ObjectId,
  run_id: ObjectId (ref: migration_runs),
  timestamp: datetime,
  level: "INFO" | "WARN" | "ERROR" | "DEBUG",
  agent: string?,
  scope: "run" | "project",
  gitlab_project_id: int?,
  message: string,
  payload: object
}
```

#### artifacts
```javascript
{
  _id: ObjectId,
  run_id: ObjectId (ref: migration_runs),
  project_id: ObjectId?,
  gitlab_project_id: int?,
  type: string,  // "inventory", "plan", "workflow", etc.
  path: string,  // Relative from artifact_root
  size_bytes: int?,
  created_at: datetime,
  metadata: object
}
```

## Security Architecture

### Token Encryption

```
User PAT (plain) → Fernet.encrypt(key=derived_from_APP_MASTER_KEY)
                 → Encrypted token stored in MongoDB
                 → Last 4 chars stored separately for UI display
```

Key derivation:
```python
key = sha256(APP_MASTER_KEY).digest()
fernet_key = base64.urlsafe_b64encode(key)
cipher = Fernet(fernet_key)
```

### Authentication Flow

```
User credentials → API (/api/auth/login)
                 → Verify password (bcrypt)
                 → Generate JWT token
                 → Return token to client
                 → Client stores in localStorage/cookie
                 → Client sends in Authorization header
                 → API verifies JWT
                 → Extract user info
                 → Check RBAC permissions
                 → Process request
```

### Secret Masking

All logs pass through masking filter:
```python
log_message → mask_sensitive_data() → masked_log
```

Patterns masked:
- `glpat-*` → `glpat-****`
- `ghp_*` → `ghp_****`
- `github_pat_*` → `github_pat_****`
- `Bearer *` → `Bearer ****`

## Agent Architecture

### Agent Contract

Each agent must implement:

```python
class BaseAgent:
    def validate_input(self, config: dict) -> bool
    def execute(self, config: dict) -> dict
    def handle_error(self, error: Exception) -> dict
    def generate_artifact(self, data: dict) -> str
```

### Agent Communication

Agents communicate via:
1. **MongoDB** - State updates
2. **Artifacts** - File outputs
3. **Events** - Progress logs

```
Agent → MongoDB (update run_projects.stage_status)
      → Artifacts (write JSON/YAML files)
      → Events (log progress messages)
```

### Discovery Agent Integration

Wraps existing `discovery_agent` module:

```python
from discovery_agent.orchestrator import run_discovery

def run_discovery_task(run_id, config):
    # Call existing discovery logic
    result = run_discovery(
        base_url=config['gitlab_url'],
        token=decrypt_token(config['token_encrypted']),
        root_group=config.get('root_group'),
        output_dir=f"artifacts/runs/{run_id}/discovery"
    )
    
    # Store results in MongoDB
    for project in result['projects']:
        store_project(run_id, project)
    
    # Emit events
    emit_event(run_id, "Discovery completed", payload=result['stats'])
```

## Celery Task Architecture

### Task Types

1. **Orchestrator Task** - Manages pipeline
2. **Agent Tasks** - Individual agent execution
3. **Project Tasks** - Per-project operations

### Task Graph

```
orchestrator_task(run_id)
    ↓
discovery_task(run_id) → [results]
    ↓
parallel([
    export_task(run_id, project_1),
    export_task(run_id, project_2),
    ...
]) → [results]
    ↓
parallel([
    transform_task(run_id, project_1),
    transform_task(run_id, project_2),
    ...
]) → [results]
    ↓
plan_task(run_id) → [plan]
    ↓
IF mode == "APPLY":
    parallel([
        apply_task(run_id, project_1),
        apply_task(run_id, project_2),
        ...
    ]) → [results]
    ↓
    parallel([
        verify_task(run_id, project_1),
        verify_task(run_id, project_2),
        ...
    ]) → [results]
```

### Task Idempotency

Each task computes idempotency key:
```python
key = f"{run_id}:{agent_name}:{project_id}:{input_hash}"
```

Before execution:
1. Check if task with key already completed
2. If yes, return cached result
3. If no, execute and mark complete

## API Architecture

### Endpoint Organization

```
/api/
  /auth/
    POST   /login
    POST   /logout
    GET    /me
  
  /projects/
    POST   /                          # Create project
    GET    /                          # List projects
    GET    /{project_id}              # Get project
    PUT    /{project_id}              # Update project
    DELETE /{project_id}              # Delete project
    
    POST   /{project_id}/connections/gitlab   # Add GitLab creds
    POST   /{project_id}/connections/github   # Add GitHub creds
    GET    /{project_id}/connections          # List connections
    
    POST   /{project_id}/runs         # Create run
    GET    /{project_id}/runs         # List runs
  
  /runs/
    GET    /{run_id}                  # Get run status
    POST   /{run_id}/cancel           # Cancel run
    POST   /{run_id}/resume           # Resume run
    GET    /{run_id}/artifacts        # List artifacts
    GET    /{run_id}/plan             # Get plan
    POST   /{run_id}/apply            # Execute apply
    POST   /{run_id}/verify           # Run verify
    
    GET    /{run_id}/events           # Get events (paginated)
    GET    /{run_id}/projects         # Get projects in run
    GET    /{run_id}/projects/{gitlab_project_id}  # Get project detail
  
  /ws/runs/{run_id}                   # WebSocket for real-time updates
```

### Request/Response Flow

```
Client Request
    ↓
FastAPI Router
    ↓
Authentication Middleware (verify JWT)
    ↓
RBAC Check (verify permissions)
    ↓
Request Validation (Pydantic)
    ↓
Service Layer (business logic)
    ↓
Database Layer (MongoDB queries)
    ↓
Response Serialization (Pydantic)
    ↓
Secret Masking (if applicable)
    ↓
Client Response
```

## Frontend Architecture

### Component Structure

```
src/
  ├── components/       # Reusable components
  │   ├── Navbar.js
  │   ├── ProjectCard.js
  │   ├── RunDashboard.js
  │   ├── EventTimeline.js
  │   └── ...
  │
  ├── pages/           # Page components
  │   ├── Home.js
  │   ├── Login.js
  │   ├── Projects.js
  │   ├── ProjectDetail.js
  │   ├── RunDetail.js
  │   └── ...
  │
  ├── api/             # API client
  │   ├── client.js    # Axios instance
  │   ├── projects.js  # Project API calls
  │   ├── runs.js      # Run API calls
  │   └── ...
  │
  ├── state/           # State management
  │   ├── auth.js
  │   ├── projects.js
  │   └── ...
  │
  └── App.js           # Main app with routing
```

### State Management

Using React Context + Hooks:

```javascript
AuthContext → Current user, JWT token
ProjectsContext → Projects list, selected project
RunsContext → Runs list, selected run, events
```

### WebSocket Integration

```javascript
// Connect to run events
const ws = new WebSocket(`ws://localhost:8000/ws/runs/${runId}`)

ws.onmessage = (event) => {
  const update = JSON.parse(event.data)
  
  if (update.type === 'status') {
    updateRunStatus(update.data)
  } else if (update.type === 'event') {
    addEvent(update.data)
  } else if (update.type === 'project_progress') {
    updateProjectProgress(update.data)
  }
}
```

## Deployment Architecture

### Docker Compose (Development)

```yaml
services:
  mongo:     # Port 27017
  redis:     # Port 6379
  backend:   # Port 8000
  worker:    # No exposed ports
  frontend:  # Port 3000
```

### Production (Kubernetes - Future)

```
┌──────────────────────────────────────────────┐
│              Load Balancer                    │
└────────┬────────────────────────┬────────────┘
         │                        │
         ▼                        ▼
    ┌─────────┐            ┌──────────┐
    │Frontend │            │ Backend  │
    │ Pods    │            │ Pods     │
    │ (3x)    │            │ (3x)     │
    └─────────┘            └──────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
              ┌─────────┐  ┌─────────┐  ┌─────────┐
              │ MongoDB │  │  Redis  │  │ Worker  │
              │StatefulSet│ │   Pod   │  │  Pods   │
              │  (3x)   │  └─────────┘  │  (5x)   │
              └─────────┘                └─────────┘
```

## Performance Considerations

### Database Indexes

```javascript
// Recommended indexes
db.migration_runs.createIndex({ project_id: 1, created_at: -1 })
db.events.createIndex({ run_id: 1, timestamp: -1 })
db.run_projects.createIndex({ run_id: 1, gitlab_project_id: 1 })
db.connections.createIndex({ project_id: 1, type: 1 })
```

### Caching Strategy

```
Redis layers:
1. User sessions (JWT cache)
2. Project metadata (TTL: 5 min)
3. Run status (TTL: 30 sec)
4. API rate limit counters
```

### Concurrency

```
Max concurrent:
- API workers: 4 per container
- Celery workers: 4 per container
- Projects per run: 5 (configurable)
```

## Monitoring & Observability

### Metrics to Track

- API request latency
- Celery task duration
- MongoDB query performance
- Redis hit rate
- Migration success rate
- Error rates per agent

### Logging

Structured JSON logs:
```json
{
  "timestamp": "2024-01-15T10:00:00Z",
  "level": "INFO",
  "name": "app.agents.discovery",
  "message": "Discovery started",
  "run_id": "507f1f77bcf86cd799439011",
  "project_id": "507f1f77bcf86cd799439012"
}
```

## Future Enhancements

1. **GitHub App Authentication** - Replace PATs
2. **Multi-tenancy** - Organization isolation
3. **LFS Migration** - Automated LFS transfer
4. **Advanced CI Conversion** - More GitLab features
5. **Rollback Support** - Undo GitHub changes
6. **Cost Estimation** - Predict migration effort
7. **Compliance Reports** - Audit trails
8. **Terraform Export** - IaC for GitHub config
