"""CI/CD-related actions"""

from typing import Any, Dict
from pathlib import Path
import base64
from .base import BaseAction, ActionResult
import httpx


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
            
            # Try to get existing file
            try:
                existing_content = await self.github_client.get_file_content(
                    repo=target_repo,
                    path=target_path,
                    ref=branch
                )
                if existing_content:
                    # Get SHA for update
                    owner, repo = target_repo.split("/")
                    response = await self.github_client._request(
                        'GET',
                        f"/repos/{target_repo}/contents/{target_path}",
                        params={"ref": branch}
                    )
                    file_data = response.json()
                    sha = file_data["sha"]
                    
                    # Update existing file
                    await self.github_client.create_or_update_file(
                        repo=target_repo,
                        path=target_path,
                        content=content,
                        message=commit_message,
                        branch=branch,
                        sha=sha
                    )
                    action = "updated"
                else:
                    raise FileNotFoundError()
            except (FileNotFoundError, httpx.HTTPStatusError) as e:
                # Create new file
                await self.github_client.create_or_update_file(
                    repo=target_repo,
                    path=target_path,
                    content=content,
                    message=commit_message,
                    branch=branch
                )
                action = "created"
            
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
            
            # Create environment using GitHubClient
            await self.github_client.create_environment(
                repo=target_repo,
                environment_name=environment_name
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "environment_name": environment_name,
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


class SetSecretAction(BaseAction):
    """Set repository or environment secret"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            secret_name = self.parameters["name"]
            secret_value = self.parameters.get("value")
            scope = self.parameters.get("scope", "repository")
            environment_name = self.parameters.get("environment")
            
            if not secret_value:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={},
                    error=f"Secret value not provided for {secret_name}. User input required."
                )
            
            # Get repository public key
            public_key = await self.github_client.get_public_key(target_repo)
            
            # Encrypt secret value (requires PyNaCl)
            try:
                from nacl import encoding, public
                
                public_key_obj = public.PublicKey(
                    public_key["key"].encode("utf-8"),
                    encoding.Base64Encoder()
                )
                sealed_box = public.SealedBox(public_key_obj)
                encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
                encrypted_value = base64.b64encode(encrypted).decode("utf-8")
                
                # Create or update secret
                if scope == "environment" and environment_name:
                    success = await self.github_client.create_environment_secret(
                        repo=target_repo,
                        environment_name=environment_name,
                        secret_name=secret_name,
                        encrypted_value=encrypted_value
                    )
                else:
                    success = await self.github_client.create_or_update_secret(
                        repo=target_repo,
                        secret_name=secret_name,
                        encrypted_value=encrypted_value,
                        key_id=public_key["key_id"]
                    )
                
                if not success:
                    raise Exception("Failed to create secret")
                
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
            
            # NOTE: Variables API requires REST API calls not fully supported by PyGithub
            # This is a placeholder that logs the intent
            self.logger.warning(f"Variable setting not fully implemented - manual setup required for: {variable_name}")
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "variable_name": variable_name,
                    "scope": scope,
                    "target_repo": target_repo,
                    "note": "Variable needs manual creation via REST API or GitHub UI"
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
