/**
 * Loading Component
 */
import React from 'react';
import './Loading.css';

export const Loading = ({ message = 'Loading...', size = 'medium' }) => {
  return (
    <div className={`loading-container loading-${size}`}>
      <div className="spinner"></div>
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};

export const LoadingOverlay = ({ message }) => {
  return (
    <div className="loading-overlay">
      <Loading message={message} size="large" />
    </div>
  );
};
