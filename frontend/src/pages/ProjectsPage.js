/**
 * Projects List Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { projectsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './ProjectsPage.css';

export const ProjectsPage = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);
  
  const toast = useToast();

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) {
        params.status = statusFilter;
      }
      
      const response = await projectsAPI.list(params);
      setProjects(response.data);
    } catch (error) {
      console.error('Failed to load projects:', error);
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, toast]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this project?')) {
      return;
    }

    try {
      await projectsAPI.delete(id);
      toast.success('Project deleted successfully');
      loadProjects();
    } catch (error) {
      console.error('Failed to delete project:', error);
      toast.error('Failed to delete project');
    }
  };

  // Filter and paginate
  const filteredProjects = projects.filter(project =>
    project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (project.description && project.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const totalPages = Math.ceil(filteredProjects.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedProjects = filteredProjects.slice(startIndex, startIndex + itemsPerPage);

  if (loading) {
    return <Loading message="Loading projects..." />;
  }

  return (
    <div className="page projects-page">
      <div className="page-header">
        <div>
          <h1>Migration Projects</h1>
          <p className="page-subtitle">Manage your GitLab to GitHub migrations</p>
        </div>
        <Link to="/projects/new" className="btn btn-primary">
          + New Project
        </Link>
      </div>

      <div className="content">
        <div className="filters">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search projects..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="search-input"
            />
          </div>
          
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
              <option value="created">Created</option>
              <option value="configured">Configured</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {filteredProjects.length === 0 ? (
          <div className="empty-state">
            <p>No projects found.</p>
            <p className="hint">
              {searchTerm || statusFilter
                ? 'Try adjusting your filters.'
                : 'Create your first project to get started.'}
            </p>
          </div>
        ) : (
          <>
            <div className="projects-table">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Last Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedProjects.map((project) => (
                    <tr key={project.id}>
                      <td>
                        <Link to={`/projects/${project.id}`} className="project-link">
                          <strong>{project.name}</strong>
                          {project.description && (
                            <span className="project-desc">{project.description}</span>
                          )}
                        </Link>
                      </td>
                      <td>
                        <span className={`status-badge status-${project.status}`}>
                          {project.status}
                        </span>
                      </td>
                      <td>{new Date(project.created_at).toLocaleDateString()}</td>
                      <td>{new Date(project.updated_at).toLocaleDateString()}</td>
                      <td>
                        <div className="action-buttons">
                          <Link
                            to={`/projects/${project.id}`}
                            className="btn btn-sm"
                          >
                            View
                          </Link>
                          <button
                            onClick={() => handleDelete(project.id)}
                            className="btn btn-sm btn-danger"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
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
