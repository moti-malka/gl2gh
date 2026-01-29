/**
 * User Mapping Page
 * Note: This currently uses mock data for demonstration. 
 * In production, this should fetch data from the backend API.
 */
import React, { useState } from 'react';
import { useToast } from '../components/Toast';
import './UserMappingPage.css';

export const UserMappingPage = () => {
  // TODO: Replace with actual API call to fetch user mappings
  // Example: const { data: mappings } = useQuery(['user-mappings', projectId], () => fetchUserMappings(projectId));
  const [mappings, setMappings] = useState([
    {
      id: 1,
      gitlab: { username: 'johndoe', email: 'john@example.com', name: 'John Doe' },
      github: { login: 'johndoe', email: 'john@example.com', name: 'John Doe' },
      confidence: 'high',
      status: 'automatic',
    },
    {
      id: 2,
      gitlab: { username: 'janedoe', email: 'jane@company.com', name: 'Jane Doe' },
      github: null,
      confidence: 'none',
      status: 'unmapped',
    },
    {
      id: 3,
      gitlab: { username: 'bob', email: 'bob@example.com', name: 'Bob Smith' },
      github: { login: 'bobsmith', email: 'bob@github.com', name: 'Bob Smith' },
      confidence: 'medium',
      status: 'automatic',
    },
  ]);
  
  const [selectedMappings, setSelectedMappings] = useState([]);
  const [editingMapping, setEditingMapping] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  const toast = useToast();

  const handleSelectMapping = (id) => {
    setSelectedMappings(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    );
  };

  const handleConfirmMapping = (id) => {
    setMappings(prev =>
      prev.map(m => m.id === id ? { ...m, status: 'confirmed' } : m)
    );
    toast.success('Mapping confirmed');
  };

  const handleEditMapping = (mapping) => {
    setEditingMapping(mapping);
  };

  const handleSaveMapping = (id, githubUser) => {
    setMappings(prev =>
      prev.map(m =>
        m.id === id
          ? { ...m, github: githubUser, status: 'manual', confidence: 'high' }
          : m
      )
    );
    setEditingMapping(null);
    toast.success('Mapping updated');
  };

  const handleConfirmAll = () => {
    const highConfidence = mappings.filter(
      m => m.confidence === 'high' && m.status === 'automatic'
    );
    
    if (highConfidence.length === 0) {
      toast.info('No high-confidence mappings to confirm');
      return;
    }
    
    setMappings(prev =>
      prev.map(m =>
        m.confidence === 'high' && m.status === 'automatic'
          ? { ...m, status: 'confirmed' }
          : m
      )
    );
    
    toast.success(`Confirmed ${highConfidence.length} high-confidence mappings`);
  };

  const handleSkipSelected = () => {
    if (selectedMappings.length === 0) {
      toast.info('No mappings selected');
      return;
    }
    
    setMappings(prev =>
      prev.map(m =>
        selectedMappings.includes(m.id) ? { ...m, status: 'skipped' } : m
      )
    );
    
    setSelectedMappings([]);
    toast.success(`Skipped ${selectedMappings.length} mappings`);
  };

  const getConfidenceColor = (confidence) => {
    switch (confidence) {
      case 'high': return 'green';
      case 'medium': return 'yellow';
      case 'low': return 'orange';
      default: return 'gray';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'confirmed': return '✓';
      case 'automatic': return '◐';
      case 'manual': return '✎';
      case 'skipped': return '○';
      default: return '?';
    }
  };

  return (
    <div className="page user-mapping-page">
      <div className="page-header">
        <div>
          <h1>User Mapping</h1>
          <p className="page-subtitle">
            Map GitLab users to GitHub users for accurate attribution
          </p>
        </div>
      </div>

      <div className="content">
        <div className="mapping-toolbar">
          <div className="toolbar-left">
            <input
              type="text"
              placeholder="Search users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
          </div>
          
          <div className="toolbar-right">
            <button onClick={handleConfirmAll} className="btn btn-sm btn-primary">
              Confirm All High Confidence
            </button>
            <button
              onClick={handleSkipSelected}
              className="btn btn-sm btn-secondary"
              disabled={selectedMappings.length === 0}
            >
              Skip Selected ({selectedMappings.length})
            </button>
          </div>
        </div>

        <div className="mapping-table-container">
          <table className="mapping-table">
            <thead>
              <tr>
                <th width="40px">
                  <input
                    type="checkbox"
                    checked={selectedMappings.length === mappings.length}
                    onChange={(e) =>
                      setSelectedMappings(
                        e.target.checked ? mappings.map(m => m.id) : []
                      )
                    }
                  />
                </th>
                <th>GitLab User</th>
                <th>→</th>
                <th>GitHub User</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {mappings
                .filter(m =>
                  searchQuery === '' ||
                  m.gitlab.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  m.gitlab.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  (m.github?.login || '').toLowerCase().includes(searchQuery.toLowerCase())
                )
                .map((mapping) => (
                  <tr key={mapping.id} className={`mapping-row status-${mapping.status}`}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedMappings.includes(mapping.id)}
                        onChange={() => handleSelectMapping(mapping.id)}
                      />
                    </td>
                    <td>
                      <div className="user-cell">
                        <strong>{mapping.gitlab.username}</strong>
                        <span className="user-email">{mapping.gitlab.email}</span>
                      </div>
                    </td>
                    <td className="arrow-cell">→</td>
                    <td>
                      {mapping.github ? (
                        <div className="user-cell">
                          <strong>{mapping.github.login}</strong>
                          {mapping.github.email && (
                            <span className="user-email">{mapping.github.email}</span>
                          )}
                        </div>
                      ) : (
                        <span className="unmapped">Not mapped</span>
                      )}
                    </td>
                    <td>
                      <span className={`confidence-badge confidence-${getConfidenceColor(mapping.confidence)}`}>
                        {mapping.confidence}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge status-${mapping.status}`}>
                        {getStatusIcon(mapping.status)} {mapping.status}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        {mapping.status === 'automatic' && (
                          <button
                            onClick={() => handleConfirmMapping(mapping.id)}
                            className="btn btn-xs btn-primary"
                          >
                            Confirm
                          </button>
                        )}
                        <button
                          onClick={() => handleEditMapping(mapping)}
                          className="btn btn-xs"
                        >
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {editingMapping && (
          <div className="modal-overlay" onClick={() => setEditingMapping(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>Edit User Mapping</h3>
                <button
                  onClick={() => setEditingMapping(null)}
                  className="modal-close"
                >
                  ×
                </button>
              </div>
              <div className="modal-body">
                <div className="mapping-preview">
                  <div>
                    <strong>GitLab User:</strong>
                    <p>{editingMapping.gitlab.username} ({editingMapping.gitlab.email})</p>
                  </div>
                  <div className="arrow">→</div>
                  <div>
                    <strong>GitHub User:</strong>
                    <input
                      type="text"
                      placeholder="Enter GitHub username"
                      defaultValue={editingMapping.github?.login || ''}
                      className="github-input"
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  onClick={() => setEditingMapping(null)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={() =>
                    handleSaveMapping(editingMapping.id, {
                      login: 'newuser',
                      email: 'newuser@github.com',
                    })
                  }
                  className="btn btn-primary"
                >
                  Save Mapping
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
