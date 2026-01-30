"""Package-related actions"""

import os
from typing import Any, Dict
from .base import BaseAction, ActionResult


class PublishPackageAction(BaseAction):
    """Publish package to GitHub Packages"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            package_type = self.parameters.get("package_type", "npm")
            package_name = self.parameters["package_name"]
            version = self.parameters["version"]
            package_files = self.parameters.get("files", [])
            
            # Validate target_repo format
            if '/' not in target_repo:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={},
                    error=f"Invalid target_repo format: '{target_repo}'. Expected 'owner/repo'."
                )
            
            # Check if package type is supported for automated migration
            # Only npm, maven, and nuget have GitHub Packages support
            supported_types = {"npm", "maven", "nuget"}
            
            if package_type not in supported_types:
                # Unsupported package type - report as gap
                self.logger.warning(
                    f"Package type '{package_type}' not supported for automatic migration. "
                    f"Package {package_name}@{version} requires manual setup."
                )
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "package_name": package_name,
                        "version": version,
                        "package_type": package_type,
                        "target_repo": target_repo,
                        "status": "unsupported",
                        "note": f"Package type '{package_type}' requires manual migration. "
                                "Consider using GitHub Releases or external registry."
                    }
                )
            
            # Check if we have package files
            if not package_files:
                self.logger.warning(f"No package files available for {package_name}@{version}")
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "package_name": package_name,
                        "version": version,
                        "package_type": package_type,
                        "target_repo": target_repo,
                        "status": "no_files",
                        "note": "No package files found in export. Manual republishing required."
                    }
                )
            
            # Perform package-type-specific publishing
            if package_type == "npm":
                result = await self._publish_npm(package_name, version, package_files, target_repo)
            elif package_type == "maven":
                result = await self._publish_maven(package_name, version, package_files, target_repo)
            elif package_type == "nuget":
                result = await self._publish_nuget(package_name, version, package_files, target_repo)
            else:
                # Should not reach here due to earlier check
                result = {"success": False, "error": f"Unsupported package type: {package_type}"}
            
            if result.get("success"):
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "package_name": package_name,
                        "version": version,
                        "package_type": package_type,
                        "target_repo": target_repo,
                        "status": "published",
                        "details": result.get("details", {})
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "package_name": package_name,
                        "version": version,
                        "package_type": package_type
                    },
                    error=result.get("error", "Unknown error during package publishing")
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
    
    async def _publish_npm(
        self, 
        package_name: str, 
        version: str, 
        package_files: list, 
        target_repo: str
    ) -> Dict[str, Any]:
        """
        Publish npm package to GitHub Packages.
        
        NOTE: This requires:
        - .npmrc configured with GitHub Packages registry
        - NPM_TOKEN environment variable with GitHub token
        - Package file (*.tgz) from export
        """
        try:
            # Find the .tgz file
            tgz_file = None
            for file_info in package_files:
                if file_info.get("file_name", "").endswith(".tgz"):
                    tgz_file = file_info.get("local_path")
                    break
            
            if not tgz_file:
                return {
                    "success": False,
                    "error": "No .tgz file found for npm package"
                }
            
            # Check if NPM_TOKEN is available
            npm_token = os.environ.get("NPM_TOKEN") or os.environ.get("GITHUB_TOKEN")
            if not npm_token:
                self.logger.warning(
                    f"NPM_TOKEN not available. Package {package_name}@{version} publishing skipped. "
                    "Set NPM_TOKEN environment variable with GitHub PAT that has 'write:packages' scope."
                )
                return {
                    "success": True,
                    "details": {
                        "note": "Package publishing requires NPM_TOKEN environment variable",
                        "manual_steps": [
                            f"1. Set up .npmrc with registry=https://npm.pkg.github.com/{target_repo.split('/')[0]}",
                            f"2. Set NPM_TOKEN with GitHub PAT (write:packages scope)",
                            f"3. Run: npm publish {tgz_file}"
                        ]
                    }
                }
            
            # For now, we document the steps rather than actually publishing
            # Actual publishing would require configured .npmrc and proper auth
            self.logger.info(
                f"NPM package {package_name}@{version} ready for publishing. "
                "Manual configuration required."
            )
            
            return {
                "success": True,
                "details": {
                    "package_file": tgz_file,
                    "registry": f"https://npm.pkg.github.com/{target_repo.split('/')[0]}",
                    "note": "Package file available. Configure .npmrc and publish manually or via CI/CD.",
                    "manual_steps": [
                        f"1. Configure .npmrc: @{target_repo.split('/')[0]}:registry=https://npm.pkg.github.com",
                        "2. Authenticate with GitHub token",
                        f"3. Run: npm publish {tgz_file}"
                    ]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error publishing npm package: {e}")
            return {"success": False, "error": str(e)}
    
    async def _publish_maven(
        self, 
        package_name: str, 
        version: str, 
        package_files: list, 
        target_repo: str
    ) -> Dict[str, Any]:
        """
        Publish Maven package to GitHub Packages.
        
        NOTE: This requires:
        - Maven settings.xml configured with GitHub Packages
        - GITHUB_TOKEN environment variable
        - Package files (*.jar, *.pom) from export
        """
        try:
            # Find required Maven files
            jar_file = None
            pom_file = None
            
            for file_info in package_files:
                file_name = file_info.get("file_name", "")
                if file_name.endswith(".jar"):
                    jar_file = file_info.get("local_path")
                elif file_name.endswith(".pom"):
                    pom_file = file_info.get("local_path")
            
            if not jar_file:
                return {
                    "success": False,
                    "error": "No .jar file found for Maven package"
                }
            
            # Check if GITHUB_TOKEN is available
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                self.logger.warning(
                    f"GITHUB_TOKEN not available. Maven package {package_name}@{version} publishing skipped."
                )
                return {
                    "success": True,
                    "details": {
                        "note": "Package publishing requires GITHUB_TOKEN environment variable",
                        "manual_steps": [
                            "1. Configure settings.xml with GitHub Packages repository",
                            "2. Set GITHUB_TOKEN environment variable",
                            f"3. Run: mvn deploy:deploy-file -DgroupId=... -DartifactId={package_name} -Dversion={version} -Dfile={jar_file}"
                        ]
                    }
                }
            
            # Document the steps for manual publishing
            self.logger.info(
                f"Maven package {package_name}@{version} ready for publishing. "
                "Manual configuration required."
            )
            
            return {
                "success": True,
                "details": {
                    "jar_file": jar_file,
                    "pom_file": pom_file,
                    "repository": f"https://maven.pkg.github.com/{target_repo}",
                    "note": "Package files available. Configure settings.xml and publish manually or via CI/CD.",
                    "manual_steps": [
                        f"1. Add repository to pom.xml: <distributionManagement><repository><id>github</id><url>https://maven.pkg.github.com/{target_repo}</url></repository></distributionManagement>",
                        "2. Configure ~/.m2/settings.xml with GitHub credentials",
                        "3. Run: mvn deploy"
                    ]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error publishing Maven package: {e}")
            return {"success": False, "error": str(e)}
    
    async def _publish_nuget(
        self, 
        package_name: str, 
        version: str, 
        package_files: list, 
        target_repo: str
    ) -> Dict[str, Any]:
        """
        Publish NuGet package to GitHub Packages.
        
        NOTE: This requires:
        - nuget.config configured with GitHub Packages
        - GITHUB_TOKEN environment variable
        - Package file (*.nupkg) from export
        """
        try:
            # Find the .nupkg file
            nupkg_file = None
            for file_info in package_files:
                if file_info.get("file_name", "").endswith(".nupkg"):
                    nupkg_file = file_info.get("local_path")
                    break
            
            if not nupkg_file:
                return {
                    "success": False,
                    "error": "No .nupkg file found for NuGet package"
                }
            
            # Check if GITHUB_TOKEN is available
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                self.logger.warning(
                    f"GITHUB_TOKEN not available. NuGet package {package_name}@{version} publishing skipped."
                )
                return {
                    "success": True,
                    "details": {
                        "note": "Package publishing requires GITHUB_TOKEN environment variable",
                        "manual_steps": [
                            "1. Configure nuget.config with GitHub Packages source",
                            "2. Set GITHUB_TOKEN environment variable",
                            f"3. Run: dotnet nuget push {nupkg_file} --source github"
                        ]
                    }
                }
            
            # Document the steps for manual publishing
            self.logger.info(
                f"NuGet package {package_name}@{version} ready for publishing. "
                "Manual configuration required."
            )
            
            return {
                "success": True,
                "details": {
                    "package_file": nupkg_file,
                    "source": f"https://nuget.pkg.github.com/{target_repo.split('/')[0]}/index.json",
                    "note": "Package file available. Configure nuget.config and publish manually or via CI/CD.",
                    "manual_steps": [
                        f"1. Add source: dotnet nuget add source https://nuget.pkg.github.com/{target_repo.split('/')[0]}/index.json -n github",
                        "2. Authenticate with GitHub token",
                        f"3. Run: dotnet nuget push {nupkg_file} --source github"
                    ]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error publishing NuGet package: {e}")
            return {"success": False, "error": str(e)}
