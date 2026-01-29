"""Configuration management for the Discovery Agent."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class DiscoveryConfig:
    """Configuration for the GitLab Discovery Agent."""

    # Required settings
    gitlab_base_url: str
    gitlab_token: str

    # Optional - if not provided, discovers ALL accessible groups
    root_group: Optional[str] = None

    # Optional - scan a single project by path (e.g., "group/project")
    project_path: Optional[str] = None

    # Optional settings with defaults
    output_dir: str = "./output"
    max_api_calls: int = 5000
    max_per_project_calls: int = 200
    timeout: int = 30
    verify_ssl: bool = True
    log_level: str = "INFO"
    
    # Deep analysis settings
    deep: bool = False  # Enable deep analysis with migration scoring
    deep_top_n: int = 20  # Limit deep analysis to top N projects (0 = all)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.gitlab_base_url:
            raise ValueError("gitlab_base_url is required")
        if not self.gitlab_token:
            raise ValueError("gitlab_token is required")

        # Normalize base URL (remove trailing slash)
        self.gitlab_base_url = self.gitlab_base_url.rstrip("/")

        # Ensure output directory path is valid
        self.output_dir = os.path.expanduser(self.output_dir)

        # Normalize empty string to None for root_group and project_path
        if self.root_group == "":
            self.root_group = None
        if self.project_path == "":
            self.project_path = None

    @property
    def single_project_mode(self) -> bool:
        """Return True if we should scan a single project only."""
        return self.project_path is not None

    @property
    def discover_all(self) -> bool:
        """Return True if we should discover all accessible groups."""
        return self.root_group is None and self.project_path is None

    @classmethod
    def from_env(cls, **overrides) -> "DiscoveryConfig":
        """Create configuration from environment variables with optional overrides."""
        load_dotenv()

        config_dict = {
            "gitlab_base_url": os.getenv("GITLAB_BASE_URL", ""),
            "gitlab_token": os.getenv("GITLAB_TOKEN", ""),
            "root_group": os.getenv("GITLAB_ROOT_GROUP") or None,
            "project_path": os.getenv("GITLAB_PROJECT") or None,
            "output_dir": os.getenv("OUTPUT_DIR", "./output"),
            "max_api_calls": int(os.getenv("MAX_API_CALLS", "5000")),
            "max_per_project_calls": int(os.getenv("MAX_PER_PROJECT_CALLS", "200")),
            "timeout": int(os.getenv("TIMEOUT", "30")),
            "verify_ssl": os.getenv("VERIFY_SSL", "true").lower() == "true",
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "deep": os.getenv("DEEP", "false").lower() == "true",
            "deep_top_n": int(os.getenv("DEEP_TOP_N", "20")),
        }

        # Apply overrides (filter out None values from CLI)
        for key, value in overrides.items():
            if value is not None:
                config_dict[key] = value

        return cls(**config_dict)


def ensure_output_dir(config: DiscoveryConfig) -> Path:
    """
    Ensure the output directory exists and return it as a Path.
    
    Args:
        config: Discovery configuration
        
    Returns:
        Path object for the output directory
    """
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path
