---
applyTo: "backend/tests/**/*.py"
---
# Testing Instructions

## Test Structure
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

class TestMyFeature:
    """Tests for MyFeature functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, db, test_user):
        """Test that operation succeeds with valid input."""
        # Arrange
        service = MyService(db)
        input_data = {"name": "test"}
        
        # Act
        result = await service.create(input_data)
        
        # Assert
        assert result["name"] == "test"
        assert "_id" in result
    
    @pytest.mark.asyncio
    async def test_invalid_input_raises_error(self, db):
        """Test that invalid input raises appropriate error."""
        service = MyService(db)
        
        with pytest.raises(ValueError, match="Name required"):
            await service.create({})
```

## Available Fixtures (from conftest.py)
- `db` - Test MongoDB database (auto-cleaned)
- `user_service` - UserService instance
- `project_service` - ProjectService instance
- `connection_service` - ConnectionService instance
- `run_service` - RunService instance
- `event_service` - EventService instance
- `artifact_service` - ArtifactService instance
- `test_user` - Pre-created test user

## Mocking External APIs
```python
import responses

@responses.activate
def test_gitlab_api_call():
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects",
        json=[{"id": 1, "name": "test"}],
        status=200
    )
    
    result = gitlab_client.list_projects()
    assert len(result) == 1
```

## Mocking Async Functions
```python
@pytest.mark.asyncio
async def test_with_mocked_dependency():
    with patch("app.services.my_service.external_call") as mock:
        mock.return_value = AsyncMock(return_value={"data": "test"})
        
        result = await my_function()
        assert result["data"] == "test"
```

## Running Tests
```bash
# All tests
cd backend && python -m pytest

# Specific file
python -m pytest tests/test_my_feature.py

# With coverage
python -m pytest --cov=app tests/

# Verbose output
python -m pytest -v tests/
```

## Test Naming
- File: `test_<module>.py`
- Class: `TestFeatureName`
- Method: `test_<scenario>` or `test_<action>_<expected_result>`
