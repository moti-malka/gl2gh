/**
 * Checkpoint Panel Component
 * Displays checkpoint information and recovery options for failed runs
 */
import React from 'react';
import './CheckpointPanel.css';

export const CheckpointPanel = ({ runId, checkpoint, onResume, onStartFresh }) => {
  if (!checkpoint || !checkpoint.has_checkpoint) {
    return null;
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const getComponentStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'failed':
        return '✕';
      case 'in_progress':
        return '⋯';
      default:
        return '○';
    }
  };

  const getComponentStatusClass = (status) => {
    switch (status) {
      case 'completed':
        return 'completed';
      case 'failed':
        return 'failed';
      case 'in_progress':
        return 'in-progress';
      default:
        return 'pending';
    }
  };

  const components = checkpoint.components || {};
  const componentsList = Object.entries(components);

  return (
    <div className="checkpoint-panel">
      <div className="checkpoint-header">
        <h3>🔄 Recovery Options Available</h3>
        <p className="checkpoint-info">
          This run was interrupted. You can resume from where it left off or start fresh.
        </p>
      </div>

      <div className="checkpoint-details">
        <div className="checkpoint-meta">
          <div className="meta-item">
            <span className="meta-label">Started:</span>
            <span className="meta-value">{formatDate(checkpoint.started_at)}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Last Updated:</span>
            <span className="meta-value">{formatDate(checkpoint.updated_at)}</span>
          </div>
          {checkpoint.resume_from && (
            <div className="meta-item">
              <span className="meta-label">Resume From:</span>
              <span className="meta-value highlight">{checkpoint.resume_from}</span>
            </div>
          )}
        </div>

        <div className="checkpoint-components">
          <h4>Component Progress</h4>
          <ul className="components-list">
            {componentsList.map(([name, data]) => (
              <li key={name} className={`component-item ${getComponentStatusClass(data.status)}`}>
                <span className="component-icon">
                  {getComponentStatusIcon(data.status)}
                </span>
                <span className="component-name">{name}</span>
                <span className="component-status">
                  {data.status}
                  {data.processed_items !== undefined && data.total_items !== undefined && (
                    <span className="component-progress">
                      {' '}({data.processed_items}/{data.total_items})
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {checkpoint.errors && checkpoint.errors.length > 0 && (
          <div className="checkpoint-errors">
            <h4>Errors</h4>
            <ul className="errors-list">
              {checkpoint.errors.slice(0, 3).map((error, index) => (
                <li key={index} className="error-item">
                  <span className="error-component">{error.component}:</span>
                  <span className="error-message">{error.message}</span>
                </li>
              ))}
              {checkpoint.errors.length > 3 && (
                <li className="error-more">
                  ...and {checkpoint.errors.length - 3} more errors
                </li>
              )}
            </ul>
          </div>
        )}
      </div>

      <div className="checkpoint-actions">
        {checkpoint.resumable && (
          <button 
            onClick={onResume} 
            className="btn btn-primary resume-btn"
            title="Continue from where the run left off"
          >
            🔄 Resume from Checkpoint
          </button>
        )}
        <button 
          onClick={onStartFresh} 
          className="btn btn-secondary start-fresh-btn"
          title="Clear checkpoint and restart from beginning"
        >
          🔁 Start Fresh
        </button>
      </div>
    </div>
  );
};
