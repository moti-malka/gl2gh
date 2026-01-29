"""
Migration Agents using Microsoft Agent Framework

This package implements specialized agents for GitLab to GitHub migration
using Microsoft Agent Framework (MAF) patterns and principles:

- BaseAgent: Abstract base with MAF patterns (context, tools, retry)
- DiscoveryAgent: Scan and analyze GitLab projects
- ExportAgent: Export GitLab data
- TransformAgent: Convert GitLab → GitHub formats
- PlanAgent: Generate executable migration plans
- ApplyAgent: Execute plans on GitHub
- VerifyAgent: Validate migration results
- AgentOrchestrator: Coordinate multi-agent workflows

Each agent follows MAF principles:
- Clear input/output contracts
- Deterministic behavior
- Context awareness
- Tool integration
- Error handling with retries
- Progress tracking
"""

from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.export_agent import ExportAgent
from app.agents.transform_agent import TransformAgent
from app.agents.plan_agent import PlanAgent
from app.agents.apply_agent import ApplyAgent
from app.agents.verify_agent import VerifyAgent
from app.agents.orchestrator import AgentOrchestrator, MigrationMode

__all__ = [
    # Base classes
    'BaseAgent',
    'AgentResult',
    
    # Specialized agents
    'DiscoveryAgent',
    'ExportAgent',
    'TransformAgent',
    'PlanAgent',
    'ApplyAgent',
    'VerifyAgent',
    
    # Orchestration
    'AgentOrchestrator',
    'MigrationMode',
]
