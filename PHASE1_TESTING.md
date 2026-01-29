# Phase 1 Implementation - Testing Guide

## Overview

Phase 1 implements the complete database services layer and authentication system for the gl2gh migration platform.

## What Was Implemented

### 1. Database Services (7 Services)

All services include comprehensive error handling, logging, and async operations:

- **UserService**: User management with password hashing
- **ProjectService**: Migration project CRUD operations
- **ConnectionService**: Secure storage of GitLab/GitHub tokens with encryption
- **RunService**: Migration run lifecycle management
- **EventService**: Event logging and retrieval with filtering
- **UserMappingService**: GitLab to GitHub user mapping
- **ArtifactService**: Migration artifact metadata storage

### 2. Authentication System

- **JWT Token Generation**: Access and refresh tokens
- **Password Hashing**: bcrypt for secure password storage
- **Token Encryption**: Fernet encryption for GitLab/GitHub PATs
- **Role-Based Access Control**: Admin, Operator, and Viewer roles
- **FastAPI Dependencies**: Reusable auth middleware

### 3. API Endpoints

All endpoints now connected to services with proper authentication:

- `/api/auth/*` - Login, logout, register, token refresh, get current user
- `/api/projects/*` - Project CRUD with role-based access
- `/api/projects/{id}/connections/*` - Secure credential storage
- `/api/projects/{id}/runs/*` - Run management
- `/api/runs/{id}/events` - Event retrieval with filtering
- `/api/runs/{id}/artifacts` - Artifact listing

### 4. Test Suite

Comprehensive tests covering:
- All 7 services (unit tests)
- Authentication flow
- API integration tests
- Access control verification

## Setup Instructions

### 1. Prerequisites

```bash
# Ensure you have:
- Docker and Docker Compose
- Python 3.11+
- MongoDB running (via Docker)
- Redis running (via Docker)
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set:
# - SECRET_KEY (for JWT tokens)
# - APP_MASTER_KEY (for encrypting GitLab/GitHub tokens)

# For testing, you can use:
SECRET_KEY=test-secret-key-minimum-32-characters-long
APP_MASTER_KEY=test-master-key-for-encryption-also-32-chars
```

### 3. Start Services

```bash
# Start MongoDB and Redis
docker-compose up -d mongo redis

# Wait for services to be healthy
docker-compose ps

# Install Python dependencies (if running locally)
cd backend
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
# Create indexes for all collections
cd backend
python scripts/init_db.py

# Create default admin user
python scripts/init_admin.py

# Default credentials (CHANGE IN PRODUCTION):
# Email: admin@gl2gh.local
# Password: admin123
```

### 5. Run Tests

```bash
# Set test environment
export MONGO_URL=mongodb://localhost:27017
export MONGO_DB_NAME=gl2gh_test
export APP_MASTER_KEY=test-master-key-for-encryption-32bytes
export SECRET_KEY=test-secret-key-for-jwt

# Run all tests
cd backend
pytest -v

# Run specific test file
pytest tests/test_user_service.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### 6. Start Application

```bash
# Option A: Using Docker Compose (recommended)
docker-compose up -d backend worker

# Option B: Run locally
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Verify Installation

```bash
# Check health
curl http://localhost:8000/health

# Register a user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpass123"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'

# Use the returned access_token for authenticated requests
export TOKEN="<access_token_from_login>"

# Get current user
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Create a project
curl -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Migration Project",
    "description": "Test project"
  }'
```

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Security Notes

### Token Encryption

GitLab and GitHub personal access tokens are encrypted using Fernet encryption with the `APP_MASTER_KEY`. The key is derived using SHA-256 hashing.

### Password Storage

User passwords are hashed using bcrypt with automatic salt generation.

### JWT Tokens

- **Access tokens**: Expire after 30 minutes (configurable)
- **Refresh tokens**: Expire after 7 days
- Tokens include user ID and role for authorization

### Sensitive Data Masking

All logging automatically masks:
- GitLab tokens (glpat-*)
- GitHub tokens (ghp_*, github_pat_*)
- Bearer tokens

## Database Collections

The following MongoDB collections are created:

1. **users** - User accounts
2. **projects** - Migration projects
3. **connections** - Encrypted credentials
4. **runs** - Migration runs
5. **events** - Run event logs
6. **artifacts** - Artifact metadata
7. **user_mappings** - GitLab to GitHub user mappings

## Troubleshooting

### Cannot connect to MongoDB

```bash
# Check if MongoDB is running
docker-compose ps mongo

# Check logs
docker-compose logs mongo

# Restart MongoDB
docker-compose restart mongo
```

### Tests failing with connection errors

```bash
# Ensure test database name is different
export MONGO_DB_NAME=gl2gh_test

# Clean test database
mongosh gl2gh_test --eval "db.dropDatabase()"
```

### Authentication not working

```bash
# Verify environment variables are set
echo $SECRET_KEY
echo $APP_MASTER_KEY

# Ensure keys are at least 32 characters
# Recreate tokens after changing keys
```

## Next Steps

With Phase 1 complete, you can now:

1. **Use the API** to create projects and manage migrations
2. **Integrate with agents** - Services are ready for agent integration
3. **Build the frontend** - All backend APIs are functional
4. **Add Celery tasks** - Run service supports async task management
5. **Implement remaining agents** - Discovery, Export, Transform, etc.

## Success Criteria ✅

All Phase 1 requirements met:

- ✅ All 7 services implemented with error handling
- ✅ Authentication working (JWT, login, middleware)
- ✅ API endpoints connected to services
- ✅ Role-based access control implemented
- ✅ Services properly exported from __init__.py
- ✅ Comprehensive test suite created
- ✅ Database indexes configured
- ✅ Admin initialization script
- ✅ Documentation complete

## Architecture Notes

### Service Layer Pattern

All services inherit from `BaseService` which provides:
- Database connection management
- Logging setup
- Consistent error handling

### Async/Await Throughout

All database operations use Motor (async MongoDB driver) for non-blocking I/O.

### Pydantic Models

MongoDB documents use Pydantic models for validation and serialization.

### API Response Models

Separate response models ensure clean API contracts without exposing internal fields.

## Performance Considerations

- **Indexes**: All frequently queried fields are indexed
- **Pagination**: All list endpoints support skip/limit
- **Connection pooling**: Motor handles connection pooling automatically
- **Async operations**: Non-blocking I/O for high concurrency

## Security Best Practices

1. **Never log sensitive data** - Automatic masking in place
2. **Use environment variables** - No secrets in code
3. **Validate all inputs** - Pydantic validation on all requests
4. **Use parameterized queries** - Motor prevents injection attacks
5. **Rotate keys regularly** - Change SECRET_KEY and APP_MASTER_KEY periodically
6. **HTTPS in production** - Always use TLS for API communication
