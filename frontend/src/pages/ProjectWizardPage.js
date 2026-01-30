/**
 * Project Creation Wizard
 */
import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectsAPI, connectionsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { ConnectionTest } from '../components/ConnectionTest';
import { Loading } from '../components/Loading';
import './ProjectWizard.css';

// Inline Scope Picker for wizard (simplified version)
const WizardScopePicker = ({ gitlabUrl, gitlabToken, selectedScope, onScopeSelected }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [items, setItems] = useState([]);
  const [currentPath, setCurrentPath] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([{ name: 'Root', path: null }]);

  const loadItems = useCallback(async (path = null) => {
    if (!gitlabUrl || !gitlabToken) {
      setError('GitLab credentials are required');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Direct API call since we don't have a project yet
      const response = await fetch(
        `http://localhost:8000/api/connections/test/gitlab/browse?${new URLSearchParams({
          base_url: gitlabUrl,
          token: gitlabToken,
          ...(path && { path })
        })}`
      );
      const data = await response.json();
      
      if (data.success) {
        setItems(data.items || []);
        setCurrentPath(path);
        
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
        setError(data.error || 'Failed to load items');
      }
    } catch (err) {
      console.error('Error loading GitLab items:', err);
      setError('Failed to connect to GitLab');
    } finally {
      setLoading(false);
    }
  }, [gitlabUrl, gitlabToken]);

  React.useEffect(() => {
    if (gitlabUrl && gitlabToken) {
      loadItems(null);
    }
  }, [gitlabUrl, gitlabToken, loadItems]);

  const handleItemClick = (item) => {
    if (item.type === 'group') {
      loadItems(item.full_path);
    } else {
      onScopeSelected({
        scope_type: item.type,
        scope_id: item.id,
        scope_path: item.full_path
      });
    }
  };

  const handleSelectGroup = (item) => {
    onScopeSelected({
      scope_type: item.type,
      scope_id: item.id,
      scope_path: item.full_path
    });
  };

  const getVisibilityIcon = (visibility) => {
    switch (visibility) {
      case 'public': return '🌐';
      case 'internal': return '🏢';
      case 'private': return '🔒';
      default: return '';
    }
  };

  if (!gitlabUrl || !gitlabToken) {
    return (
      <div className="scope-picker-empty">
        <p>⚠️ Please configure GitLab connection first</p>
      </div>
    );
  }

  return (
    <div className="wizard-scope-picker">
      {/* Breadcrumbs */}
      <div className="scope-breadcrumbs">
        {breadcrumbs.map((crumb, index) => (
          <span key={index}>
            {index > 0 && <span className="separator">/</span>}
            <button
              type="button"
              className={`breadcrumb-btn ${index === breadcrumbs.length - 1 ? 'active' : ''}`}
              onClick={() => loadItems(crumb.path)}
            >
              {crumb.name}
            </button>
          </span>
        ))}
      </div>

      {error && (
        <div className="scope-error">
          ⚠️ {error}
          <button type="button" onClick={() => loadItems(currentPath)}>Retry</button>
        </div>
      )}

      {loading ? (
        <div className="scope-loading">
          <Loading size="small" />
          <span>Loading GitLab structure...</span>
        </div>
      ) : (
        <div className="scope-items">
          {items.length === 0 ? (
            <div className="scope-empty">No groups or projects found</div>
          ) : (
            items.map(item => (
              <div
                key={`${item.type}-${item.id}`}
                className={`scope-item ${item.type} ${selectedScope?.scope_id === item.id ? 'selected' : ''}`}
              >
                <div className="scope-item-main" onClick={() => handleItemClick(item)}>
                  <span className="scope-icon">{item.type === 'group' ? '📁' : '📦'}</span>
                  <div className="scope-item-info">
                    <span className="scope-name">{item.name}</span>
                    <span className="scope-path">{item.full_path}</span>
                  </div>
                  <span className="scope-visibility">
                    {getVisibilityIcon(item.visibility)}
                  </span>
                </div>
                {item.type === 'group' && (
                  <div className="scope-item-actions">
                    <button
                      type="button"
                      className="btn-select"
                      onClick={(e) => { e.stopPropagation(); handleSelectGroup(item); }}
                    >
                      Select Group
                    </button>
                    <button
                      type="button"
                      className="btn-browse"
                      onClick={(e) => { e.stopPropagation(); loadItems(item.full_path); }}
                    >
                      Browse →
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {selectedScope && (
        <div className="scope-selected">
          <span>✓ Selected: </span>
          <strong>{selectedScope.scope_path}</strong>
          <span className="scope-type-badge">{selectedScope.scope_type}</span>
        </div>
      )}
    </div>
  );
};

export const ProjectWizardPage = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [projectData, setProjectData] = useState({
    name: '',
    description: '',
    gitlab_url: 'https://gitlab.com',
    gitlab_token: '',
    github_token: '',
    github_org: '',
    scope: null,
  });
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const toast = useToast();

  const steps = [
    { id: 1, title: 'Basic Info', desc: 'Project name and description' },
    { id: 2, title: 'GitLab Source', desc: 'Connect to GitLab' },
    { id: 3, title: 'Migration Scope', desc: 'Select what to migrate' },
    { id: 4, title: 'GitHub Target', desc: 'Connect to GitHub' },
    { id: 5, title: 'Review', desc: 'Review and create' },
  ];

  const handleChange = (field, value) => {
    setProjectData(prev => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    setCurrentStep(prev => prev - 1);
  };

  const validateStep = (step) => {
    switch (step) {
      case 1:
        if (!projectData.name.trim()) {
          toast.error('Project name is required');
          return false;
        }
        return true;
      case 2:
        if (!projectData.gitlab_url.trim()) {
          toast.error('GitLab URL is required');
          return false;
        }
        if (!projectData.gitlab_token.trim()) {
          toast.error('GitLab token is required');
          return false;
        }
        return true;
      case 3:
        if (!projectData.scope) {
          toast.error('Please select a migration scope (group or project)');
          return false;
        }
        return true;
      case 4:
        if (!projectData.github_token.trim()) {
          toast.error('GitHub token is required');
          return false;
        }
        return true;
      default:
        return true;
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const response = await projectsAPI.create({
        name: projectData.name,
        description: projectData.description,
        settings: {
          gitlab: {
            url: projectData.gitlab_url,
            token: projectData.gitlab_token,
            scope_type: projectData.scope?.scope_type,
            scope_id: projectData.scope?.scope_id,
            scope_path: projectData.scope?.scope_path,
          },
          github: {
            token: projectData.github_token,
            org: projectData.github_org,
          },
        },
      });
      
      toast.success('Project created successfully!');
      navigate(`/projects/${response.data.id}`);
    } catch (error) {
      console.error('Failed to create project:', error);
      toast.error(error.response?.data?.detail || 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page project-wizard-page">
      <div className="wizard-container">
        <div className="wizard-header">
          <h1>Create New Project</h1>
          <div className="wizard-steps">
            {steps.map((step) => (
              <div
                key={step.id}
                className={`wizard-step ${currentStep === step.id ? 'active' : ''} ${
                  currentStep > step.id ? 'completed' : ''
                }`}
              >
                <div className="step-number">{step.id}</div>
                <div className="step-info">
                  <div className="step-title">{step.title}</div>
                  <div className="step-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="wizard-content">
          {currentStep === 1 && (
            <div className="wizard-step-content">
              <h2>Basic Information</h2>
              <p className="step-description">
                Enter the basic details for your migration project.
              </p>
              
              <div className="form-group">
                <label htmlFor="name">Project Name *</label>
                <input
                  id="name"
                  type="text"
                  value={projectData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  placeholder="e.g., My Project Migration"
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label htmlFor="description">Description</label>
                <textarea
                  id="description"
                  value={projectData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  placeholder="Optional description of your migration project"
                  rows="4"
                />
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="wizard-step-content">
              <h2>GitLab Source Connection</h2>
              <p className="step-description">
                Configure the connection to your GitLab instance.
              </p>
              
              <div className="form-group">
                <label htmlFor="gitlab_url">GitLab URL *</label>
                <input
                  id="gitlab_url"
                  type="url"
                  value={projectData.gitlab_url}
                  onChange={(e) => handleChange('gitlab_url', e.target.value)}
                  placeholder="https://gitlab.com"
                />
                <span className="form-hint">
                  Enter the full URL of your GitLab instance
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="gitlab_token">Personal Access Token *</label>
                <input
                  id="gitlab_token"
                  type="password"
                  value={projectData.gitlab_token}
                  onChange={(e) => handleChange('gitlab_token', e.target.value)}
                  placeholder="Enter your GitLab PAT"
                />
                <span className="form-hint">
                  Token needs: api, read_repository, read_user scopes
                </span>
              </div>

              <ConnectionTest 
                type="gitlab"
                url={projectData.gitlab_url}
                token={projectData.gitlab_token}
              />
            </div>
          )}

          {currentStep === 3 && (
            <div className="wizard-step-content">
              <h2>Select Migration Scope</h2>
              <p className="step-description">
                Choose what you want to migrate: a group (all projects within) or a specific project.
              </p>
              
              <WizardScopePicker
                gitlabUrl={projectData.gitlab_url}
                gitlabToken={projectData.gitlab_token}
                selectedScope={projectData.scope}
                onScopeSelected={(scope) => handleChange('scope', scope)}
              />
            </div>
          )}

          {currentStep === 4 && (
            <div className="wizard-step-content">
              <h2>GitHub Target Connection</h2>
              <p className="step-description">
                Configure the connection to your GitHub account.
              </p>
              
              <div className="form-group">
                <label htmlFor="github_token">Personal Access Token *</label>
                <input
                  id="github_token"
                  type="password"
                  value={projectData.github_token}
                  onChange={(e) => handleChange('github_token', e.target.value)}
                  placeholder="Enter your GitHub PAT"
                />
                <span className="form-hint">
                  Token needs: repo, workflow, admin:org scopes
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="github_org">Organization/User (Optional)</label>
                <input
                  id="github_org"
                  type="text"
                  value={projectData.github_org}
                  onChange={(e) => handleChange('github_org', e.target.value)}
                  placeholder="organization-name or username"
                />
                <span className="form-hint">
                  Leave empty to use your personal account
                </span>
              </div>

              <ConnectionTest 
                type="github"
                url="https://api.github.com"
                token={projectData.github_token}
              />
            </div>
          )}

          {currentStep === 5 && (
            <div className="wizard-step-content">
              <h2>Review & Create</h2>
              <p className="step-description">
                Please review your project configuration before creating.
              </p>
              
              <div className="review-section">
                <h3>Basic Information</h3>
                <div className="review-item">
                  <strong>Project Name:</strong> {projectData.name}
                </div>
                {projectData.description && (
                  <div className="review-item">
                    <strong>Description:</strong> {projectData.description}
                  </div>
                )}
              </div>

              <div className="review-section">
                <h3>GitLab Source</h3>
                <div className="review-item">
                  <strong>URL:</strong> {projectData.gitlab_url}
                </div>
                <div className="review-item">
                  <strong>Token:</strong> ••••••••••••
                </div>
              </div>

              <div className="review-section">
                <h3>Migration Scope</h3>
                {projectData.scope ? (
                  <>
                    <div className="review-item">
                      <strong>Type:</strong> {projectData.scope.scope_type}
                    </div>
                    <div className="review-item">
                      <strong>Path:</strong> {projectData.scope.scope_path}
                    </div>
                  </>
                ) : (
                  <div className="review-item warning">
                    ⚠️ No scope selected
                  </div>
                )}
              </div>

              <div className="review-section">
                <h3>GitHub Target</h3>
                <div className="review-item">
                  <strong>Token:</strong> ••••••••••••
                </div>
                {projectData.github_org && (
                  <div className="review-item">
                    <strong>Organization:</strong> {projectData.github_org}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="wizard-actions">
          {currentStep > 1 && (
            <button
              onClick={handleBack}
              className="btn btn-secondary"
              disabled={loading}
            >
              Back
            </button>
          )}
          
          <div style={{ flex: 1 }} />
          
          <button
            onClick={() => navigate('/projects')}
            className="btn btn-secondary"
            disabled={loading}
          >
            Cancel
          </button>
          
          {currentStep < 5 ? (
            <button
              onClick={handleNext}
              className="btn btn-primary"
              disabled={loading}
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              className="btn btn-primary"
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
