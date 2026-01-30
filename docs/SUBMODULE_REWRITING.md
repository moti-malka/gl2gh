# Submodule URL Rewriting

This document explains how the submodule URL rewriting feature works in the GitLab to GitHub migration tool.

## Overview

When migrating repositories from GitLab to GitHub, git submodules pointing to GitLab URLs need to be rewritten to point to GitHub. This feature automatically detects, transforms, and updates submodule URLs during migration.

## How It Works

### 1. Export Phase
During the export phase, the `export_agent.py` detects if a repository has submodules by reading the `.gitmodules` file:

```python
# Export submodule info if present
result = subprocess.run(
    ['git', 'config', '--file', '.gitmodules', '--list'],
    cwd=temp_dir,
    capture_output=True,
    text=True,
    timeout=10
)
if result.returncode == 0 and result.stdout:
    submodules_path = repo_dir / "submodules.txt"
    with open(submodules_path, 'w') as f:
        f.write(result.stdout)
```

### 2. Transform Phase
During the transform phase, the `SubmoduleTransformer` processes the submodule information:

1. **Parses** the `.gitmodules` file content
2. **Identifies** which submodules are being migrated (based on URL mappings)
3. **Rewrites** URLs for migrated repositories (GitLab → GitHub)
4. **Preserves** the original URL format (SSH vs HTTPS)
5. **Flags** external submodules (not being migrated) with warnings
6. **Generates** an updated `.gitmodules` file

Example usage in `transform_agent.py`:

```python
submodules_result = await self._transform_submodules(
    export_data.get("submodules_content"),
    gitlab_project,
    github_repo,
    output_dir
)
```

### 3. Apply Phase
During the apply phase, the `UpdateGitmodulesAction` updates the `.gitmodules` file in the GitHub repository:

```python
class UpdateGitmodulesAction(BaseAction):
    async def execute(self) -> ActionResult:
        target_repo = self.parameters["target_repo"]
        gitmodules_content = self.parameters["gitmodules_content"]
        
        repo = self.github_client.get_repo(target_repo)
        
        # Update or create .gitmodules file
        ...
```

## Supported URL Formats

The transformer handles multiple Git URL formats:

### HTTPS URLs
- **Input**: `https://gitlab.com/myorg/common-lib.git`
- **Output**: `https://github.com/myorg/common-lib.git`

### SSH URLs
- **Input**: `git@gitlab.com:myorg/tool.git`
- **Output**: `git@github.com:myorg/tool.git`

### Relative URLs
Relative URLs (e.g., `../other-repo.git`) are currently **not** automatically rewritten and will generate warnings.

## Example

### Original `.gitmodules`
```ini
[submodule "libs/common"]
    path = libs/common
    url = https://gitlab.com/myorg/common-lib.git

[submodule "vendor/tool"]
    path = vendor/tool
    url = git@gitlab.com:myorg/tool.git

[submodule "external/dependency"]
    path = external/dependency
    url = https://gitlab.com/external/some-lib.git
```

### After Transformation
```ini
[submodule "libs/common"]
    path = libs/common
    url = https://github.com/myorg/common-lib.git

[submodule "vendor/tool"]
    path = vendor/tool
    url = git@github.com:myorg/tool.git

[submodule "external/dependency"]
    path = external/dependency
    url = https://gitlab.com/external/some-lib.git  # Not rewritten - external repo
```

### Warnings Generated
```
⚠ Submodule 'external/dependency' URL not rewritten - repository not being migrated
```

## Features

### ✅ Implemented
- [x] Parse `.gitmodules` file
- [x] Identify which submodules are being migrated
- [x] Rewrite URLs for migrated repos
- [x] Flag non-migrated submodules as warnings
- [x] Update `.gitmodules` in GitHub repo
- [x] Handle SSH/HTTPS URLs
- [x] Preserve URL format (SSH stays SSH, HTTPS stays HTTPS)
- [x] Preserve additional submodule properties (branch, update method, etc.)

### ⚠️ Edge Cases
- **Relative URLs**: Currently not automatically rewritten
- **Nested Submodules**: Parent submodule must be cloned first
- **External Submodules**: Flagged with warnings but not rewritten

## Testing

Comprehensive unit tests are available in:
```
backend/tests/transformers/test_submodule_transformer.py
```

Run tests with:
```bash
cd /home/runner/work/gl2gh/gl2gh
PYTHONPATH=/home/runner/work/gl2gh/gl2gh/backend:$PYTHONPATH \
python -m pytest backend/tests/transformers/test_submodule_transformer.py -v
```

## Architecture

### Components

1. **SubmoduleTransformer** (`backend/app/utils/transformers/submodule_transformer.py`)
   - Core transformation logic
   - URL parsing and rewriting
   - Format preservation

2. **Transform Agent** (`backend/app/agents/transform_agent.py`)
   - Orchestrates submodule transformation
   - Integrates with migration workflow
   - Generates transformation artifacts

3. **UpdateGitmodulesAction** (`backend/app/agents/actions/repository.py`)
   - Updates `.gitmodules` file in GitHub
   - Handles file creation/update scenarios

## Output Files

The transformation generates the following artifacts in the output directory:

1. **submodules_transformed.json**: Complete transformation metadata
   ```json
   {
     "submodules": [...],
     "rewrite_count": 2,
     "external_count": 1,
     "total_count": 3
   }
   ```

2. **gitmodules_updated.txt**: Updated `.gitmodules` file content ready for GitHub

## Future Enhancements

Potential improvements for future versions:

- [ ] Support for relative submodule URLs
- [ ] Automatic detection of nested submodule dependencies
- [ ] Batch rewriting for multiple repositories
- [ ] Integration with GitHub CLI for local testing
- [ ] Support for submodule branch tracking
