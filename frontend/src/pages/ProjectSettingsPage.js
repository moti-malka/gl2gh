/**
 * Project Settings Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { projectsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './ProjectSettingsPage.css';

export const ProjectSettingsPage = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    settings: {
      gitlab: {
        url: '',
        group: '',
      },
      github: {
        org: '',
        visibility: 'private',
      },
      migration: {
        include_issues: true,
        include_merge_requests: true,
        include_wikis: true,
        include_releases: true,
      },
      behavior: {
        auto_retry_failed: false,
        parallel_migrations: 1,
        notification_enabled: false,
      }
    }
  });

  const loadProject = useCallback(async () => {
    setLoading(true);
    try {
      const response = await projectsAPI.get(id);
      const projectData = response.data;
      
      setProject(projectData);
      setFormData({
        name: projectData.name || '',
        description: projectData.description || '',
        settings: {
          gitlab: {
            url: projectData.settings?.gitlab?.url || '',
            group: projectData.settings?.gitlab?.group || '',
          },
          github: {
            org: projectData.settings?.github?.org || '',
            visibility: projectData.settings?.github?.visibility || 'private',
          },
          migration: {
            include_issues: projectData.settings?.migration?.include_issues ?? true,
            include_merge_requests: projectData.settings?.migration?.include_merge_requests ?? true,
            include_wikis: projectData.settings?.migration?.include_wikis ?? true,
            include_releases: projectData.settings?.migration?.include_releases ?? true,
          },
          behavior: {
            auto_retry_failed: projectData.settings?.behavior?.auto_retry_failed ?? false,
            parallel_migrations: projectData.settings?.behavior?.parallel_migrations || 1,
            notification_enabled: projectData.settings?.behavior?.notification_enabled ?? false,
          }
        }
      });
    } catch (error) {
      console.error('Failed to load project:', error);
      toast.error('Failed to load project settings');
      navigate('/projects');
    } finally {
      setLoading(false);
    }
  }, [id, toast, navigate]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      await projectsAPI.update(id, formData);
      toast.success('Project settings updated successfully');
      navigate(`/projects/${id}`);
    } catch (error) {
      console.error('Failed to update project:', error);
      toast.error(error.response?.data?.detail || 'Failed to update project settings');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate(`/projects/${id}`);
  };

  if (loading) {
    return <Loading message="Loading project settings..." />;
  }

  if (!project) {
    return null;
  }

  return (
    <div className="page project-settings-page">
      <div className="page-header">
        <div>
          <div className="breadcrumb">
            <Link to="/projects">Projects</Link>
            <span className="separator">›</span>
            <Link to={`/projects/${id}`}>{project.name}</Link>
            <span className="separator">›</span>
            <span>Settings</span>
          </div>
          <h1>Project Settings</h1>
          <p className="page-subtitle">Configure project details and migration behavior</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="settings-form">
        {/* General Settings */}
        <div className="settings-section">
          <h2>General</h2>
          <div className="form-group">
            <label>Project Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
            />
          </div>
        </div>

        {/* GitLab Settings */}
        <div className="settings-section">
          <h2>GitLab Source</h2>
          <div className="form-group">
            <label>GitLab URL</label>
            <input
              type="url"
              value={formData.settings.gitlab.url}
              onChange={(e) => setFormData({
                ...formData,
                settings: {
                  ...formData.settings,
                  gitlab: { ...formData.settings.gitlab, url: e.target.value }
                }
              })}
              placeholder="https://gitlab.com"
            />
          </div>

          <div className="form-group">
            <label>GitLab Group</label>
            <input
              type="text"
              value={formData.settings.gitlab.group}
              onChange={(e) => setFormData({
                ...formData,
                settings: {
                  ...formData.settings,
                  gitlab: { ...formData.settings.gitlab, group: e.target.value }
                }
              })}
              placeholder="my-group/sub-group"
            />
          </div>
        </div>

        {/* GitHub Settings */}
        <div className="settings-section">
          <h2>GitHub Target</h2>
          <div className="form-group">
            <label>GitHub Organization</label>
            <input
              type="text"
              value={formData.settings.github.org}
              onChange={(e) => setFormData({
                ...formData,
                settings: {
                  ...formData.settings,
                  github: { ...formData.settings.github, org: e.target.value }
                }
              })}
              placeholder="my-organization"
            />
            <small className="form-hint">Leave empty for personal account</small>
          </div>

          <div className="form-group">
            <label>Repository Visibility</label>
            <select
              value={formData.settings.github.visibility}
              onChange={(e) => setFormData({
                ...formData,
                settings: {
                  ...formData.settings,
                  github: { ...formData.settings.github, visibility: e.target.value }
                }
              })}
            >
              <option value="private">Private</option>
              <option value="public">Public</option>
              <option value="internal">Internal</option>
            </select>
          </div>
        </div>

        {/* Migration Options */}
        <div className="settings-section">
          <h2>Migration Options</h2>
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.settings.migration.include_issues}
                onChange={(e) => setFormData({
                  ...formData,
                  settings: {
                    ...formData.settings,
                    migration: { ...formData.settings.migration, include_issues: e.target.checked }
                  }
                })}
              />
              <span>Migrate Issues</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.settings.migration.include_merge_requests}
                onChange={(e) => setFormData({
                  ...formData,
                  settings: {
                    ...formData.settings,
                    migration: { ...formData.settings.migration, include_merge_requests: e.target.checked }
                  }
                })}
              />
              <span>Migrate Merge Requests / Pull Requests</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.settings.migration.include_wikis}
                onChange={(e) => setFormData({
                  ...formData,
                  settings: {
                    ...formData.settings,
                    migration: { ...formData.settings.migration, include_wikis: e.target.checked }
                  }
                })}
              />
              <span>Migrate Wikis</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.settings.migration.include_releases}
                onChange={(e) => setFormData({
                  ...formData,
                  settings: {
                    ...formData.settings,
                    migration: { ...formData.settings.migration, include_releases: e.target.checked }
                  }
                })}
              />
              <span>Migrate Releases</span>
            </label>
          </div>
        </div>

        {/* Behavior Settings */}
        <div className="settings-section">
          <h2>Behavior</h2>
          <div className="form-group">
            <label>Parallel Migrations</label>
            <input
              type="number"
              min="1"
              max="10"
              value={formData.settings.behavior.parallel_migrations}
              onChange={(e) => setFormData({
                ...formData,
                settings: {
                  ...formData.settings,
                  behavior: { ...formData.settings.behavior, parallel_migrations: parseInt(e.target.value) || 1 }
                }
              })}
            />
            <small className="form-hint">Number of repositories to migrate in parallel (1-10)</small>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.settings.behavior.auto_retry_failed}
                onChange={(e) => setFormData({
                  ...formData,
                  settings: {
                    ...formData.settings,
                    behavior: { ...formData.settings.behavior, auto_retry_failed: e.target.checked }
                  }
                })}
              />
              <span>Automatically retry failed migrations</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.settings.behavior.notification_enabled}
                onChange={(e) => setFormData({
                  ...formData,
                  settings: {
                    ...formData.settings,
                    behavior: { ...formData.settings.behavior, notification_enabled: e.target.checked }
                  }
                })}
              />
              <span>Enable email notifications</span>
            </label>
          </div>
        </div>

        {/* Form Actions */}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <button type="button" onClick={handleCancel} className="btn" disabled={saving}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};
