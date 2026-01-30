/**
 * ComponentSelector - UI for selecting which components to migrate
 */
import React, { useState, useEffect } from 'react';
import './ComponentSelector.css';

export const ComponentSelector = ({ inventory, initialSelection, onSelectionChange }) => {
  const [selection, setSelection] = useState(initialSelection || getDefaultSelection());

  useEffect(() => {
    if (initialSelection) {
      setSelection(initialSelection);
    }
  }, [initialSelection]);

  function getDefaultSelection() {
    return {
      repository: { enabled: true, lfs: false, submodules: false },
      ci_cd: { enabled: true, workflows: true, variables: true, environments: true, schedules: true },
      issues: { enabled: true, open: true, closed: false, labels: true, milestones: true },
      merge_requests: { enabled: false, open: false, merged: false },
      wiki: { enabled: true },
      releases: { enabled: true, notes: true, assets: false },
      packages: { enabled: false },
      settings: { enabled: false, protected_branches: false, webhooks: false, members: false }
    };
  }

  const handleComponentToggle = (component) => {
    const newSelection = {
      ...selection,
      [component]: {
        ...selection[component],
        enabled: !selection[component].enabled
      }
    };
    setSelection(newSelection);
    onSelectionChange(newSelection);
  };

  const handleSubToggle = (component, subComponent) => {
    const newSelection = {
      ...selection,
      [component]: {
        ...selection[component],
        [subComponent]: !selection[component][subComponent]
      }
    };
    setSelection(newSelection);
    onSelectionChange(newSelection);
  };

  const handlePreset = (preset) => {
    let newSelection;
    
    if (preset === 'full') {
      newSelection = {
        repository: { enabled: true, lfs: true, submodules: true },
        ci_cd: { enabled: true, workflows: true, variables: true, environments: true, schedules: true },
        issues: { enabled: true, open: true, closed: true, labels: true, milestones: true },
        merge_requests: { enabled: true, open: true, merged: true },
        wiki: { enabled: true },
        releases: { enabled: true, notes: true, assets: true },
        packages: { enabled: true },
        settings: { enabled: true, protected_branches: true, webhooks: true, members: true }
      };
    } else if (preset === 'code-only') {
      newSelection = {
        repository: { enabled: true, lfs: false, submodules: false },
        ci_cd: { enabled: false, workflows: false, variables: false, environments: false, schedules: false },
        issues: { enabled: false, open: false, closed: false, labels: false, milestones: false },
        merge_requests: { enabled: false, open: false, merged: false },
        wiki: { enabled: false },
        releases: { enabled: false, notes: false, assets: false },
        packages: { enabled: false },
        settings: { enabled: false, protected_branches: false, webhooks: false, members: false }
      };
    } else if (preset === 'code-issues') {
      newSelection = {
        repository: { enabled: true, lfs: false, submodules: false },
        ci_cd: { enabled: true, workflows: true, variables: true, environments: true, schedules: false },
        issues: { enabled: true, open: true, closed: false, labels: true, milestones: true },
        merge_requests: { enabled: false, open: false, merged: false },
        wiki: { enabled: true },
        releases: { enabled: true, notes: true, assets: false },
        packages: { enabled: false },
        settings: { enabled: false, protected_branches: false, webhooks: false, members: false }
      };
    }
    
    setSelection(newSelection);
    onSelectionChange(newSelection);
  };

  const isComponentAvailable = (component) => {
    if (!inventory) return true;
    
    const componentData = inventory[component];
    if (!componentData) return false;
    
    // Check if component has data
    if (component === 'repository') return true; // Always available
    if (component === 'ci_cd') return componentData.projects_with_ci > 0;
    if (component === 'issues') return (componentData.total_open + componentData.total_closed) > 0;
    if (component === 'merge_requests') return (componentData.total_open + componentData.total_merged + componentData.total_closed) > 0;
    if (component === 'wiki') return componentData.projects_with_wiki > 0;
    if (component === 'releases') return componentData.total_releases > 0;
    if (component === 'packages') return false; // Not supported yet
    if (component === 'settings') return true; // Always available
    
    return true;
  };

  return (
    <div className="component-selector">
      <div className="selector-header">
        <h2>🎯 Select Components to Migrate</h2>
        <p className="selector-subtitle">Choose which components you want to include in the migration</p>
        
        <div className="selector-presets">
          <button className="preset-btn" onClick={() => handlePreset('full')}>
            Full Migration
          </button>
          <button className="preset-btn" onClick={() => handlePreset('code-issues')}>
            Code + Issues
          </button>
          <button className="preset-btn" onClick={() => handlePreset('code-only')}>
            Code Only
          </button>
        </div>
      </div>

      <div className="selector-grid">
        {/* Repository */}
        <div className={`selector-card ${isComponentAvailable('repository') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.repository.enabled}
              onChange={() => handleComponentToggle('repository')}
              disabled={!isComponentAvailable('repository')}
            />
            <span className="selector-icon">📁</span>
            <h3>Repository</h3>
          </div>
          {selection.repository.enabled && (
            <div className="selector-card-body">
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.repository.lfs}
                  onChange={() => handleSubToggle('repository', 'lfs')}
                />
                <span>Include LFS objects</span>
                {inventory?.repository?.has_lfs && <span className="option-badge warning">Large files</span>}
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.repository.submodules}
                  onChange={() => handleSubToggle('repository', 'submodules')}
                />
                <span>Include submodules</span>
              </label>
            </div>
          )}
        </div>

        {/* CI/CD */}
        <div className={`selector-card ${isComponentAvailable('ci_cd') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.ci_cd.enabled}
              onChange={() => handleComponentToggle('ci_cd')}
              disabled={!isComponentAvailable('ci_cd')}
            />
            <span className="selector-icon">⚙️</span>
            <h3>CI/CD</h3>
          </div>
          {selection.ci_cd.enabled && (
            <div className="selector-card-body">
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.ci_cd.workflows}
                  onChange={() => handleSubToggle('ci_cd', 'workflows')}
                />
                <span>Convert workflows</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.ci_cd.variables}
                  onChange={() => handleSubToggle('ci_cd', 'variables')}
                />
                <span>Migrate variables</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.ci_cd.environments}
                  onChange={() => handleSubToggle('ci_cd', 'environments')}
                />
                <span>Create environments</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.ci_cd.schedules}
                  onChange={() => handleSubToggle('ci_cd', 'schedules')}
                />
                <span>Migrate schedules</span>
              </label>
            </div>
          )}
        </div>

        {/* Issues */}
        <div className={`selector-card ${isComponentAvailable('issues') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.issues.enabled}
              onChange={() => handleComponentToggle('issues')}
              disabled={!isComponentAvailable('issues')}
            />
            <span className="selector-icon">📋</span>
            <h3>Issues</h3>
            {inventory?.issues && (
              <span className="component-count">
                {inventory.issues.total_open + inventory.issues.total_closed}
              </span>
            )}
          </div>
          {selection.issues.enabled && (
            <div className="selector-card-body">
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.issues.open}
                  onChange={() => handleSubToggle('issues', 'open')}
                />
                <span>Open issues ({inventory?.issues?.total_open || 0})</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.issues.closed}
                  onChange={() => handleSubToggle('issues', 'closed')}
                />
                <span>Closed issues ({inventory?.issues?.total_closed || 0})</span>
                {inventory?.issues?.total_closed > 100 && <span className="option-badge warning">Large set</span>}
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.issues.labels}
                  onChange={() => handleSubToggle('issues', 'labels')}
                />
                <span>Labels</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.issues.milestones}
                  onChange={() => handleSubToggle('issues', 'milestones')}
                />
                <span>Milestones</span>
              </label>
            </div>
          )}
        </div>

        {/* Merge Requests */}
        <div className={`selector-card ${isComponentAvailable('merge_requests') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.merge_requests.enabled}
              onChange={() => handleComponentToggle('merge_requests')}
              disabled={!isComponentAvailable('merge_requests')}
            />
            <span className="selector-icon">🔀</span>
            <h3>Merge Requests</h3>
            {inventory?.merge_requests && (
              <span className="component-count">
                {inventory.merge_requests.total_open + inventory.merge_requests.total_merged + inventory.merge_requests.total_closed}
              </span>
            )}
          </div>
          {selection.merge_requests.enabled && (
            <div className="selector-card-body">
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.merge_requests.open}
                  onChange={() => handleSubToggle('merge_requests', 'open')}
                />
                <span>Open MRs ({inventory?.merge_requests?.total_open || 0})</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.merge_requests.merged}
                  onChange={() => handleSubToggle('merge_requests', 'merged')}
                />
                <span>Merged MRs ({inventory?.merge_requests?.total_merged || 0})</span>
                {inventory?.merge_requests?.total_merged > 50 && <span className="option-badge warning">Large set</span>}
              </label>
            </div>
          )}
        </div>

        {/* Wiki */}
        <div className={`selector-card ${isComponentAvailable('wiki') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.wiki.enabled}
              onChange={() => handleComponentToggle('wiki')}
              disabled={!isComponentAvailable('wiki')}
            />
            <span className="selector-icon">📖</span>
            <h3>Wiki</h3>
            {inventory?.wiki && inventory.wiki.total_pages > 0 && (
              <span className="component-count">{inventory.wiki.total_pages} pages</span>
            )}
          </div>
        </div>

        {/* Releases */}
        <div className={`selector-card ${isComponentAvailable('releases') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.releases.enabled}
              onChange={() => handleComponentToggle('releases')}
              disabled={!isComponentAvailable('releases')}
            />
            <span className="selector-icon">🏷️</span>
            <h3>Releases</h3>
            {inventory?.releases && (
              <span className="component-count">{inventory.releases.total_releases}</span>
            )}
          </div>
          {selection.releases.enabled && (
            <div className="selector-card-body">
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.releases.notes}
                  onChange={() => handleSubToggle('releases', 'notes')}
                />
                <span>Release notes</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.releases.assets}
                  onChange={() => handleSubToggle('releases', 'assets')}
                />
                <span>Release assets</span>
                <span className="option-badge warning">May be large</span>
              </label>
            </div>
          )}
        </div>

        {/* Settings */}
        <div className={`selector-card ${isComponentAvailable('settings') ? '' : 'disabled'}`}>
          <div className="selector-card-header">
            <input
              type="checkbox"
              checked={selection.settings.enabled}
              onChange={() => handleComponentToggle('settings')}
              disabled={!isComponentAvailable('settings')}
            />
            <span className="selector-icon">⚙️</span>
            <h3>Settings</h3>
          </div>
          {selection.settings.enabled && (
            <div className="selector-card-body">
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.settings.protected_branches}
                  onChange={() => handleSubToggle('settings', 'protected_branches')}
                />
                <span>Protected branches</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.settings.webhooks}
                  onChange={() => handleSubToggle('settings', 'webhooks')}
                />
                <span>Webhooks</span>
              </label>
              <label className="sub-option">
                <input
                  type="checkbox"
                  checked={selection.settings.members}
                  onChange={() => handleSubToggle('settings', 'members')}
                />
                <span>Team members</span>
              </label>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
