"""Database models for MongoDB collections"""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class MongoBaseModel(BaseModel):
    """Base model for MongoDB documents"""
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


# User Models
class User(MongoBaseModel):
    """User model"""
    email: str
    username: str
    hashed_password: str
    full_name: Optional[str] = None
    role: str = "operator"  # admin, operator, viewer
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Migration Project Models
class ProjectSettings(BaseModel):
    """Project settings nested model"""
    gitlab: Dict[str, Any] = Field(default_factory=dict)
    github: Dict[str, Any] = Field(default_factory=dict)
    budgets: Dict[str, int] = Field(default_factory=lambda: {
        "max_api_calls": 5000,
        "max_per_project_calls": 200
    })
    behavior: Dict[str, Any] = Field(default_factory=lambda: {
        "default_run_mode": "PLAN_ONLY",
        "rename_default_branch_to": None,
        "include_archived": False
    })


class MigrationProject(MongoBaseModel):
    """Migration project model"""
    name: str
    description: Optional[str] = None
    created_by: PyObjectId
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    status: str = "active"  # active, archived


# Connection Models
class Connection(MongoBaseModel):
    """Connection (credential) model"""
    project_id: PyObjectId
    type: str  # "gitlab" or "github"
    base_url: Optional[str] = None
    token_encrypted: str
    token_last4: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Migration Run Models
class RunStats(BaseModel):
    """Run statistics nested model"""
    groups: int = 0
    projects: int = 0
    errors: int = 0
    api_calls: int = 0


class MigrationRun(MongoBaseModel):
    """Migration run model"""
    project_id: PyObjectId
    mode: str  # FULL, PLAN_ONLY, DISCOVER_ONLY, EXPORT_ONLY, APPLY, VERIFY
    status: str = "CREATED"  # CREATED, QUEUED, RUNNING, COMPLETED, FAILED, CANCELED
    stage: Optional[str] = None  # DISCOVER, EXPORT, TRANSFORM, PLAN, APPLY, VERIFY
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stats: RunStats = Field(default_factory=RunStats)
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)
    artifact_root: Optional[str] = None
    error: Optional[Dict[str, str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Run Project Models
class StageStatus(BaseModel):
    """Stage status for a project in a run"""
    discover: str = "PENDING"
    export: str = "PENDING"
    transform: str = "PENDING"
    plan: str = "PENDING"
    apply: str = "PENDING"
    verify: str = "PENDING"


class RunProject(MongoBaseModel):
    """Individual project within a migration run"""
    run_id: PyObjectId
    gitlab_project_id: int
    path_with_namespace: str
    bucket: Optional[str] = None  # S, M, L, XL
    facts: Dict[str, Any] = Field(default_factory=dict)
    readiness: Dict[str, Any] = Field(default_factory=dict)
    stage_status: StageStatus = Field(default_factory=StageStatus)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Event Models
class Event(MongoBaseModel):
    """Event log model"""
    run_id: PyObjectId
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str  # INFO, WARN, ERROR, DEBUG
    agent: Optional[str] = None  # DiscoveryAgent, ExportAgent, etc.
    scope: str = "run"  # "run" or "project"
    gitlab_project_id: Optional[int] = None
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)


# Artifact Models
class Artifact(MongoBaseModel):
    """Artifact metadata model"""
    run_id: PyObjectId
    project_id: Optional[PyObjectId] = None
    gitlab_project_id: Optional[int] = None
    type: str  # inventory, plan, apply_report, verify_report, workflow, etc.
    path: str  # Relative path from artifact_root
    size_bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
