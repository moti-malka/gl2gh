/**
 * Connection Test Component
 * Tests GitLab/GitHub connection without saving credentials
 */
import React, { useState } from 'react';
import apiClient from '../services/api';
import './ConnectionTest.css';

export const ConnectionTest = ({ type, url, token }) => {
  const [status, setStatus] = useState(null); // null, 'testing', 'success', 'error'
  const [result, setResult] = useState(null);

  const testConnection = async () => {
    setStatus('testing');
    setResult(null);
    
    try {
      const response = await apiClient.post(`/connections/test/${type}`, {
        base_url: url,
        token: token
      });
      
      if (response.data.success) {
        setStatus('success');
        setResult(response.data);
      } else {
        setStatus('error');
        setResult(response.data);
      }
    } catch (error) {
      setStatus('error');
      setResult({
        message: error.response?.data?.message || error.message || 'Connection failed'
      });
    }
  };

  return (
    <div className="connection-test">
      <button 
        className="btn btn-secondary test-button" 
        onClick={testConnection} 
        disabled={!token || status === 'testing'}
      >
        {status === 'testing' ? 'Testing...' : 'Test Connection'}
      </button>
      
      {status === 'success' && result && (
        <div className="test-result test-success">
          <span className="test-icon">✅</span>
          <div className="test-details">
            <div className="test-user">
              Connected as <strong>@{result.user}</strong>
            </div>
            {result.scopes && result.scopes.length > 0 && (
              <div className="test-scopes">
                Scopes: {result.scopes.join(', ')}
              </div>
            )}
          </div>
        </div>
      )}
      
      {status === 'error' && result && (
        <div className="test-result test-error">
          <span className="test-icon">❌</span>
          <div className="test-details">
            <div className="test-message">
              {result.message || 'Connection failed'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
