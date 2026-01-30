/**
 * Quick Migrate Page - Simplified single project migration
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../components/Toast';
import apiClient from '../services/api';
import './QuickMigratePage.css';

export const QuickMigratePage = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    gitlabUrl: 'https://gitlab.com',
    gitlabProjectPath: '',
    gitlabToken: '',
    githubOrg: '',
    githubRepoName: '',
    githubToken: '',
    includeCi: true,
    includeIssues: true,
    includeWiki: false,
    includeReleases: false,
  });
  
  const [errors, setErrors] = useState({});

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    // Clear error for this field when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const parseGitLabUrl = (url) => {
    // Try to extract project path from full GitLab URL
    // Example: https://gitlab.com/moti.malka25/demo-project -> moti.malka25/demo-project
    try {
      const urlObj = new URL(url);
      const path = urlObj.pathname.replace(/^\//, '').replace(/\.git$/, '');
      if (path && path.includes('/')) {
        return path;
      }
    } catch (e) {
      // Not a valid URL, might already be a path
    }
    return null;
  };

  const handleGitLabUrlBlur = () => {
    // Auto-fill project path if full URL is pasted
    if (formData.gitlabProjectPath === '' && formData.gitlabUrl) {
      const path = parseGitLabUrl(formData.gitlabUrl);
      if (path) {
        setFormData(prev => ({ ...prev, gitlabProjectPath: path }));
      }
    }
  };

  const handleGitLabProjectPathBlur = () => {
    // Auto-suggest GitHub repo name from project path
    if (formData.githubRepoName === '' && formData.gitlabProjectPath) {
      const parts = formData.gitlabProjectPath.split('/');
      const projectName = parts[parts.length - 1];
      setFormData(prev => ({ ...prev, githubRepoName: projectName }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.gitlabUrl) {
      newErrors.gitlabUrl = 'GitLab URL is required';
    } else if (!formData.gitlabUrl.startsWith('http://') && !formData.gitlabUrl.startsWith('https://')) {
      newErrors.gitlabUrl = 'GitLab URL must start with http:// or https://';
    }
    
    if (!formData.gitlabProjectPath) {
      newErrors.gitlabProjectPath = 'GitLab project path is required';
    } else if (!formData.gitlabProjectPath.includes('/')) {
      newErrors.gitlabProjectPath = 'Project path must be in format: username/project or group/subgroup/project';
    }
    
    if (!formData.gitlabToken) {
      newErrors.gitlabToken = 'GitLab token is required';
    }
    
    if (!formData.githubOrg) {
      newErrors.githubOrg = 'GitHub organization/user is required';
    }
    
    if (!formData.githubRepoName) {
      newErrors.githubRepoName = 'GitHub repository name is required';
    }
    
    if (!formData.githubToken) {
      newErrors.githubToken = 'GitHub token is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      toast.error('Please fix the errors in the form');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await apiClient.post('/api/migrate/quick', {
        gitlab_url: formData.gitlabUrl,
        gitlab_project_path: formData.gitlabProjectPath,
        gitlab_token: formData.gitlabToken,
        github_org: formData.githubOrg,
        github_repo_name: formData.githubRepoName,
        github_token: formData.githubToken,
        options: {
          include_ci: formData.includeCi,
          include_issues: formData.includeIssues,
          include_wiki: formData.includeWiki,
          include_releases: formData.includeReleases,
        }
      });
      
      const { run_id, dashboard_url, message } = response.data;
      toast.success(message || 'Migration started successfully!');
      navigate(dashboard_url);
      
    } catch (error) {
      console.error('Failed to start quick migration:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to start migration';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page quick-migrate-page">
      <div className="page-header">
        <h1>Quick Project Migration</h1>
        <p className="page-subtitle">
          Migrate a single GitLab project to GitHub in minutes
        </p>
      </div>

      <form onSubmit={handleSubmit} className="quick-migrate-form">
        <div className="form-section">
          <h2>Source (GitLab)</h2>
          
          <div className="form-group">
            <label htmlFor="gitlabUrl">
              GitLab Instance URL
              <span className="required">*</span>
            </label>
            <input
              id="gitlabUrl"
              name="gitlabUrl"
              type="text"
              value={formData.gitlabUrl}
              onChange={handleInputChange}
              onBlur={handleGitLabUrlBlur}
              placeholder="https://gitlab.com"
              className={errors.gitlabUrl ? 'error' : ''}
            />
            {errors.gitlabUrl && <span className="error-message">{errors.gitlabUrl}</span>}
            <small className="field-hint">The base URL of your GitLab instance</small>
          </div>

          <div className="form-group">
            <label htmlFor="gitlabProjectPath">
              GitLab Project Path
              <span className="required">*</span>
            </label>
            <input
              id="gitlabProjectPath"
              name="gitlabProjectPath"
              type="text"
              value={formData.gitlabProjectPath}
              onChange={handleInputChange}
              onBlur={handleGitLabProjectPathBlur}
              placeholder="username/project or group/subgroup/project"
              className={errors.gitlabProjectPath ? 'error' : ''}
            />
            {errors.gitlabProjectPath && <span className="error-message">{errors.gitlabProjectPath}</span>}
            <small className="field-hint">Example: moti.malka25/demo-project</small>
          </div>

          <div className="form-group">
            <label htmlFor="gitlabToken">
              GitLab Personal Access Token (PAT)
              <span className="required">*</span>
            </label>
            <input
              id="gitlabToken"
              name="gitlabToken"
              type="password"
              value={formData.gitlabToken}
              onChange={handleInputChange}
              placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
              className={errors.gitlabToken ? 'error' : ''}
            />
            {errors.gitlabToken && <span className="error-message">{errors.gitlabToken}</span>}
            <small className="field-hint">
              Token with read_api and read_repository permissions
            </small>
          </div>
        </div>

        <div className="form-divider">
          <span>↓ Target ↓</span>
        </div>

        <div className="form-section">
          <h2>Target (GitHub)</h2>
          
          <div className="form-group">
            <label htmlFor="githubOrg">
              GitHub Organization/User
              <span className="required">*</span>
            </label>
            <input
              id="githubOrg"
              name="githubOrg"
              type="text"
              value={formData.githubOrg}
              onChange={handleInputChange}
              placeholder="your-username or your-org"
              className={errors.githubOrg ? 'error' : ''}
            />
            {errors.githubOrg && <span className="error-message">{errors.githubOrg}</span>}
            <small className="field-hint">The GitHub organization or user account</small>
          </div>

          <div className="form-group">
            <label htmlFor="githubRepoName">
              GitHub Repository Name
              <span className="required">*</span>
            </label>
            <input
              id="githubRepoName"
              name="githubRepoName"
              type="text"
              value={formData.githubRepoName}
              onChange={handleInputChange}
              placeholder="repository-name"
              className={errors.githubRepoName ? 'error' : ''}
            />
            {errors.githubRepoName && <span className="error-message">{errors.githubRepoName}</span>}
            <small className="field-hint">Name for the new GitHub repository</small>
          </div>

          <div className="form-group">
            <label htmlFor="githubToken">
              GitHub Personal Access Token
              <span className="required">*</span>
            </label>
            <input
              id="githubToken"
              name="githubToken"
              type="password"
              value={formData.githubToken}
              onChange={handleInputChange}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              className={errors.githubToken ? 'error' : ''}
            />
            {errors.githubToken && <span className="error-message">{errors.githubToken}</span>}
            <small className="field-hint">
              Token with repo and workflow permissions
            </small>
          </div>
        </div>

        <div className="form-section">
          <h2>Migration Options</h2>
          
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="includeCi"
                checked={formData.includeCi}
                onChange={handleInputChange}
              />
              <span>Include CI/CD conversion</span>
            </label>
            <small className="field-hint">Convert GitLab CI to GitHub Actions</small>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="includeIssues"
                checked={formData.includeIssues}
                onChange={handleInputChange}
              />
              <span>Include issues and merge requests</span>
            </label>
            <small className="field-hint">Migrate issues and PRs (read-only export)</small>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="includeWiki"
                checked={formData.includeWiki}
                onChange={handleInputChange}
              />
              <span>Include wiki</span>
            </label>
            <small className="field-hint">Migrate project wiki pages</small>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="includeReleases"
                checked={formData.includeReleases}
                onChange={handleInputChange}
              />
              <span>Include releases</span>
            </label>
            <small className="field-hint">Migrate release notes and tags</small>
          </div>
        </div>

        <div className="form-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/projects')}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Starting Migration...' : 'Start Migration'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default QuickMigratePage;
