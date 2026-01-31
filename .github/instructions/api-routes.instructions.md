---
applyTo: "backend/app/api/**/*.py"
---
# FastAPI Route Instructions

## Route Structure
```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.db import get_db
from app.api.auth import get_current_user
from app.models import CreateRequest, Response
from app.services import MyService

router = APIRouter(prefix="/myresource", tags=["My Resource"])

@router.post("/", response_model=Response, status_code=status.HTTP_201_CREATED)
async def create_resource(
    data: CreateRequest,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new resource.
    
    - **data**: Resource creation data
    - Returns the created resource
    """
    service = MyService(db)
    return await service.create(data, current_user["_id"])
```

## HTTP Status Codes
- `200` - Success (GET, PUT, PATCH)
- `201` - Created (POST)
- `204` - No Content (DELETE)
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `422` - Unprocessable Entity (Pydantic validation)
- `500` - Internal Server Error

## Error Handling
```python
from fastapi import HTTPException, status

# Not found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Resource not found"
)

# Permission denied
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions"
)
```

## Authentication
- Use `get_current_user` dependency for authenticated routes
- Use `get_current_admin` for admin-only routes
- Token is passed in `Authorization: Bearer <token>` header

## Pagination
```python
@router.get("/", response_model=PaginatedResponse)
async def list_resources(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_db)
):
    service = MyService(db)
    items = await service.list(skip=skip, limit=limit)
    total = await service.count()
    return {"items": items, "total": total, "skip": skip, "limit": limit}
```

## Registering Routes
After creating a new router, register it in `app/main.py`:
```python
from app.api.myresource import router as myresource_router
app.include_router(myresource_router, prefix="/api")
```
