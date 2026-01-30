# Attachment Migration Feature

## Overview

The attachment migration feature ensures that images, files, and other attachments in GitLab issues and merge requests are preserved during migration to GitHub. Without this feature, attachment links would be broken after migration since they point to non-existent GitLab paths.

## How It Works

The attachment migration process consists of three main phases:

### 1. Export Phase - Download Attachments

During the export phase (`ExportAgent`), the system:

1. **Detects Attachments**: Scans issue/MR descriptions and comments for attachment patterns:
   - Image markdown: `![alt](/uploads/hash/file.png)`
   - File links: `[name](/uploads/hash/file.txt)`
   - Direct upload links: `/uploads/hash/file.pdf`

2. **Downloads Files**: For each detected attachment:
   - Constructs the full GitLab URL: `{gitlab_url}/{project_path}/uploads/hash/filename`
   - Downloads the file to local storage
   - Stores in organized directory structure:
     ```
     export/
       issues/
         attachments/
           hash_filename.ext
       merge_requests/
         attachments/
           hash_filename.ext
     ```

3. **Tracks Metadata**: Creates mapping files:
   - `issues/attachment_metadata.json` - Maps old paths to local files
   - `merge_requests/attachment_metadata.json` - Maps old paths to local files

### 2. Transform Phase - Rewrite Links

During the transformation phase (`ContentTransformer`), the system:

1. **Loads Attachment Mappings**: Reads attachment metadata from export
2. **Rewrites Content**: Replaces GitLab attachment paths with GitHub URLs
   - Old: `![bug](/uploads/abc123/screenshot.png)`
   - New: `![bug](https://github.com/owner/repo/blob/main/.github/attachments/issues/abc123_screenshot.png)`
3. **Handles Comments**: Also rewrites attachment links in issue/MR comments

### 3. Apply Phase - Upload to GitHub

During the apply phase (`CommitAttachmentsAction`), the system:

1. **Commits Files**: Uploads all attachments to the GitHub repository
   - Target directory: `.github/attachments/issues/` and `.github/attachments/merge_requests/`
   - Uses GitHub API to create/update files
2. **Preserves Structure**: Maintains organization by component type
3. **Generates URLs**: Creates proper GitHub blob URLs for each file

## Implementation Details

### Attachment Pattern Matching

The system uses regex patterns to detect GitLab attachments:

```python
ATTACHMENT_PATTERNS = [
    r'!\[.*?\]\((/uploads/[^)]+)\)',           # Images: ![alt](/uploads/...)
    r'\[.*?\]\((/uploads/[^)]+)\)',            # Files: [name](/uploads/...)
    r'(/uploads/[a-f0-9]+/[^\s)]+)',           # Direct upload links
]
```

### File Naming Convention

To prevent conflicts and maintain uniqueness:
- Original: `/uploads/abc123def/screenshot.png`
- Stored as: `abc123def_screenshot.png`
- This preserves the hash for uniqueness while keeping the original filename

### GitHub Storage Location

Attachments are stored in the repository at:
```
.github/attachments/
  issues/
    hash1_file1.png
    hash2_file2.pdf
  merge_requests/
    hash3_file3.jpg
    hash4_file4.log
```

## Usage

### Export with Attachments

When exporting a GitLab project, attachments are automatically detected and downloaded:

```python
from app.agents.export_agent import ExportAgent

agent = ExportAgent()
result = await agent.execute({
    "gitlab_url": "https://gitlab.com",
    "gitlab_token": "your-token",
    "project_id": "123",
    "output_dir": "./export"
})
```

After export, check:
- `export/issues/attachment_metadata.json` - Issue attachments
- `export/merge_requests/attachment_metadata.json` - MR attachments

### Transform with Link Rewriting

During transformation, set attachment mappings:

```python
from app.utils.transformers import ContentTransformer

transformer = ContentTransformer()

# Load attachment metadata from export
import json
with open("export/issues/attachment_metadata.json") as f:
    attachment_metadata = json.load(f)

# Create GitHub URL mappings
github_repo = "owner/repo"
attachment_mappings = {}
for old_path, local_path in attachment_metadata.items():
    filename = local_path.split("/")[-1]
    github_url = f"https://github.com/{github_repo}/blob/main/.github/attachments/issues/{filename}"
    attachment_mappings[old_path] = github_url

# Set mappings
transformer.set_attachment_mappings(attachment_mappings)

# Transform content
result = transformer.transform({
    "content_type": "issue",
    "content": issue_data,
    "gitlab_project": "gitlab-org/project",
    "github_repo": github_repo
})
```

### Apply - Commit Attachments

Add an attachment commit action to your migration plan:

