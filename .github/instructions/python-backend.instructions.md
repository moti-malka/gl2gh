---
applyTo: "backend/**/*.py"
---
# Python Backend Instructions

## Code Style
- Use Python 3.11+ features (match statements, type unions with `|`, etc.)
- Always use async/await for I/O operations
- Type hints are required for all function parameters and return values
- Use Pydantic v2 models for data validation

## Import Order
1. Standard library
2. Third-party packages
3. Local imports (from app.*)

## Async Patterns
```python
# Correct - use async methods
async def get_data():
    result = await collection.find_one({"id": id})
    return result

# Wrong - blocking calls in async context
def get_data():
    result = collection.find_one({"id": id})  # Blocks!
```

## Error Handling
- Use HTTPException for API errors with appropriate status codes
- Log errors with context using the logging module
- Return meaningful error messages to clients

## Database Operations
- Use Motor's async methods: `find_one`, `insert_one`, `update_one`, `delete_one`
- Always handle the case where documents don't exist
- Use ObjectId for MongoDB `_id` fields

## Testing
- Tests go in `backend/tests/`
- Use fixtures from `conftest.py`
- Mock external services (GitLab/GitHub APIs)
- Name test files `test_<module>.py`
- Name test functions `test_<description>`

## Pydantic Models
```python
from pydantic import BaseModel, Field, field_validator

class MyModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    count: int = Field(default=0, ge=0)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()
```
