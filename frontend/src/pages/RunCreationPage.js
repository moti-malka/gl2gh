/**
 * Run Creation Page
 */
import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { runsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import './RunCreationPage.css';

export const RunCreationPage = () => {
  const { projectId } = useParams();
  const [mode, setMode] = useState('PLAN_ONLY');
  const [components, setComponents] = useState({
    discovery: true,
    export: true,
    transform: true,
    plan: true,
    apply: false,
    verify: false,
  });
  const [concurrency, setConcurrency] = useState(4);
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const toast = useToast();

  const handleComponentToggle = (component) => {
    setComponents(prev => ({ ...prev, [component]: !prev[component] }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const selectedComponents = Object.entries(components)
      .filter(([_, enabled]) => enabled)
      .map(([name, _]) => name);
    
    if (selectedComponents.length === 0) {
      toast.error('Please select at least one component');
      return;
    }

    setLoading(true);
    try {
      const response = await runsAPI.create(projectId, {
        mode,
        components: selectedComponents,
        config: {
          concurrency,
        },
      });
      
      toast.success('Run created successfully!');
      navigate(`/runs/${response.data.id}`);
    } catch (error) {
      console.error('Failed to create run:', error);
      toast.error(error.response?.data?.detail || 'Failed to create run');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page run-creation-page">
      <div className="page-header">
        <h1>Start New Migration Run</h1>
        <p className="page-subtitle">Configure and start a new migration run</p>
      </div>

      <form onSubmit={handleSubmit} className="run-form">
        <div className="form-section">
          <h2>Migration Mode</h2>
          <p className="section-description">
            Choose how to run the migration: plan only, preview changes, or execute.
          </p>
          
          <div className="mode-selector">
            <label className={`mode-option ${mode === 'PLAN_ONLY' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="mode"
                value="PLAN_ONLY"
                checked={mode === 'PLAN_ONLY'}
                onChange={(e) => setMode(e.target.value)}
              />
              <div className="mode-content">
                <strong>Plan Only</strong>
                <p>Generate migration plan without executing (recommended first)</p>
              </div>
            </label>
            
            <label className={`mode-option ${mode === 'DRY_RUN' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="mode"
                value="DRY_RUN"
                checked={mode === 'DRY_RUN'}
                onChange={(e) => setMode(e.target.value)}
              />
              <div className="mode-content">
                <strong>Dry Run</strong>
                <p>Simulate execution and show what would happen (no changes made)</p>
              </div>
            </label>
            
            <label className={`mode-option ${mode === 'EXECUTE' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="mode"
                value="EXECUTE"
                checked={mode === 'EXECUTE'}
                onChange={(e) => setMode(e.target.value)}
              />
              <div className="mode-content">
                <strong>Execute</strong>
                <p>Execute the full migration to GitHub</p>
              </div>
            </label>
          </div>
        </div>

        <div className="form-section">
          <h2>Components</h2>
          <p className="section-description">
            Select which migration components to run.
          </p>
          
          <div className="component-list">
            <label className="component-checkbox">
              <input
                type="checkbox"
                checked={components.discovery}
                onChange={() => handleComponentToggle('discovery')}
              />
              <div className="component-info">
                <strong>Discovery</strong>
                <p>Scan GitLab projects and analyze migration readiness</p>
              </div>
            </label>
            
            <label className="component-checkbox">
              <input
                type="checkbox"
                checked={components.export}
                onChange={() => handleComponentToggle('export')}
              />
              <div className="component-info">
                <strong>Export</strong>
                <p>Extract repository data and CI configurations</p>
              </div>
            </label>
            
            <label className="component-checkbox">
              <input
                type="checkbox"
                checked={components.transform}
                onChange={() => handleComponentToggle('transform')}
              />
              <div className="component-info">
                <strong>Transform</strong>
                <p>Convert GitLab CI to GitHub Actions</p>
              </div>
            </label>
            
            <label className="component-checkbox">
              <input
                type="checkbox"
                checked={components.plan}
                onChange={() => handleComponentToggle('plan')}
              />
              <div className="component-info">
                <strong>Plan</strong>
                <p>Generate detailed migration execution plan</p>
              </div>
            </label>
            
            <label className="component-checkbox">
              <input
                type="checkbox"
                checked={components.apply}
                onChange={() => handleComponentToggle('apply')}
                disabled={mode === 'PLAN_ONLY'}
              />
              <div className="component-info">
                <strong>Apply</strong>
                <p>Execute migration to GitHub (requires DRY_RUN or EXECUTE mode)</p>
              </div>
            </label>
            
            <label className="component-checkbox">
              <input
                type="checkbox"
                checked={components.verify}
                onChange={() => handleComponentToggle('verify')}
                disabled={mode === 'PLAN_ONLY' || mode === 'DRY_RUN'}
              />
              <div className="component-info">
                <strong>Verify</strong>
                <p>Validate migration results (requires EXECUTE mode)</p>
              </div>
            </label>
          </div>
        </div>

        <div className="form-section">
          <h2>Advanced Options</h2>
          
          <div className="form-group">
            <label htmlFor="concurrency">
              Concurrency Level: {concurrency}
            </label>
            <input
              id="concurrency"
              type="range"
              min="1"
              max="10"
              value={concurrency}
              onChange={(e) => setConcurrency(parseInt(e.target.value))}
            />
            <p className="form-hint">
              Number of parallel operations (higher = faster but more resource intensive)
            </p>
          </div>
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={() => navigate(`/projects/${projectId}`)}
            className="btn btn-secondary"
            disabled={loading}
          >
            Cancel
          </button>
          
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Creating Run...' : 'Start Run'}
          </button>
        </div>
      </form>
    </div>
  );
};
