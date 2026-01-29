/**
 * Connections Management Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { projectsAPI, connectionsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './ConnectionsPage.css';

export const ConnectionsPage = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    type: 'gitlab',
    url: '',
    token: '',
    name: ''
  });
  const toast = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectResponse, connectionsResponse] = await Promise.all([
        projectsAPI.get(id),
        connectionsAPI.list(id),
      ]);
      
      setProject(projectResponse.data);
      setConnections(connectionsResponse.data);
    } catch (error) {
      console.error('Failed to load connections:', error);
      toast.error('Failed to load connections');
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddConnection = async (e) => {
    e.preventDefault();
    
    try {
      await connectionsAPI.create(id, formData);
      toast.success('Connection added successfully');
      setShowAddForm(false);
      setFormData({ type: 'gitlab', url: '', token: '', name: '' });
      loadData();
    } catch (error) {
      console.error('Failed to add connection:', error);
      toast.error(error.response?.data?.detail || 'Failed to add connection');
    }
  };

  const handleTestConnection = async (connectionId) => {
    try {
      await connectionsAPI.test(id, connectionId);
      toast.success('Connection test successful');
    } catch (error) {
      console.error('Connection test failed:', error);
      toast.error('Connection test failed');
    }
  };

  const handleDeleteConnection = async (connectionId) => {
    if (!window.confirm('Are you sure you want to delete this connection?')) {
      return;
    }

    try {
      await connectionsAPI.delete(id, connectionId);
      toast.success('Connection deleted successfully');
      loadData();
    } catch (error) {
      console.error('Failed to delete connection:', error);
      toast.error('Failed to delete connection');
    }
  };

  if (loading) {
    return <Loading message="Loading connections..." />;
  }

  if (!project) {
    return null;
  }

  return (
    <div className="page connections-page">
      <div className="page-header">
        <div>
          <div className="breadcrumb">
            <Link to="/projects">Projects</Link>
            <span className="separator">›</span>
            <Link to={`/projects/${id}`}>{project.name}</Link>
            <span className="separator">›</span>
            <span>Connections</span>
          </div>
          <h1>Manage Connections</h1>
          <p className="page-subtitle">Configure GitLab source and GitHub target connections</p>
        </div>
        <button 
          onClick={() => setShowAddForm(!showAddForm)} 
          className="btn btn-primary"
        >
          + Add Connection
        </button>
      </div>

      {showAddForm && (
        <div className="add-form-section">
          <h2>Add New Connection</h2>
          <form onSubmit={handleAddConnection}>
            <div className="form-group">
              <label>Connection Type</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                required
              >
                <option value="gitlab">GitLab (Source)</option>
                <option value="github">GitHub (Target)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Connection Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Primary GitLab"
                required
              />
            </div>

            <div className="form-group">
              <label>URL</label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                placeholder={formData.type === 'gitlab' ? 'https://gitlab.com' : 'https://github.com'}
                required
              />
            </div>

            <div className="form-group">
              <label>Access Token</label>
              <input
                type="password"
                value={formData.token}
                onChange={(e) => setFormData({ ...formData, token: e.target.value })}
                placeholder="Personal access token"
                required
              />
              <small className="form-hint">
                {formData.type === 'gitlab' 
                  ? 'GitLab personal access token with api and read_repository scopes'
                  : 'GitHub personal access token with repo scope'}
              </small>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn btn-primary">
                Add Connection
              </button>
              <button 
                type="button" 
                onClick={() => setShowAddForm(false)} 
                className="btn"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="content">
        {connections.length === 0 ? (
          <div className="empty-state">
            <p>No connections configured yet.</p>
            <p className="hint">Add your first GitLab or GitHub connection to get started.</p>
          </div>
        ) : (
          <div className="connections-grid">
            {connections.map((connection) => (
              <div key={connection.id} className="connection-card">
                <div className="connection-header">
                  <div>
                    <h3>{connection.name || connection.type}</h3>
                    <span className={`connection-type ${connection.type}`}>
                      {connection.type === 'gitlab' ? '🦊 GitLab' : '🐙 GitHub'}
                    </span>
                  </div>
                  <span className={`status-badge status-${connection.status || 'unknown'}`}>
                    {connection.status || 'unknown'}
                  </span>
                </div>

                <div className="connection-details">
                  <div className="detail-row">
                    <span className="detail-label">URL:</span>
                    <span className="detail-value">{connection.url}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Token:</span>
                    <span className="detail-value">••••••••</span>
                  </div>
                  {connection.created_at && (
                    <div className="detail-row">
                      <span className="detail-label">Added:</span>
                      <span className="detail-value">
                        {new Date(connection.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>

                <div className="connection-actions">
                  <button
                    onClick={() => handleTestConnection(connection.id)}
                    className="btn btn-sm"
                  >
                    Test Connection
                  </button>
                  <button
                    onClick={() => handleDeleteConnection(connection.id)}
                    className="btn btn-sm btn-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
