/**
 * Run Dashboard Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { runsAPI, eventsAPI } from '../services/api';
import { progressService } from '../services/progress';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import { ProjectSelectionPanel } from '../components/ProjectSelectionPanel';
import { CheckpointPanel } from '../components/CheckpointPanel';
import { ComponentInventory } from '../components/ComponentInventory';
import { ComponentSelector } from '../components/ComponentSelector';
import './RunDashboardPage.css';

// Helper functions for action display
const getActionIcon = (actionType) => {
  const icons = {
    'repo_create': '📦',
    'repo_push': '⬆️',
    'issue_create': '📋',
    'issue_migrate': '📋',
    'mr_create': '🔀',
    'mr_migrate': '🔀',
    'pr_create': '🔀',
    'wiki_migrate': '📖',
    'wiki_create': '📖',
    'release_create': '🏷️',
    'label_create': '🏷️',
    'milestone_create': '🎯',
    'branch_protect': '🛡️',
    'webhook_create': '🔗',
    'ci_migrate': '⚙️',
    'workflow_create': '⚙️',
    'user_map': '👤',
    'settings_apply': '⚙️'
  };
  return icons[actionType] || '▶️';
};

const formatActionType = (actionType) => {
  const labels = {
    'repo_create': 'Create Repository',
    'repo_push': 'Push Code',
    'issue_create': 'Create Issues',
    'issue_migrate': 'Migrate Issues',
    'mr_create': 'Create Pull Requests',
    'mr_migrate': 'Migrate Merge Requests',
    'pr_create': 'Create Pull Requests',
    'wiki_migrate': 'Migrate Wiki',
    'wiki_create': 'Create Wiki Pages',
    'release_create': 'Create Releases',
    'label_create': 'Create Labels',
    'milestone_create': 'Create Milestones',
    'branch_protect': 'Protect Branches',
    'webhook_create': 'Create Webhooks',
    'ci_migrate': 'Migrate CI/CD',
    'workflow_create': 'Create Workflows',
    'user_map': 'Map Users',
    'settings_apply': 'Apply Settings'
  };
  return labels[actionType] || actionType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

export const RunDashboardPage = () => {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [events, setEvents] = useState([]);
  const [checkpoint, setCheckpoint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showProjectSelection, setShowProjectSelection] = useState(false);
  const [discoveredProjects, setDiscoveredProjects] = useState([]);
  const [loadingDiscovery, setLoadingDiscovery] = useState(false);
  const [discoveryLoadAttempted, setDiscoveryLoadAttempted] = useState(false);
  const [connectionMethod, setConnectionMethod] = useState(null);
  const [summary, setSummary] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  
  // Component inventory and selection
  const [inventory, setInventory] = useState(null);
  const [showComponentSelector, setShowComponentSelector] = useState(false);
  const [componentSelection, setComponentSelection] = useState(null);
  const [loadingInventory, setLoadingInventory] = useState(false);
  
  const toast = useToast();

  const loadDiscoveryResults = useCallback(async () => {
    if (loadingDiscovery || discoveryLoadAttempted) return; // Prevent multiple loads
    setLoadingDiscovery(true);
    setDiscoveryLoadAttempted(true);
    try {
      const response = await runsAPI.getDiscoveryResults(runId);
      setDiscoveredProjects(response.data.projects || []);
      setShowProjectSelection(true);
    } catch (error) {
      // Silently handle errors - discovery may not be ready yet or have no artifacts
      // Don't retry - we already attempted once
      console.debug('Discovery results not available:', error.response?.status);
    } finally {
      setLoadingDiscovery(false);
    }
  }, [runId, loadingDiscovery, discoveryLoadAttempted]);

  const loadRunData = useCallback(async () => {
    setLoading(true);
    try {
      const [runResponse, eventsResponse] = await Promise.all([
        runsAPI.get(runId),
        eventsAPI.list(runId, { limit: 100 }),
      ]);
      
      setRun(runResponse.data);
      setEvents(eventsResponse.data);
      
      // Load summary and artifacts if run is completed
      if (['COMPLETED', 'success'].includes(runResponse.data.status)) {
        try {
          const [summaryResponse, artifactsResponse] = await Promise.all([
            runsAPI.getSummary(runId).catch(() => ({ data: null })),
            runsAPI.getArtifacts(runId).catch(() => ({ data: [] })),
          ]);
          setSummary(summaryResponse.data);
          setArtifacts(artifactsResponse.data || []);
        } catch (err) {
          console.debug('Could not load summary/artifacts:', err);
        }
      }
      
      // Don't try to load discovery results during polling - it's handled separately
      
      // Load checkpoint if run is failed or canceled
      if (['FAILED', 'CANCELED'].includes(runResponse.data.status)) {
        try {
          const checkpointResponse = await runsAPI.getCheckpoint(runId);
          setCheckpoint(checkpointResponse.data);
        } catch (error) {
          console.log('No checkpoint available:', error);
          setCheckpoint(null);
        }
      }
    } catch (error) {
      console.error('Failed to load run:', error);
      toast.error('Failed to load run details');
    } finally {
      setLoading(false);
    }
  }, [runId, toast]);

  const loadInventory = useCallback(async () => {
    if (loadingInventory) return;
    setLoadingInventory(true);
    try {
      const response = await runsAPI.getInventory(runId);
      setInventory(response.data);
    } catch (error) {
      console.debug('Inventory not available:', error.response?.status);
    } finally {
      setLoadingInventory(false);
    }
  }, [runId, loadingInventory]);

  const loadComponentSelection = useCallback(async () => {
    try {
      const response = await runsAPI.getComponentSelection(runId);
      setComponentSelection(response.data);
    } catch (error) {
      console.debug('Component selection not available:', error.response?.status);
    }
  }, [runId]);

  const handleComponentSelectionChange = (newSelection) => {
    setComponentSelection(newSelection);
  };

  const handleSaveComponentSelection = async () => {
    try {
      await runsAPI.saveComponentSelection(runId, componentSelection);
      toast.success('Component selection saved');
      setShowComponentSelector(false);
      // Continue to plan generation or next step
      await loadRunData();
    } catch (error) {
      console.error('Failed to save component selection:', error);
      toast.error('Failed to save component selection');
    }
  };

  const handleProjectSelectionContinue = async (selections) => {
    try {
      await runsAPI.saveProjectSelection(runId, selections);
      toast.success('Project selection saved');
      setShowProjectSelection(false);
      // Reload run data to update UI
      await loadRunData();
    } catch (error) {
      console.error('Failed to save project selection:', error);
      toast.error('Failed to save project selection');
    }
  };

  const handleProjectSelectionBack = () => {
    setShowProjectSelection(false);
  };

  useEffect(() => {
    loadRunData();
    
    // Subscribe to real-time updates with automatic fallback
    const unsubscribe = progressService.subscribeToRun(runId, (data) => {
      setRun(prev => ({ ...prev, ...data }));
      
      // Add new event if included
      if (data.event) {
        setEvents(prev => [data.event, ...prev]);
      }
      
      // Update connection method indicator
      setConnectionMethod(progressService.getConnectionMethod());
    });

    return () => {
      unsubscribe();
    };
  }, [runId, loadRunData]);

  // Load inventory after discovery completes
  useEffect(() => {
    if (run && run.stage && ['EXPORT', 'TRANSFORM', 'PLAN', 'APPLY', 'VERIFY', 'DONE'].includes(run.stage)) {
      // Discovery has completed, load inventory
      if (!inventory && !loadingInventory) {
        loadInventory();
        loadComponentSelection();
      }
    }
  }, [run, inventory, loadingInventory, loadInventory, loadComponentSelection]);

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel this run?')) {
      return;
    }

    try {
      await runsAPI.cancel(runId);
      toast.success('Run cancelled');
      await loadRunData();
    } catch (error) {
      console.error('Failed to cancel run:', error);
      toast.error('Failed to cancel run');
    }
  };

  const handleResume = async () => {
    try {
      await runsAPI.resume(runId);
      toast.success('Run resumed successfully');
      await loadRunData();
    } catch (error) {
      console.error('Failed to resume run:', error);
      toast.error('Failed to resume run');
    }
  };

  const handleStartFresh = async () => {
    if (!window.confirm('Are you sure you want to clear the checkpoint and start fresh? This cannot be undone.')) {
      return;
    }

    try {
      await runsAPI.clearCheckpoint(runId);
      toast.success('Checkpoint cleared');
      await loadRunData();
    } catch (error) {
      console.error('Failed to clear checkpoint:', error);
      toast.error('Failed to clear checkpoint');
    }
  };

  const handleNextStep = async (action) => {
    switch (action) {
      case 'apply':
        if (!window.confirm('Are you sure you want to apply the migration plan? This will create/modify resources on GitHub.')) {
          return;
        }
        try {
          await runsAPI.apply(runId);
          toast.success('Migration apply started');
          await loadRunData();
        } catch (error) {
          console.error('Failed to start apply:', error);
          toast.error('Failed to start migration apply');
        }
        break;
      case 'review_plan':
      case 'download_plan':
        // Navigate to plan view or download
        window.open(`/api/runs/${runId}/plan`, '_blank');
        break;
      case 'review_discovery':
        setShowProjectSelection(true);
        break;
      case 'resume':
        await handleResume();
        break;
      case 'view_errors':
        // Scroll to events section
        document.querySelector('.events-section')?.scrollIntoView({ behavior: 'smooth' });
        break;
      default:
        toast.info(`Action "${action}" not implemented yet`);
    }
  };

  const getProgressPercentage = () => {
    if (!run) return 0;
    
    // If run is completed, show 100%
    if (run.status === 'COMPLETED' || run.status === 'success') {
      return 100;
    }
    
    // First check if run has a progress_percent field from backend
    if (run.progress_percent !== undefined && run.progress_percent !== null) {
      return run.progress_percent;
    }
    
    // Legacy: check for progress as int
    if (typeof run.progress === 'number') {
      return run.progress;
    }
    
    // Fallback: Calculate from events
    const total = run.components?.length || 1;
    const completed = events.filter(e => 
      e.type === 'component_completed' || 
      (e.payload && e.payload.type === 'component_completed')
    ).length;
    
    return Math.round((completed / total) * 100);
  };

  const getElapsedTime = () => {
    if (!run?.started_at) return '0s';
    
    const start = new Date(run.started_at);
    const end = run.completed_at ? new Date(run.completed_at) : new Date();
    const seconds = Math.floor((end - start) / 1000);
    
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  if (loading) {
    return <Loading message="Loading run..." />;
  }

  if (!run) {
    return null;
  }

  const isRunning = ['pending', 'running'].includes(run.status);

  return (
    <div className="page run-dashboard-page">
      <div className="page-header">
        <div>
          <div className="breadcrumb">
            <Link to="/projects">Projects</Link>
            <span className="separator">›</span>
            <Link to={`/projects/${run.project_id}`}>Project</Link>
            <span className="separator">›</span>
            <span>Run #{runId.slice(-6)}</span>
          </div>
          <h1>Migration Run Dashboard</h1>
        </div>
        <div className="header-actions">
          {connectionMethod && (
            <span className={`connection-indicator connection-${connectionMethod}`} title={`Connected via ${connectionMethod.toUpperCase()}`}>
              {connectionMethod === 'websocket' && '🔗 WebSocket'}
              {connectionMethod === 'sse' && '📡 SSE'}
              {connectionMethod === 'polling' && '🔄 Polling'}
            </span>
          )}
          {isRunning && (
            <button onClick={handleCancel} className="btn btn-danger">
              Cancel Run
            </button>
          )}
        </div>
      </div>

      {/* Show Project Selection Panel if discovery completed and selection not made */}
      {showProjectSelection && discoveredProjects.length > 0 && (
        <ProjectSelectionPanel
          runId={runId}
          discoveredProjects={discoveredProjects}
          onContinue={handleProjectSelectionContinue}
          onBack={handleProjectSelectionBack}
        />
      )}

      {loadingDiscovery && (
        <div className="loading-discovery">
          <Loading message="Loading discovery results..." />
        </div>
      )}

      {/* Show Component Inventory after discovery completes */}
      {inventory && run && run.stage && !['DISCOVER', 'CREATED', 'QUEUED'].includes(run.stage) && (
        <ComponentInventory inventory={inventory} />
      )}

      {/* Show Component Selector before plan generation */}
      {showComponentSelector && inventory && (
        <div className="component-selector-panel">
          <ComponentSelector
            inventory={inventory}
            initialSelection={componentSelection}
            onSelectionChange={handleComponentSelectionChange}
          />
          <div className="selector-actions">
            <button 
              className="btn btn-secondary" 
              onClick={() => setShowComponentSelector(false)}
            >
              Cancel
            </button>
            <button 
              className="btn btn-primary" 
              onClick={handleSaveComponentSelection}
            >
              Save & Continue to Plan
            </button>
          </div>
        </div>
      )}

      {/* Button to open component selector if inventory available and not in progress */}
      {inventory && !showComponentSelector && run && ['COMPLETED', 'FAILED'].includes(run.status) && run.stage === 'DISCOVER' && (
        <div className="configure-migration-section">
          <button 
            className="btn btn-primary btn-large" 
            onClick={() => setShowComponentSelector(true)}
          >
            🎯 Configure Migration Components
          </button>
          <p className="configure-hint">
            Select which components you want to migrate before proceeding
          </p>
        </div>
      )}

      {/* Compact Status Bar */}
      <div className="status-bar">
        <div className="status-item">
          <span className="status-label">Status</span>
          <span className={`status-value status-${run.status}`}>{run.status}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Mode</span>
          <span className="status-value">{run.mode}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Progress</span>
          <div className="mini-progress">
            <div className="mini-progress-bar" style={{ width: `${getProgressPercentage()}%` }}></div>
            <span className="mini-progress-text">{getProgressPercentage()}%</span>
          </div>
        </div>
        <div className="status-item">
          <span className="status-label">Time</span>
          <span className="status-value">{getElapsedTime()}</span>
        </div>
        {/* Inline Stage Progress */}
        <div className="stages-inline">
          {(() => {
            const modeStages = {
              'DISCOVER_ONLY': ['DISCOVER'],
              'PLAN_ONLY': ['DISCOVER', 'EXPORT', 'TRANSFORM', 'PLAN'],
              'APPLY': ['DISCOVER', 'EXPORT', 'TRANSFORM', 'PLAN', 'APPLY'],
              'FULL': ['DISCOVER', 'EXPORT', 'TRANSFORM', 'PLAN', 'APPLY', 'VERIFY'],
            };
            const stages = run.components?.length > 0 
              ? run.components 
              : (modeStages[run.mode] || modeStages['PLAN_ONLY']);
            const isRunCompleted = run.status === 'COMPLETED' || run.status === 'success';
            const currentStage = run.stage?.toUpperCase();
            const stageIndex = stages.findIndex(s => s.toUpperCase() === currentStage);
            
            return stages.map((stage, idx) => {
              const isCompleted = isRunCompleted || idx < stageIndex;
              const isCurrent = !isRunCompleted && currentStage === stage.toUpperCase();
              const isFailed = run.status === 'FAILED' && isCurrent;
              return (
                <div key={stage} className={`stage-dot ${isCompleted ? 'completed' : ''} ${isCurrent ? 'current' : ''} ${isFailed ? 'failed' : ''}`} title={stage}>
                  {isCompleted ? '✓' : isFailed ? '✕' : isCurrent ? '●' : '○'}
                  <span className="stage-name">{stage.slice(0, 3)}</span>
                </div>
              );
            });
          })()}
        </div>
      </div>

      {/* Summary Section - Shows plan and gaps (inventory is shown separately above) */}
      {summary && run.status === 'COMPLETED' && (
        <div className="summary-section">
          <h2>📋 Migration Plan Summary</h2>
          
          {/* Plan Summary */}
          {summary.plan && (
            <div className="summary-card">
              <p className="summary-stat">Generated <strong>{summary.plan.total_actions}</strong> action(s) for migration</p>
              {summary.plan.actions_by_type && Object.keys(summary.plan.actions_by_type).length > 0 && (
                <div className="action-types-grid">
                  {Object.entries(summary.plan.actions_by_type).map(([type, count]) => (
                    <div key={type} className="action-type-card">
                      <span className="action-icon">{getActionIcon(type)}</span>
                      <span className="action-name">{formatActionType(type)}</span>
                      <span className="action-count">{count}</span>
                    </div>
                  ))}
                </div>
              )}
              {summary.plan.preview && summary.plan.preview.length > 0 && (
                <div className="plan-preview">
                  <h4>Actions Preview:</h4>
                  <div className="actions-list">
                    {summary.plan.preview.map((action, i) => (
                      <div key={i} className="action-item">
                        <span className="action-type-icon">{getActionIcon(action.type)}</span>
                        <div className="action-details">
                          <strong>{formatActionType(action.type)}</strong>
                          <span className="action-description">{action.description || action.target}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {summary.plan.total_actions > 5 && (
                    <p className="more-hint">... and {summary.plan.total_actions - 5} more actions</p>
                  )}
                </div>
              )}
            </div>
          )}
          
          {/* Gaps Warning */}
          {summary.gaps && summary.gaps.total > 0 && (
            <div className="summary-card warning">
              <h3>⚠️ Conversion Gaps</h3>
              <p>Found <strong>{summary.gaps.total}</strong> feature(s) that cannot be directly migrated.</p>
              {summary.gaps.preview && summary.gaps.preview.length > 0 && (
                <ul className="gaps-list">
                  {summary.gaps.preview.map((gap, i) => (
                    <li key={i}>{gap.feature || gap.description || gap.type}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          
          {/* Quick Actions */}
          <div className="quick-actions">
            <button className="quick-action-btn primary" onClick={() => handleNextStep('apply')}>
              ▶️ Apply Migration
            </button>
            <button className="quick-action-btn" onClick={() => handleNextStep('review_plan')}>
              📄 Review Plan
            </button>
          </div>
        </div>
      )}

      {/* Show checkpoint panel for failed/canceled runs */}
      {['FAILED', 'CANCELED'].includes(run.status) && checkpoint && checkpoint.has_checkpoint && (
        <CheckpointPanel
          checkpoint={checkpoint}
          onResume={handleResume}
          onStartFresh={handleStartFresh}
        />
      )}

      <div className="events-section">
        <h2>Event Log</h2>
        <div className="events-log">
          {events.length === 0 ? (
            <div className="empty-state">
              <p>No events yet.</p>
            </div>
          ) : (
            events.map((event, index) => {
              const isError = event.type === 'error';
              const errorDetails = event.error_details || event.payload?.error_details;
              
              return (
                <div key={index} className={`event-item event-${event.type}`}>
                  <div>
                    <span className="event-time">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </span>
                    <span className={`event-type ${event.type}`}>
                      {event.type}
                    </span>
                    <span className="event-message">{event.message}</span>
                  </div>
                  
                  {isError && errorDetails && (
                    <div className="error-details">
                      {errorDetails.code && (
                        <div className="error-code">
                          <strong>Error Code:</strong> {errorDetails.code}
                        </div>
                      )}
                      {errorDetails.suggestion && (
                        <div className="error-suggestion">
                          <strong>💡 Suggestion:</strong> {errorDetails.suggestion}
                        </div>
                      )}
                      {errorDetails.retry_after && (
                        <div className="error-retry">
                          <strong>⏰ Retry After:</strong>{' '}
                          {new Date(errorDetails.retry_after).toLocaleString()}
                        </div>
                      )}
                      {errorDetails.technical && (
                        <details className="error-technical">
                          <summary>Technical Details</summary>
                          <pre>{errorDetails.technical}</pre>
                        </details>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {run.status === 'failed' && run.error_details && (
        <div className="error-summary-section">
          <h2>⚠️ Error Summary</h2>
          <div className="error-summary-card">
            <div className="error-category">
              <strong>Category:</strong> {run.error_details.category || 'Unknown'}
            </div>
            <div className="error-message">
              <strong>Message:</strong> {run.error_details.message || run.error}
            </div>
            {run.error_details.suggestion && (
              <div className="error-suggestion-box">
                <h3>💡 How to fix:</h3>
                <p>{run.error_details.suggestion}</p>
              </div>
            )}
            {run.error_details.retry_after && (
              <div className="error-retry-info">
                <strong>⏰ You can retry after:</strong>{' '}
                {new Date(run.error_details.retry_after).toLocaleString()}
              </div>
            )}
            {run.error_details.technical && (
              <details className="error-technical-details">
                <summary>View Technical Details</summary>
                <pre>{run.error_details.technical}</pre>
              </details>
            )}
          </div>
        </div>
      )}

      {run.status === 'completed' && (
        <div className="artifacts-section">
          <h2>Artifacts</h2>
          <div className="artifacts-list">
            <Link to={`/runs/${runId}/artifacts/plan.json`} className="artifact-link">
              📄 Migration Plan
            </Link>
            <Link to={`/runs/${runId}/artifacts/gaps.json`} className="artifact-link">
              ⚠ Conversion Gaps
            </Link>
            <Link to={`/runs/${runId}/artifacts/verification.json`} className="artifact-link">
              ✓ Verification Report
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
