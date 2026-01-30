/**
 * GitLab Scope Picker Component
 * 
 * Allows users to browse their GitLab account and select a group or project
 * for migration scope.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { connectionsAPI } from '../services/api';
import { Loading } from './Loading';
import './GitLabScopePicker.css';

export const GitLabScopePicker = ({ projectId, onScopeSelected, currentScope }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [items, setItems] = useState([]);
  const [currentPath, setCurrentPath] = useState(null);
  const [parentPath, setParentPath] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([{ name: 'Root', path: null }]);
  const [selectedItem, setSelectedItem] = useState(null);

  const loadItems = useCallback(async (path = null) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await connectionsAPI.browseGitLab(projectId, path, true);
      
      if (response.data.success) {
        setItems(response.data.items || []);
        setCurrentPath(response.data.current_path);
        setParentPath(response.data.parent_path);
        
        // Update breadcrumbs
        if (path === null) {
          setBreadcrumbs([{ name: 'Root', path: null }]);
        } else {
          const parts = path.split('/');
          const newBreadcrumbs = [{ name: 'Root', path: null }];
          let accPath = '';
          for (const part of parts) {
            accPath = accPath ? `${accPath}/${part}` : part;
            newBreadcrumbs.push({ name: part, path: accPath });
          }
          setBreadcrumbs(newBreadcrumbs);
        }
      } else {
        setError(response.data.error || 'Failed to load items');
      }
    } catch (err) {
      console.error('Error loading GitLab items:', err);
      setError(err.response?.data?.detail || 'Failed to connect to GitLab');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadItems(null);
  }, [loadItems]);

  const handleItemClick = (item) => {
    if (item.type === 'group') {
      // Navigate into group
      loadItems(item.full_path);
    } else {
      // Select project
      setSelectedItem(item);
    }
  };

  const handleSelectGroup = (item) => {
    // Select the group as scope
    setSelectedItem(item);
  };

  const handleBreadcrumbClick = (crumb) => {
    loadItems(crumb.path);
    setSelectedItem(null);
  };

  const handleConfirmSelection = () => {
    if (selectedItem) {
      onScopeSelected({
        scope_type: selectedItem.type,
        scope_id: selectedItem.id,
        scope_path: selectedItem.full_path
      });
    }
  };

  const getVisibilityIcon = (visibility) => {
    switch (visibility) {
      case 'public': return '🌐';
      case 'internal': return '🏢';
      case 'private': return '🔒';
      default: return '';
    }
  };

  const getTypeIcon = (type) => {
    return type === 'group' ? '📁' : '📦';
  };

  return (
    <div className="gitlab-scope-picker">
      <div className="scope-picker-header">
        <h3>Select Migration Scope</h3>
        <p>Choose a GitLab group or project to migrate</p>
      </div>

      {/* Current Scope Display */}
      {currentScope && (
        <div className="current-scope">
          <span className="scope-label">Current Scope:</span>
          <span className="scope-value">
            {getTypeIcon(currentScope.scope_type)} {currentScope.scope_path}
          </span>
        </div>
      )}

      {/* Breadcrumbs */}
      <div className="breadcrumbs">
        {breadcrumbs.map((crumb, index) => (
          <span key={index}>
            {index > 0 && <span className="breadcrumb-separator">/</span>}
            <button
              className={`breadcrumb-btn ${index === breadcrumbs.length - 1 ? 'active' : ''}`}
              onClick={() => handleBreadcrumbClick(crumb)}
            >
              {crumb.name}
            </button>
          </span>
        ))}
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => loadItems(currentPath)}>Retry</button>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="loading-overlay">
          <Loading size="medium" />
          <span>Loading GitLab structure...</span>
        </div>
      )}

      {/* Items List */}
      {!loading && !error && (
        <div className="items-list">
          {items.length === 0 ? (
            <div className="empty-state">
              <p>No groups or projects found at this level.</p>
              {currentPath && (
                <button onClick={() => loadItems(parentPath)}>
                  ← Go back
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Groups first */}
              {items.filter(i => i.type === 'group').map(item => (
                <div
                  key={`group-${item.id}`}
                  className={`scope-item group ${selectedItem?.id === item.id ? 'selected' : ''}`}
                >
                  <div className="item-main" onClick={() => handleItemClick(item)}>
                    <span className="item-icon">{getTypeIcon(item.type)}</span>
                    <div className="item-info">
                      <span className="item-name">{item.name}</span>
                      <span className="item-path">{item.full_path}</span>
                      {item.description && (
                        <span className="item-description">{item.description}</span>
                      )}
                    </div>
                    <span className="visibility-badge">
                      {getVisibilityIcon(item.visibility)} {item.visibility}
                    </span>
                  </div>
                  <div className="item-actions">
                    <button
                      className="select-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectGroup(item);
                      }}
                      title="Select this group as migration scope"
                    >
                      Select Group
                    </button>
                    <button
                      className="browse-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleItemClick(item);
                      }}
                      title="Browse group contents"
                    >
                      Browse →
                    </button>
                  </div>
                </div>
              ))}

              {/* Projects */}
              {items.filter(i => i.type === 'project').map(item => (
                <div
                  key={`project-${item.id}`}
                  className={`scope-item project ${selectedItem?.id === item.id ? 'selected' : ''}`}
                  onClick={() => handleItemClick(item)}
                >
                  <div className="item-main">
                    <span className="item-icon">{getTypeIcon(item.type)}</span>
                    <div className="item-info">
                      <span className="item-name">{item.name}</span>
                      <span className="item-path">{item.full_path}</span>
                      {item.description && (
                        <span className="item-description">{item.description}</span>
                      )}
                      {item.default_branch && (
                        <span className="item-branch">🌿 {item.default_branch}</span>
                      )}
                    </div>
                    <span className="visibility-badge">
                      {getVisibilityIcon(item.visibility)} {item.visibility}
                    </span>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {/* Selection Summary */}
      {selectedItem && (
        <div className="selection-summary">
          <div className="selection-info">
            <span className="selection-label">Selected:</span>
            <span className="selection-value">
              {getTypeIcon(selectedItem.type)} <strong>{selectedItem.full_path}</strong>
              <span className="selection-type">({selectedItem.type})</span>
            </span>
          </div>
          <div className="selection-actions">
            <button className="cancel-btn" onClick={() => setSelectedItem(null)}>
              Cancel
            </button>
            <button className="confirm-btn" onClick={handleConfirmSelection}>
              Confirm Selection
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GitLabScopePicker;
