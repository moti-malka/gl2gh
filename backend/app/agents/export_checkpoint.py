"""Export checkpointing for resume capability"""

from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ExportCheckpoint:
    """
    Manages export checkpoints for resume capability.
    
    Checkpoints track:
    - Component completion status
    - Last processed item per component
    - Error history
    - Progress metrics
    """
    
    def __init__(self, checkpoint_file: Path):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_file: Path to checkpoint file
        """
        self.checkpoint_file = checkpoint_file
        self.checkpoint_data = {
            "version": "1.0",
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": None,
            "components": {},
            "errors": [],
            "metadata": {}
        }
        self._load()
    
    def _load(self):
        """Load checkpoint from file if it exists"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    self.checkpoint_data = json.load(f)
                logger.info(f"Loaded checkpoint from {self.checkpoint_file}")
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}, starting fresh")
    
    def _save(self):
        """Save checkpoint to file"""
        try:
            self.checkpoint_data["updated_at"] = datetime.utcnow().isoformat()
            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write atomically
            temp_file = self.checkpoint_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.checkpoint_data, f, indent=2)
            
            temp_file.replace(self.checkpoint_file)
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def mark_component_started(self, component: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Mark component as started.
        
        Args:
            component: Component name (e.g., 'repository', 'issues')
            metadata: Optional component metadata
        """
        if component not in self.checkpoint_data["components"]:
            self.checkpoint_data["components"][component] = {
                "status": "in_progress",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "last_item": None,
                "total_items": 0,
                "processed_items": 0,
                "errors": [],
                "metadata": metadata or {}
            }
        else:
            # Resume existing component
            self.checkpoint_data["components"][component]["status"] = "in_progress"
        
        self._save()
    
    def update_component_progress(
        self,
        component: str,
        processed_items: int,
        total_items: Optional[int] = None,
        last_item: Optional[Any] = None
    ):
        """
        Update component progress.
        
        Args:
            component: Component name
            processed_items: Number of items processed
            total_items: Total items (if known)
            last_item: Last processed item identifier
        """
        if component in self.checkpoint_data["components"]:
            comp_data = self.checkpoint_data["components"][component]
            comp_data["processed_items"] = processed_items
            if total_items is not None:
                comp_data["total_items"] = total_items
            if last_item is not None:
                comp_data["last_item"] = last_item
            
            self._save()
    
    def mark_component_completed(self, component: str, success: bool = True, error: Optional[str] = None):
        """
        Mark component as completed.
        
        Args:
            component: Component name
            success: Whether component completed successfully
            error: Optional error message
        """
        if component in self.checkpoint_data["components"]:
            comp_data = self.checkpoint_data["components"][component]
            comp_data["status"] = "completed" if success else "failed"
            comp_data["completed_at"] = datetime.utcnow().isoformat()
            
            if error:
                comp_data["errors"].append({
                    "message": error,
                    "timestamp": datetime.utcnow().isoformat()
                })
                self.checkpoint_data["errors"].append({
                    "component": component,
                    "message": error,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            self._save()
    
    def is_component_completed(self, component: str) -> bool:
        """Check if component is already completed"""
        if component in self.checkpoint_data["components"]:
            return self.checkpoint_data["components"][component]["status"] == "completed"
        return False
    
    def get_component_status(self, component: str) -> Optional[Dict[str, Any]]:
        """Get component checkpoint data"""
        return self.checkpoint_data["components"].get(component)
    
    def get_last_processed_item(self, component: str) -> Optional[Any]:
        """Get last processed item for component"""
        if component in self.checkpoint_data["components"]:
            return self.checkpoint_data["components"][component].get("last_item")
        return None
    
    def should_resume_component(self, component: str) -> bool:
        """Check if component should be resumed"""
        if component in self.checkpoint_data["components"]:
            status = self.checkpoint_data["components"][component]["status"]
            return status == "in_progress"
        return False
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get overall progress summary"""
        total_components = len(self.checkpoint_data["components"])
        completed = sum(
            1 for c in self.checkpoint_data["components"].values()
            if c["status"] == "completed"
        )
        failed = sum(
            1 for c in self.checkpoint_data["components"].values()
            if c["status"] == "failed"
        )
        in_progress = sum(
            1 for c in self.checkpoint_data["components"].values()
            if c["status"] == "in_progress"
        )
        
        return {
            "total_components": total_components,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "total_errors": len(self.checkpoint_data["errors"]),
            "started_at": self.checkpoint_data["started_at"],
            "updated_at": self.checkpoint_data["updated_at"]
        }
    
    def clear(self):
        """Clear checkpoint data and file"""
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
            self.checkpoint_data = {
                "version": "1.0",
                "started_at": datetime.utcnow().isoformat(),
                "updated_at": None,
                "components": {},
                "errors": [],
                "metadata": {}
            }
        except Exception as e:
            logger.error(f"Failed to clear checkpoint: {e}")
    
    def set_metadata(self, key: str, value: Any):
        """Set checkpoint metadata"""
        self.checkpoint_data["metadata"][key] = value
        self._save()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get checkpoint metadata"""
        return self.checkpoint_data["metadata"].get(key, default)