```python
{
    "action_type": "attachments_commit",
    "component": "attachments",
    "phase": "issue_setup",
    "description": "Commit issue/MR attachments to repository",
    "parameters": {
        "target_repo": "owner/repo",
        "export_dir": "./export",
        "branch": "main",
        "target_path": ".github/attachments"
    }
}
```

## Error Handling

### Download Failures

If an attachment fails to download:
- A warning is logged with the attachment path
- The download returns `None`
- The migration continues with other attachments
- The original GitLab link remains in the content (broken link)

### Large Files

GitHub has file size limits:
- Maximum file size in repository: 100 MB
- Files larger than 50 MB generate warnings
- For very large files, consider external storage (S3, etc.)

### Missing Attachments

If an attachment was deleted in GitLab before export:
- The download will fail (404 error)
- A warning is logged
- The link remains unchanged (broken)

## Testing

Run attachment-related tests:

```bash
# Test attachment detection
pytest tests/test_export_agent.py::test_extract_attachments -v

# Test attachment downloading
pytest tests/test_export_agent.py::test_download_attachment -v

# Test link rewriting
pytest tests/transformers/test_content_transformer.py::TestContentTransformer::test_attachment_link_rewriting -v

# Test full issue export with attachments
pytest tests/test_export_agent.py::test_export_issues_with_attachments -v
```

## Configuration

### Customizing Attachment Storage

You can customize where attachments are stored in the GitHub repository by modifying the `target_path` parameter:

```python
{
    "target_path": ".github/attachments"  # Default
    # Or use a different location:
    "target_path": "docs/assets/migration"
}
```

### Binary vs Text Files

The system handles both binary and text files:
- Images (PNG, JPG, GIF, etc.)
- Documents (PDF, DOCX, etc.)
- Archives (ZIP, TAR, etc.)
- Text files (TXT, LOG, etc.)

All files are read in binary mode and uploaded via GitHub API.

## Limitations

1. **GitHub File Size Limits**: Files must be under 100 MB
2. **API Rate Limits**: Each file upload counts as one API call
3. **Private Repository Access**: Attachment URLs will require authentication for private repos
4. **No LFS Support**: Currently, attachments are not stored in Git LFS
5. **Sequential Upload**: Files are uploaded one at a time (not parallelized)

## Future Enhancements

Potential improvements for future versions:

1. **Git LFS Integration**: Store large files in LFS
2. **External Storage**: Support S3/Azure Blob for very large files
3. **Parallel Downloads/Uploads**: Speed up attachment migration
4. **Deduplication**: Detect and avoid uploading duplicate files
5. **Image Optimization**: Optionally compress images during migration
6. **Retry Logic**: Automatic retry for failed downloads/uploads
7. **Progress Reporting**: Real-time progress for attachment migration

## Troubleshooting

### Attachments Not Showing

If attachments don't display after migration:

1. **Check Paths**: Verify attachment metadata files were created
2. **Verify Upload**: Confirm files exist in `.github/attachments/` in GitHub repo
3. **Check URLs**: Ensure transformed content has correct GitHub URLs
4. **Private Repos**: For private repos, users need repo access to view attachments

### Download Errors

If attachments fail to download:

1. **Check GitLab Access**: Ensure token has read access to project
2. **Verify URLs**: Confirm the GitLab URLs are correct
3. **Check Permissions**: Ensure attachments weren't restricted
4. **Network Issues**: Check for network/firewall problems

### Upload Errors

If attachments fail to upload to GitHub:

1. **Check Token Permissions**: Ensure GitHub token has repo write access
2. **Verify File Sizes**: Check files are under 100 MB
3. **Check Branch**: Ensure target branch exists
4. **API Rate Limits**: May need to wait or use higher rate limit token

## Examples

### Example Issue with Attachments

**Original GitLab Issue:**
```markdown
# Bug Report

Here's a screenshot of the error:
![error screenshot](/uploads/abc123def/error.png)

And the log file:
[error.log](/uploads/def456abc/error.log)
```

**After Migration:**
```markdown
_Originally created as issue by @user on GitLab on 2024-01-15T10:00:00Z_
_Original URL: https://gitlab.com/project/issues/42_

# Bug Report

Here's a screenshot of the error:
![error screenshot](https://github.com/owner/repo/blob/main/.github/attachments/issues/abc123def_error.png)

And the log file:
[error.log](https://github.com/owner/repo/blob/main/.github/attachments/issues/def456abc_error.log)
```

## Related Documentation

- [Export Agent Documentation](./EXPORT_AGENT.md)
- [Content Transformer Documentation](./CONTENT_TRANSFORMER.md)
- [Apply Agent Documentation](./APPLY_AGENT.md)
- [Migration Guide](./MIGRATION_GUIDE.md)
