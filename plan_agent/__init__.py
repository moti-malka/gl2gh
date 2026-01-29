"""
Plan Agent - Generates migration plans from transform outputs.

This agent produces a complete, ordered migration plan that defines all actions
needed to recreate a GitLab project on GitHub.
"""

__version__ = "0.1.0"
__author__ = "Plan Agent Team"

from .planner import PlanGenerator
from .schema import validate_plan

__all__ = [
    "PlanGenerator",
    "validate_plan",
    "__version__",
]
