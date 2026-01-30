# User Mapping Enhancement

## Overview

This enhancement improves the GitLab to GitHub user mapping functionality with fuzzy matching, project-level persistence, and RESTful API endpoints for manual user mapping management.

## Features

### 1. Fuzzy Matching

The `UserMapper` now includes intelligent fuzzy matching for both usernames and full names:

- **Username Fuzzy Matching**: Matches similar usernames like "john.doe" to "johndoe" with a similarity threshold of 0.75
- **Name Fuzzy Matching**: Matches similar names like "John-Michael Doe" to "John Michael Doe" with a similarity threshold of 0.85
- **Normalization**: Automatically normalizes usernames and names by removing punctuation and converting to lowercase

#### Matching Priority

1. **Email Match** (High Confidence) - Exact email match
2. **Username Match** (Medium Confidence) - Exact or fuzzy username match
3. **Name Match** (Low Confidence) - Exact or fuzzy name match
4. **Unmapped** - No match found

### 2. Enhanced Data Model

The `UserMapping` model now supports:

- `project_id`: Optional project-level mapping for reusing mappings across runs
- `match_method`: Tracks the matching method (email, username, name, fuzzy_username, fuzzy_name, manual)
- `confidence`: Numerical confidence score (0.0 to 1.0)
- `is_manual`: Flag indicating manual vs automatic mapping

### 3. RESTful API Endpoints

New API endpoints for managing user mappings:

#### List Mappings
```
GET /api/runs/{run_id}/user-mappings
```
Lists all user mappings for a specific run with pagination support.

#### Get Specific Mapping
```
GET /api/runs/{run_id}/user-mappings/{gitlab_username}
```
Retrieves a specific user mapping by GitLab username.

#### Create/Update Manual Mapping
```
POST /api/runs/{run_id}/user-mappings
{
  "gitlab_username": "john.doe",
  "gitlab_email": "john@example.com",
  "github_username": "johndoe",
  "confidence": 1.0,
  "match_method": "manual",
  "project_id": "optional_project_id"
}
```
Creates or updates a manual user mapping.

#### Update Mapping
```
PUT /api/runs/{run_id}/user-mappings/{mapping_id}
{
  "github_username": "new_username",
  "confidence": 1.0
}
```
Updates an existing user mapping.

#### Get Unmapped Users
```
GET /api/runs/{run_id}/user-mappings/unmapped
```
Lists all GitLab users that couldn't be mapped to GitHub users.

#### Get Mapping Statistics
```
GET /api/runs/{run_id}/user-mappings/stats
```
Returns statistics about user mappings:
```json
{
  "total": 100,
  "mapped": 85,
  "unmapped": 15,
  "coverage_percent": 85.0
}
```

### 4. Service Layer Enhancements

The `UserMappingService` now includes:

- Support for project-level mappings
- New `get_project_mappings()` method to retrieve all mappings for a project
- Enhanced `store_mapping()` with support for match_method and project_id
- Proper indexing for efficient queries

## Usage Examples

### Python API (UserMapper)

```python
from app.utils.transformers import UserMapper

mapper = UserMapper()

result = mapper.transform({
    "gitlab_users": [
        {
            "id": 1,
            "username": "john.doe",
            "email": "john@example.com",
            "name": "John Doe"
        }
    ],
    "github_users": [
        {
            "login": "johndoe",
            "id": 101,
            "email": "john@example.com",
            "name": "John Doe"
        }
    ]
})

# Access mappings
mappings = result.data["mappings"]
stats = result.data["stats"]
unmapped = result.data["unmapped_users"]
```

### REST API (cURL Examples)

```bash
# Create a manual mapping
curl -X POST http://localhost:8000/api/runs/{run_id}/user-mappings \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "gitlab_username": "olduser",
    "github_username": "newuser",
    "confidence": 1.0,
    "match_method": "manual"
  }'

# Get mapping statistics
curl -X GET http://localhost:8000/api/runs/{run_id}/user-mappings/stats \
  -H "Authorization: Bearer {token}"

# List unmapped users
curl -X GET http://localhost:8000/api/runs/{run_id}/user-mappings/unmapped \
  -H "Authorization: Bearer {token}"
```

## Testing

### Unit Tests

Run the user mapper tests:
```bash
cd backend
pytest tests/transformers/test_user_mapper.py -v
```

Test coverage includes:
- Email-based matching
- Username matching (exact and fuzzy)
- Name matching (exact and fuzzy)
- Case-insensitive matching
- Normalization helpers
- Similarity calculations
- Unmapped user handling
- Multiple user mapping scenarios

### Integration Tests

API endpoints are integrated with the FastAPI application and use JWT authentication. Tests require:
- Running MongoDB instance
- Valid authentication tokens
- Proper environment configuration

## Configuration

No additional configuration is required. The fuzzy matching thresholds are:
- Username fuzzy match: 0.75 (75% similarity)
- Name fuzzy match: 0.85 (85% similarity)

These thresholds can be adjusted in `user_mapper.py` if needed.

## Database Schema

### UserMapping Collection

```javascript
{
  _id: ObjectId,
  project_id: ObjectId (optional),
  run_id: ObjectId,
  gitlab_username: String,
  gitlab_email: String (optional),
  github_username: String (optional),
  confidence: Float (0.0 to 1.0),
  match_method: String (email|username|name|fuzzy_username|fuzzy_name|manual),
  is_manual: Boolean,
  created_at: DateTime,
  updated_at: DateTime
}
```

### Indexes

- Unique index on `(run_id, gitlab_username)`
- Index on `run_id`
- Index on `project_id`

## Implementation Files

- `backend/app/utils/transformers/user_mapper.py` - Core mapping logic with fuzzy matching
- `backend/app/models/__init__.py` - UserMapping data model
- `backend/app/services/user_mapping_service.py` - Database service layer
- `backend/app/api/user_mappings.py` - REST API endpoints
- `backend/tests/transformers/test_user_mapper.py` - Unit tests

## Future Enhancements

Potential improvements for future iterations:

1. **ML-based Matching**: Use machine learning to improve confidence scoring
2. **Bulk Import**: API endpoint for bulk manual mapping imports
3. **Mapping Export**: Export mappings to CSV/JSON for reuse
4. **Confidence Tuning**: Allow per-project configuration of similarity thresholds
5. **Name Aliases**: Support for known username aliases
6. **Historical Learning**: Learn from previous manual corrections
