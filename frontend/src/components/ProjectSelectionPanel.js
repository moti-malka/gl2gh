/**
 * Project Selection Panel Component
 * Allows users to select discovered projects and configure target GitHub repo names
 */
import React, { useState, useEffect } from 'react';
import './ProjectSelectionPanel.css';

export const ProjectSelectionPanel = ({ runId, discoveredProjects, onContinue, onBack }) => {
  const [selections, setSelections] = useState({});
  const [targetNames, setTargetNames] = useState({});

  useEffect(() => {
    // Initialize selections and target names
    const initialSelections = {};
    const initialTargetNames = {};
    
    discoveredProjects.forEach(project => {
      initialSelections[project.id] = false; // Default to unselected
      
      // Generate default target name from path_with_namespace
      // e.g., "moti.malka25/demo-2" -> "moti-malka/demo-2"
      const pathParts = project.path_with_namespace.split('/');
      const defaultTarget = pathParts.length > 1 
        ? `${pathParts[0].replace(/\./g, '-')}/${pathParts[1]}`
        : project.path_with_namespace.replace(/\./g, '-');
      
      initialTargetNames[project.id] = defaultTarget;
    });
    
    setSelections(initialSelections);
    setTargetNames(initialTargetNames);
  }, [discoveredProjects]);

  const handleSelectionChange = (projectId) => {
    setSelections(prev => ({
      ...prev,
      [projectId]: !prev[projectId]
    }));
  };

  const handleTargetNameChange = (projectId, newName) => {
    setTargetNames(prev => ({
      ...prev,
      [projectId]: newName
    }));
  };

  const handleSelectAll = () => {
    const allSelected = {};
    discoveredProjects.forEach(project => {
      allSelected[project.id] = true;
    });
    setSelections(allSelected);
  };

  const handleDeselectAll = () => {
    const allDeselected = {};
    discoveredProjects.forEach(project => {
      allDeselected[project.id] = false;
    });
    setSelections(allDeselected);
  };

  const handleContinue = () => {
    // Build selection array to pass to parent
    const selectionArray = discoveredProjects.map(project => ({
      gitlab_project_id: project.id,
      path_with_namespace: project.path_with_namespace,
      target_repo_name: targetNames[project.id] || project.path_with_namespace,
      selected: selections[project.id] || false
    }));
    
    onContinue(selectionArray);
  };

  const selectedCount = Object.values(selections).filter(Boolean).length;

  return (
    <div className="project-selection-panel">
      <div className="panel-header">
        <h2>Discovery Results - Found {discoveredProjects.length} projects</h2>
        <p className="panel-subtitle">
          Select which projects to migrate and configure target GitHub repository names
        </p>
      </div>

      <div className="projects-list">
        {discoveredProjects.map(project => {
          const metrics = project.metrics || {};
          const selected = selections[project.id] || false;
          
          return (
            <div 
              key={project.id} 
              className={`project-card ${selected ? 'selected' : ''}`}
            >
              <div className="project-card-header">
                <label className="project-checkbox">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => handleSelectionChange(project.id)}
                  />
                  <span className="project-name">{project.path_with_namespace}</span>
                </label>
              </div>

              <div className="project-metrics">
                <span className="metric" title="Commits">
                  📝 {metrics.commits || 0} commits
                </span>
                <span className="metric" title="Issues">
                  🐛 {metrics.issues || 0} issues
                </span>
                <span className="metric" title="Merge Requests">
                  🔀 {metrics.merge_requests || 0} MR
                </span>
                <span className={`metric ci-status ${metrics.has_ci ? 'has-ci' : 'no-ci'}`}>
                  {metrics.has_ci ? '✅ Has CI' : '❌ No CI'}
                </span>
                <span className="metric score" title="Migration Readiness Score">
                  Score: {project.readiness_score || 0}
                </span>
              </div>

              {project.description && (
                <div className="project-description">
                  {project.description}
                </div>
              )}

              <div className="target-repo-config">
                <label className="target-label">
                  Target GitHub Repo:
                  <input
                    type="text"
                    className="target-input"
                    value={targetNames[project.id] || ''}
                    onChange={(e) => handleTargetNameChange(project.id, e.target.value)}
                    placeholder="owner/repo-name"
                    disabled={!selected}
                  />
                </label>
              </div>
            </div>
          );
        })}
      </div>

      <div className="panel-footer">
        <div className="selection-actions">
          <button onClick={handleSelectAll} className="btn btn-secondary">
            Select All
          </button>
          <button onClick={handleDeselectAll} className="btn btn-secondary">
            Deselect All
          </button>
          <span className="selection-count">
            Selected: {selectedCount} project{selectedCount !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="navigation-actions">
          {onBack && (
            <button onClick={onBack} className="btn btn-secondary">
              ← Back to Discovery
            </button>
          )}
          <button 
            onClick={handleContinue} 
            className="btn btn-primary"
            disabled={selectedCount === 0}
          >
            Continue to Export →
          </button>
        </div>
      </div>
    </div>
  );
};
