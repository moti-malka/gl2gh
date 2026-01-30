"""Action executors for Apply Agent"""

from .base import BaseAction, ActionResult
from .repository import (
    CreateRepositoryAction,
    PushCodeAction,
    PushLFSAction,
    ConfigureRepositoryAction,
    UpdateGitmodulesAction
)
from .ci_cd import (
    CommitWorkflowAction,
    CreateEnvironmentAction,
    SetSecretAction,
    SetVariableAction
)
from .issues import (
    CreateLabelAction,
    CreateMilestoneAction,
    CreateIssueAction,
    AddIssueCommentAction
)
from .pull_requests import (
    CreatePullRequestAction,
    AddPRCommentAction
)
from .wiki import PushWikiAction
from .releases import (
    CreateReleaseAction,
    UploadReleaseAssetAction
)
from .packages import PublishPackageAction
from .settings import (
    SetBranchProtectionAction,
    AddCollaboratorAction,
    CreateWebhookAction
)
from .preservation import CommitPreservationArtifactsAction

__all__ = [
    "BaseAction",
    "ActionResult",
    "CreateRepositoryAction",
    "PushCodeAction",
    "PushLFSAction",
    "ConfigureRepositoryAction",
    "UpdateGitmodulesAction",
    "CommitWorkflowAction",
    "CreateEnvironmentAction",
    "SetSecretAction",
    "SetVariableAction",
    "CreateLabelAction",
    "CreateMilestoneAction",
    "CreateIssueAction",
    "AddIssueCommentAction",
    "CreatePullRequestAction",
    "AddPRCommentAction",
    "PushWikiAction",
    "CreateReleaseAction",
    "UploadReleaseAssetAction",
    "PublishPackageAction",
    "SetBranchProtectionAction",
    "AddCollaboratorAction",
    "CreateWebhookAction",
    "CommitPreservationArtifactsAction",
    "ACTION_REGISTRY",
]

# Action type registry - maps action type strings to action classes
ACTION_REGISTRY = {
    "repo_create": CreateRepositoryAction,
    "repo_push": PushCodeAction,
    "lfs_configure": PushLFSAction,
    "repo_configure": ConfigureRepositoryAction,
    "gitmodules_update": UpdateGitmodulesAction,
    "workflow_commit": CommitWorkflowAction,
    "environment_create": CreateEnvironmentAction,
    "secret_set": SetSecretAction,
    "variable_set": SetVariableAction,
    "label_create": CreateLabelAction,
    "milestone_create": CreateMilestoneAction,
    "issue_create": CreateIssueAction,
    "issue_comment_add": AddIssueCommentAction,
    "pr_create": CreatePullRequestAction,
    "pr_comment_add": AddPRCommentAction,
    "wiki_push": PushWikiAction,
    "release_create": CreateReleaseAction,
    "release_asset_upload": UploadReleaseAssetAction,
    "package_publish": PublishPackageAction,
    "protection_set": SetBranchProtectionAction,
    "collaborator_add": AddCollaboratorAction,
    "webhook_create": CreateWebhookAction,
    "artifact_commit": CommitPreservationArtifactsAction,
}
