"""
Checkpoint manager for resumable exports with JSON state files.

Provides state persistence to allow exports to be resumed after interruption.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import CheckpointState, ComponentType

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoint state for resumable exports.
    
    Saves state to JSON files to allow resuming exports after interruption.
    Tracks completed components and partial progress within components.
    
    Usage:
        manager = CheckpointManager(output_dir)
        state = manager.load_checkpoint(project_id, run_id)
        if not state.is_component_completed(ComponentType.REPOSITORY):
            # Export repository
            state.mark_component_completed(ComponentType.REPOSITORY)
            manager.save_checkpoint(state)
    """
    
    CHECKPOINT_FILENAME = "checkpoint.json"
    
    def __init__(self, output_dir: Path):
        """
        Initialize checkpoint manager.
        
        Args:
            output_dir: Base output directory for exports
        """
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.CheckpointManager")
    
    def _get_checkpoint_path(self, project_id: int, run_id: str) -> Path:
        """Get path to checkpoint file for a project export."""
        project_dir = self.output_dir / str(project_id) / run_id
        return project_dir / self.CHECKPOINT_FILENAME
    
    def checkpoint_exists(self, project_id: int, run_id: str) -> bool:
        """
        Check if checkpoint exists for a project export.
        
        Args:
            project_id: GitLab project ID
            run_id: Export run ID
            
        Returns:
            True if checkpoint exists
        """
        return self._get_checkpoint_path(project_id, run_id).exists()
    
    def load_checkpoint(self, project_id: int, run_id: str) -> CheckpointState:
        """
        Load checkpoint state from file.
        
        Args:
            project_id: GitLab project ID
            run_id: Export run ID
            
        Returns:
            CheckpointState (new if no checkpoint exists)
        """
        checkpoint_path = self._get_checkpoint_path(project_id, run_id)
        
        if not checkpoint_path.exists():
            self.logger.info(f"No checkpoint found for project {project_id}, run {run_id}")
            return CheckpointState(project_id=project_id, run_id=run_id)
        
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            state = CheckpointState.from_dict(data)
            self.logger.info(
                f"Loaded checkpoint for project {project_id}: "
                f"{len(state.completed_components)} components completed"
            )
            return state
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            self.logger.warning("Starting fresh export")
            return CheckpointState(project_id=project_id, run_id=run_id)
    
    def save_checkpoint(self, state: CheckpointState) -> None:
        """
        Save checkpoint state to file.
        
        Args:
            state: Checkpoint state to save
        """
        checkpoint_path = self._get_checkpoint_path(state.project_id, state.run_id)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Update checkpoint timestamp
        state.last_checkpoint_at = datetime.now(timezone.utc)
        
        try:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.logger.debug(
                f"Saved checkpoint for project {state.project_id}: "
                f"{len(state.completed_components)} components completed"
            )
            
        except (OSError, TypeError) as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
    
    def delete_checkpoint(self, project_id: int, run_id: str) -> None:
        """
        Delete checkpoint file.
        
        Args:
            project_id: GitLab project ID
            run_id: Export run ID
        """
        checkpoint_path = self._get_checkpoint_path(project_id, run_id)
        
        if checkpoint_path.exists():
            try:
                checkpoint_path.unlink()
                self.logger.info(f"Deleted checkpoint for project {project_id}, run {run_id}")
            except OSError as e:
                self.logger.error(f"Failed to delete checkpoint: {e}")
    
    def is_component_completed(self, state: CheckpointState, component: ComponentType) -> bool:
        """
        Check if a component has been completed in this export.
        
        Args:
            state: Checkpoint state
            component: Component type to check
            
        Returns:
            True if component is completed
        """
        return component in state.completed_components
    
    def mark_component_completed(self, state: CheckpointState, component: ComponentType) -> None:
        """
        Mark a component as completed.
        
        Args:
            state: Checkpoint state
            component: Component type to mark as completed
        """
        if component not in state.completed_components:
            state.completed_components.append(component)
            self.logger.debug(f"Marked {component.value} as completed")
    
    def get_partial_state(self, state: CheckpointState, key: str) -> Any:
        """
        Get partial state for a component.
        
        Used to store intermediate progress within a component.
        
        Args:
            state: Checkpoint state
            key: State key
            
        Returns:
            Partial state value or None
        """
        return state.partial_state.get(key)
    
    def set_partial_state(self, state: CheckpointState, key: str, value: Any) -> None:
        """
        Set partial state for a component.
        
        Args:
            state: Checkpoint state
            key: State key
            value: State value
        """
        state.partial_state[key] = value
        self.logger.debug(f"Updated partial state: {key}")
    
    def clear_partial_state(self, state: CheckpointState, key: str) -> None:
        """
        Clear partial state for a component.
        
        Args:
            state: Checkpoint state
            key: State key to clear
        """
        if key in state.partial_state:
            del state.partial_state[key]
            self.logger.debug(f"Cleared partial state: {key}")
