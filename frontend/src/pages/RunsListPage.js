/**
 * Runs List Page - View all migration runs for a project
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { projectsAPI, runsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './RunsListPage.css';

export const RunsListPage = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);
  const toast = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) {
        params.status = statusFilter;
      }

      const [projectResponse, runsResponse] = await Promise.all([
        projectsAPI.get(id),
        runsAPI.list(id, params),
      ]);
      
      setProject(projectResponse.data);
      setRuns(runsResponse.data);
    } catch (error) {
      console.error('Failed to load runs:', error);
      toast.error('Failed to load run history');
    } finally {
      setLoading(false);
    }
  }, [id, statusFilter, toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCancel = async (runId) => {
    if (!window.confirm('Are you sure you want to cancel this run?')) {
      return;
    }

    try {
      await runsAPI.cancel(runId);
      toast.success('Run cancelled');
      loadData();
    } catch (error) {
      console.error('Failed to cancel run:', error);
      toast.error('Failed to cancel run');
    }
  };

  const getElapsedTime = (run) => {
    if (!run.started_at) return 'Not started';
    
    const start = new Date(run.started_at);
    const end = run.completed_at ? new Date(run.completed_at) : new Date();
    const seconds = Math.floor((end - start) / 1000);
    
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  // Pagination
  const totalPages = Math.ceil(runs.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedRuns = runs.slice(startIndex, startIndex + itemsPerPage);

  if (loading) {
    return <Loading message="Loading run history..." />;
  }

  if (!project) {
    return null;
  }

  return (
    <div className="page runs-list-page">
      <div className="page-header">
        <div>
          <div className="breadcrumb">
            <Link to="/projects">Projects</Link>
            <span className="separator">›</span>
            <Link to={`/projects/${id}`}>{project.name}</Link>
            <span className="separator">›</span>
            <span>Run History</span>
          </div>
          <h1>Migration Run History</h1>
          <p className="page-subtitle">View all migration runs for this project</p>
        </div>
        <Link to={`/projects/${id}/runs/new`} className="btn btn-primary">
          + New Run
        </Link>
      </div>

      <div className="content">
        <div className="filters">
          <div className="filter-group">
            <label>Status:</label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="filter-select"
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div className="stats">
            <span className="stat-item">
              <strong>{runs.length}</strong> Total Runs
            </span>
            <span className="stat-item">
              <strong>{runs.filter(r => r.status === 'completed').length}</strong> Completed
            </span>
            <span className="stat-item">
              <strong>{runs.filter(r => r.status === 'failed').length}</strong> Failed
            </span>
          </div>
        </div>

        {runs.length === 0 ? (
          <div className="empty-state">
            <p>No runs found.</p>
            <p className="hint">
              {statusFilter
                ? 'Try adjusting your filters.'
                : 'Start your first migration run to get started.'}
            </p>
          </div>
        ) : (
          <>
            <div className="runs-table">
              <table>
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Duration</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedRuns.map((run) => {
                    const isRunning = ['pending', 'running'].includes(run.status);
                    return (
                      <tr key={run.id}>
                        <td>
                          <Link to={`/runs/${run.id}`} className="run-link">
                            #{run.id.slice(-8)}
                          </Link>
                        </td>
                        <td>
                          <span className="run-mode">{run.mode || 'standard'}</span>
                        </td>
                        <td>
                          <span className={`status-badge status-${run.status}`}>
                            {run.status}
                          </span>
                        </td>
                        <td>
                          {run.created_at
                            ? new Date(run.created_at).toLocaleString()
                            : 'N/A'}
                        </td>
                        <td>{getElapsedTime(run)}</td>
                        <td>
                          <div className="action-buttons">
                            <Link
                              to={`/runs/${run.id}`}
                              className="btn btn-sm"
                            >
                              View
                            </Link>
                            {isRunning && (
                              <button
                                onClick={() => handleCancel(run.id)}
                                className="btn btn-sm btn-danger"
                              >
                                Cancel
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="btn btn-sm"
                >
                  Previous
                </button>
                <span className="pagination-info">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="btn btn-sm"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
