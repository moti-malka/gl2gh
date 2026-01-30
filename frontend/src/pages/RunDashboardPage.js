/**
 * Run Dashboard Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { runsAPI, eventsAPI } from '../services/api';
import { progressService } from '../services/progress';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './RunDashboardPage.css';

export const RunDashboardPage = () => {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connectionMethod, setConnectionMethod] = useState(null);
  const toast = useToast();

  const loadRunData = useCallback(async () => {
    setLoading(true);
    try {
      const [runResponse, eventsResponse] = await Promise.all([
        runsAPI.get(runId),
        eventsAPI.list(runId, { limit: 100 }),
      ]);
      
      setRun(runResponse.data);
      setEvents(eventsResponse.data);
    } catch (error) {
      console.error('Failed to load run:', error);
      toast.error('Failed to load run details');
    } finally {
      setLoading(false);
    }
  }, [runId, toast]);

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

  const getProgressPercentage = () => {
    if (!run) return 0;
    
    const total = run.components?.length || 1;
    const completed = events.filter(e => e.type === 'component_completed').length;
    
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

      <div className="run-overview">
        <div className="overview-card">
          <h3>Status</h3>
          <span className={`status-badge status-${run.status}`}>
            {run.status}
          </span>
        </div>
        
        <div className="overview-card">
          <h3>Mode</h3>
          <p>{run.mode}</p>
        </div>
        
        <div className="overview-card">
          <h3>Progress</h3>
          <p>{getProgressPercentage()}%</p>
        </div>
        
        <div className="overview-card">
          <h3>Elapsed Time</h3>
          <p>{getElapsedTime()}</p>
        </div>
      </div>

      <div className="progress-section">
        <h2>Overall Progress</h2>
        <div className="progress-bar-container">
          <div className="progress-bar" style={{ width: `${getProgressPercentage()}%` }}>
            <span className="progress-text">{getProgressPercentage()}%</span>
          </div>
        </div>
      </div>

      <div className="components-section">
        <h2>Components</h2>
        <div className="components-grid">
          {run.components?.map((component) => {
            const componentEvents = events.filter(e => 
              e.component === component || e.message?.includes(component)
            );
            const isCompleted = componentEvents.some(e => e.type === 'component_completed');
            const isFailed = componentEvents.some(e => e.type === 'error');
            const isRunning = componentEvents.some(e => e.type === 'component_started') && !isCompleted && !isFailed;
            
            return (
              <div key={component} className={`component-card ${isCompleted ? 'completed' : ''} ${isFailed ? 'failed' : ''} ${isRunning ? 'running' : ''}`}>
                <div className="component-icon">
                  {isCompleted && '✓'}
                  {isFailed && '✕'}
                  {isRunning && '⋯'}
                  {!isCompleted && !isFailed && !isRunning && '○'}
                </div>
                <div className="component-name">{component}</div>
                <div className="component-status">
                  {isCompleted && 'Completed'}
                  {isFailed && 'Failed'}
                  {isRunning && 'Running'}
                  {!isCompleted && !isFailed && !isRunning && 'Pending'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="events-section">
        <h2>Event Log</h2>
        <div className="events-log">
          {events.length === 0 ? (
            <div className="empty-state">
              <p>No events yet.</p>
            </div>
          ) : (
            events.map((event, index) => (
              <div key={index} className={`event-item event-${event.type}`}>
                <span className="event-time">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <span className={`event-type ${event.type}`}>
                  {event.type}
                </span>
                <span className="event-message">{event.message}</span>
              </div>
            ))
          )}
        </div>
      </div>

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
