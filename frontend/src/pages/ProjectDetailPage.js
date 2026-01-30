/**
 * Project Detail Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { projectsAPI, runsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './ProjectDetailPage.css';

export const ProjectDetailPage = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const toast = useToast();

  const loadProjectData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectResponse, runsResponse] = await Promise.all([
        projectsAPI.get(id),
        runsAPI.list(id, { limit: 5 }),
      ]);
      
      setProject(projectResponse.data);
      setRuns(runsResponse.data);
    } catch (error) {
      console.error('Failed to load project:', error);
      toast.error('Failed to load project details');
      navigate('/projects');
    } finally {
      setLoading(false);
    }
  }, [id, toast, navigate]);

  useEffect(() => {
    loadProjectData();
  }, [loadProjectData]);

  const handleStartRun = () => {
    navigate(`/projects/${id}/runs/new`);
  };

  if (loading) {
    return <Loading message="Loading project..." />;
  }

  if (!project) {
    return null;
  }

  return (
    <div className="page project-detail-page">
      <div className="page-header">
        <div>
          <div className="breadcrumb">
            <Link to="/projects">Projects</Link>
            <span className="separator">›</span>
            <span>{project.name}</span>
          </div>
          <h1>{project.name}</h1>
          {project.description && (
            <p className="page-subtitle">{project.description}</p>
          )}
        </div>
        <button onClick={handleStartRun} className="btn btn-primary">
          Start New Run
        </button>
      </div>

      <div className="project-overview">
        <div className="overview-card">
          <h3>Status</h3>
          <span className={`status-badge status-${project.status}`}>
            {project.status}
          </span>
        </div>
        
        <div className="overview-card">
          <h3>Created</h3>
          <p>{new Date(project.created_at).toLocaleDateString()}</p>
        </div>
        
        <div className="overview-card">
          <h3>Last Updated</h3>
          <p>{new Date(project.updated_at).toLocaleDateString()}</p>
        </div>
        
        <div className="overview-card">
          <h3>Total Runs</h3>
          <p>{runs.length}</p>
        </div>
      </div>

      <div className="project-sections">
        <div className="section">
          <div className="section-header">
            <h2>Connections</h2>
            <Link to={`/projects/${id}/connections`} className="btn btn-sm">
              Manage Connections
            </Link>
          </div>
          <div className="content">
            <div className="connection-grid">
              <div className="connection-card">
                <h4>GitLab Source</h4>
                <p className="connection-url">
                  {project.settings?.gitlab?.url || 'Not configured'}
                </p>
                <span className={`connection-status ${project.settings?.gitlab?.url ? 'connected' : 'disconnected'}`}>
                  {project.settings?.gitlab?.url ? '● Connected' : '○ Not Connected'}
                </span>
              </div>
              
              <div className="connection-card">
                <h4>GitHub Target</h4>
                <p className="connection-url">
                  {project.settings?.github?.org || 'Personal account'}
                </p>
                <span className={`connection-status ${project.settings?.github?.token_last4 ? 'connected' : 'disconnected'}`}>
                  {project.settings?.github?.token_last4 ? '● Connected' : '○ Not Connected'}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <h2>Recent Runs</h2>
            <Link to={`/projects/${id}/runs`} className="btn btn-sm">
              View All Runs
            </Link>
          </div>
          <div className="content">
            {runs.length === 0 ? (
              <div className="empty-state">
                <p>No runs yet.</p>
                <p className="hint">Start your first migration run to get started.</p>
              </div>
            ) : (
              <div className="runs-list">
                {runs.map((run) => (
                  <Link
                    key={run.id}
                    to={`/runs/${run.id}`}
                    className="run-item"
                  >
                    <div className="run-info">
                      <strong>Run #{run.id.slice(-6)}</strong>
                      <span className="run-date">
                        {new Date(run.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span className={`status-badge status-${run.status}`}>
                      {run.status}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <h2>Quick Actions</h2>
          </div>
          <div className="content">
            <div className="action-grid">
              <button
                onClick={handleStartRun}
                className="action-button"
              >
                <span className="action-icon">▶</span>
                <span className="action-text">Start Migration Run</span>
              </button>
              
              <Link
                to={`/projects/${id}/connections`}
                className="action-button"
              >
                <span className="action-icon">🔗</span>
                <span className="action-text">Manage Connections</span>
              </Link>
              
              <Link
                to={`/projects/${id}/settings`}
                className="action-button"
              >
                <span className="action-icon">⚙</span>
                <span className="action-text">Project Settings</span>
              </Link>
              
              <Link
                to={`/projects/${id}/runs`}
                className="action-button"
              >
                <span className="action-icon">📊</span>
                <span className="action-text">View Run History</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
