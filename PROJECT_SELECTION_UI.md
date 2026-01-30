# Project Selection UI - Implementation Documentation

## Overview
This implementation adds a UI for selecting discovered projects after the Discovery phase completes, allowing users to choose which projects to migrate and configure target GitHub repository names.

## Components Added

### Backend API Endpoints

#### 1. GET `/api/runs/{run_id}/discovery-results`
Fetches discovery results with enhanced project metrics.

**Response Structure:**
```json
{
  "version": "2.0",
  "generated_at": "2024-01-30T00:00:00Z",
  "projects_count": 4,
  "projects": [
    {
      "id": 12345,
      "name": "demo-2",
      "path_with_namespace": "moti.malka25/demo-2",
      "description": "Demo project",
      "web_url": "https://gitlab.com/...",
      "metrics": {
        "commits": 15,
        "issues": 3,
        "merge_requests": 1,
        "has_ci": true
      },
      "readiness_score": 85,
      "components": { ... }
    }
  ]
}
```

**Features:**
- Reads inventory.json from discovery artifacts
- Calculates migration readiness scores (0-100)
- Extracts key metrics (commits, issues, MRs, CI status)
- Returns enhanced project data for UI display

#### 2. POST `/api/runs/{run_id}/selection`
Saves user's project selection for migration.

**Request Body:**
```json
{
  "selections": [
    {
      "gitlab_project_id": 12345,
      "path_with_namespace": "moti.malka25/demo-2",
      "target_repo_name": "moti-malka/demo-2",
      "selected": true
    }
  ]
}
```

**Features:**
- Stores selections in run's config_snapshot
- Validates run access
- Returns count of selected projects

### Frontend Components

#### 1. ProjectSelectionPanel Component
Location: `frontend/src/components/ProjectSelectionPanel.js`

**Props:**
- `runId`: ID of the migration run
- `discoveredProjects`: Array of discovered projects
- `onContinue`: Callback when user clicks Continue
- `onBack`: Optional callback for Back button

**Features:**
- Checkbox selection for each project
- Editable target GitHub repository names
- Select All / Deselect All buttons
- Display project metrics with icons
- Migration readiness score visualization
- Disabled inputs for unselected projects
- Responsive design

#### 2. CSS Styling
Location: `frontend/src/components/ProjectSelectionPanel.css`

**Design Features:**
- Clean, modern card-based layout
- Selected state highlighting (blue border)
- Responsive grid for project metrics
- Hover effects and transitions
- Color-coded CI status indicators
- Mobile-responsive layout

### Integration with RunDashboardPage

**Modified:** `frontend/src/pages/RunDashboardPage.js`

**New State Variables:**
- `showProjectSelection`: Controls panel visibility
- `discoveredProjects`: Stores discovery results
- `loadingDiscovery`: Loading state indicator

**New Functions:**
- `loadDiscoveryResults()`: Fetches discovery data from API
- `handleProjectSelectionContinue()`: Saves selections and continues
- `handleProjectSelectionBack()`: Returns to discovery view

**Logic Flow:**
1. Run dashboard loads run data
2. Checks if discovery completed (`stage === 'EXPORT'` or status)
3. Verifies project selection hasn't been made yet
4. Loads discovery results via API
5. Shows ProjectSelectionPanel component
6. User makes selections and clicks Continue
7. Selections saved via API
8. Panel hidden, normal dashboard resumes

## User Workflow

### Expected User Journey:

1. **Discovery Completes**
   - Run enters EXPORT stage or completes with DISCOVER_ONLY mode
   - Dashboard detects completion

2. **Project Selection UI Appears**
   - Panel shows list of discovered projects
   - Each project displays:
     - Name and path
     - Metrics (commits, issues, MRs)
     - CI/CD status
     - Migration readiness score
     - Target repo name input

3. **User Selects Projects**
   - Check boxes next to desired projects
   - Edit target GitHub repo names as needed
   - Use Select All / Deselect All for bulk actions

4. **User Continues**
   - Click "Continue to Export →" button
   - Selections saved to database
   - Dashboard proceeds to next phase

## Technical Details

### Readiness Score Calculation
Simple heuristic algorithm (0-100 scale):
- Starts at 100 (highest readiness)
- -15 points if has CI/CD (requires conversion)
- -1 to -10 points based on open issues count
- -2 to -20 points based on open MR count
- Result clamped to 0-100 range

Higher scores indicate simpler/easier migrations.

### Target Repo Name Generation
Default pattern:
- Input: `user.name/project-name`
- Output: `user-name/project-name`
- Dots (.) replaced with hyphens (-)
- User can edit before saving

### Data Storage
Selection data stored in:
```
migration_runs.config_snapshot.project_selection
```

Structure:
```json
{
  "selected_projects": [...],
  "selected_at": "2024-01-30T00:00:00Z"
}
```

## Testing

### Manual Testing Steps:

1. Start a migration run with DISCOVER_ONLY or PLAN_ONLY mode
2. Wait for discovery to complete
3. Verify ProjectSelectionPanel appears
4. Test checkbox selection/deselection
5. Test Select All / Deselect All buttons
6. Edit target repo names
7. Click Continue
8. Verify selections saved (check browser DevTools Network tab)
9. Verify panel disappears after saving

### API Testing:

```bash
# Get discovery results
curl -X GET http://localhost:8000/api/runs/{run_id}/discovery-results \
  -H "Authorization: Bearer {token}"

# Save project selection
curl -X POST http://localhost:8000/api/runs/{run_id}/selection \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "selections": [
      {
        "gitlab_project_id": 12345,
        "path_with_namespace": "user/project",
        "target_repo_name": "user/project",
        "selected": true
      }
    ]
  }'
```

## Known Limitations

1. **No persistent selection state during session**: If user refreshes browser before clicking Continue, selections are lost
2. **No validation of target repo name format**: User can enter any string
3. **No duplicate target name checking**: Multiple projects could target same GitHub repo
4. **Simple readiness score**: Basic heuristic, not comprehensive analysis

## Future Enhancements

Potential improvements:
1. Auto-save selections as user makes changes
2. Validate GitHub repo name format (owner/name pattern)
3. Check for duplicate target repo names
4. More sophisticated readiness scoring
5. Project-level configuration (branch mapping, etc.)
6. Bulk actions (select by criteria, regex matching)
7. Import/export selection configuration
8. Project preview/details modal

## Files Modified/Created

### Backend
- `backend/app/api/runs.py`: Added 2 new endpoints and models

### Frontend
- `frontend/src/components/ProjectSelectionPanel.js`: New component (170 lines)
- `frontend/src/components/ProjectSelectionPanel.css`: New styles (240 lines)
- `frontend/src/pages/RunDashboardPage.js`: Integrated panel logic
- `frontend/src/services/api.js`: Added API client methods

## Acceptance Criteria Status

✅ Display discovered projects with metrics  
✅ Checkbox selection for projects  
✅ Editable target GitHub repo names  
✅ Select all / deselect all buttons  
✅ Continue button passes selection to next stage  
✅ Back button returns to discovery options  

All acceptance criteria met!
