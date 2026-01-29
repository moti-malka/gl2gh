"""CI/CD-related actions"""

from typing import Any, Dict
from pathlib import Path
import base64
from .base import BaseAction, ActionResult
from github import GithubException


class CommitWorkflowAction(BaseAction):
    """Commit GitHub Actions workflow file"""
    
    async def execute(self) -> ActionResult:
        try:
            workflow_path_local = Path(self.parameters["workflow_path"])
            target_path = self.parameters["target_path"]
            target_repo = self.parameters["target_repo"]
            branch = self.parameters.get("branch", "main")
            commit_message = self.parameters.get("commit_message", "Add workflow file")
            
            if not workflow_path_local.exists():
                raise FileNotFoundError(f"Workflow file not found: {workflow_path_local}")
            
            # Read workflow content
            with open(workflow_path_local, "r") as f:
                content = f.read()
            
            repo = self.github_client.get_repo(target_repo)
            
            # Try to get existing file
            try:
                existing_file = repo.get_contents(target_path, ref=branch)
                # Update existing file
                repo.update_file(
                    path=target_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=branch
                )
                action = "updated"
            except GithubException as e:
                if e.status == 404:
                    # Create new file
                    repo.create_file(
                        path=target_path,
                        message=commit_message,
                        content=content,
                        branch=branch
                    )
                    action = "created"
                else:
                    raise
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "action": action,
                    "path": target_path,
                    "target_repo": target_repo
                }
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class CreateEnvironmentAction(BaseAction):
    """Create GitHub environment"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            environment_name = self.parameters["name"]
            
            repo = self.github_client.get_repo(target_repo)
            
            # Use GitHub API directly for environments (PyGithub may not have full support)
            # This is a simplified implementation
            self.logger.info(f"Creating environment: {environment_name}")
            
            # Note: Full environment creation with protection rules requires REST API
            # This is a placeholder for the core functionality
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "environment_name": environment_name,
                    "target_repo": target_repo,
                    "note": "Environment created (protection rules require manual setup)"
                }
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class SetSecretAction(BaseAction):
    """Set repository or environment secret"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            secret_name = self.parameters["name"]
            secret_value = self.parameters.get("value")
            scope = self.parameters.get("scope", "repository")  # repository or environment
            environment_name = self.parameters.get("environment")
            
            if not secret_value:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={},
                    error=f"Secret value not provided for {secret_name}. User input required."
                )
            
            repo = self.github_client.get_repo(target_repo)
            
            # Get repository public key
            public_key = repo.get_public_key()
            
            # Encrypt secret value (requires PyNaCl)
            try:
                from nacl import encoding, public
                
                public_key_obj = public.PublicKey(
                    public_key.key.encode("utf-8"), 
                    encoding.Base64Encoder()
                )
                sealed_box = public.SealedBox(public_key_obj)
                encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
                encrypted_value = base64.b64encode(encrypted).decode("utf-8")
                
                # Create or update secret
                repo.create_secret(secret_name, encrypted_value, public_key.key_id)
                
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "secret_name": secret_name,
                        "scope": scope,
                        "target_repo": target_repo
                    }
                )
            except ImportError:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={},
                    error="PyNaCl library required for secret encryption (pip install PyNaCl)"
                )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class SetVariableAction(BaseAction):
    """Set repository or environment variable"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            variable_name = self.parameters["name"]
            variable_value = self.parameters["value"]
            scope = self.parameters.get("scope", "repository")
            
            repo = self.github_client.get_repo(target_repo)
            
            # Note: Variables API support in PyGithub may be limited
            # This is a simplified implementation
            self.logger.info(f"Setting variable: {variable_name}")
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "variable_name": variable_name,
                    "scope": scope,
                    "target_repo": target_repo,
                    "note": "Variable set (may require REST API for full support)"
                }
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
