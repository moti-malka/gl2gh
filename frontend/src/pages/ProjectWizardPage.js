/**
 * Project Creation Wizard
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectsAPI } from '../services/api';
import { useToast } from '../components/Toast';
import './ProjectWizard.css';

export const ProjectWizardPage = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [projectData, setProjectData] = useState({
    name: '',
    description: '',
    gitlab_url: '',
    gitlab_token: '',
    github_token: '',
    github_org: '',
  });
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const toast = useToast();

  const steps = [
    { id: 1, title: 'Basic Info', desc: 'Project name and description' },
    { id: 2, title: 'GitLab Source', desc: 'Connect to GitLab' },
    { id: 3, title: 'GitHub Target', desc: 'Connect to GitHub' },
    { id: 4, title: 'Review', desc: 'Review and create' },
  ];

  const handleChange = (field, value) => {
    setProjectData(prev => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    setCurrentStep(prev => prev - 1);
  };

  const validateStep = (step) => {
    switch (step) {
      case 1:
        if (!projectData.name.trim()) {
          toast.error('Project name is required');
          return false;
        }
        return true;
      case 2:
        if (!projectData.gitlab_url.trim()) {
          toast.error('GitLab URL is required');
          return false;
        }
        if (!projectData.gitlab_token.trim()) {
          toast.error('GitLab token is required');
          return false;
        }
        return true;
      case 3:
        if (!projectData.github_token.trim()) {
          toast.error('GitHub token is required');
          return false;
        }
        return true;
      default:
        return true;
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const response = await projectsAPI.create({
        name: projectData.name,
        description: projectData.description,
        settings: {
          gitlab: {
            url: projectData.gitlab_url,
            token: projectData.gitlab_token,
          },
          github: {
            token: projectData.github_token,
            org: projectData.github_org,
          },
        },
      });
      
      toast.success('Project created successfully!');
      navigate(`/projects/${response.data.id}`);
    } catch (error) {
      console.error('Failed to create project:', error);
      toast.error(error.response?.data?.detail || 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page project-wizard-page">
      <div className="wizard-container">
        <div className="wizard-header">
          <h1>Create New Project</h1>
          <div className="wizard-steps">
            {steps.map((step) => (
              <div
                key={step.id}
                className={`wizard-step ${currentStep === step.id ? 'active' : ''} ${
                  currentStep > step.id ? 'completed' : ''
                }`}
              >
                <div className="step-number">{step.id}</div>
                <div className="step-info">
                  <div className="step-title">{step.title}</div>
                  <div className="step-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="wizard-content">
          {currentStep === 1 && (
            <div className="wizard-step-content">
              <h2>Basic Information</h2>
              <p className="step-description">
                Enter the basic details for your migration project.
              </p>
              
              <div className="form-group">
                <label htmlFor="name">Project Name *</label>
                <input
                  id="name"
                  type="text"
                  value={projectData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  placeholder="e.g., My Project Migration"
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label htmlFor="description">Description</label>
                <textarea
                  id="description"
                  value={projectData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  placeholder="Optional description of your migration project"
                  rows="4"
                />
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="wizard-step-content">
              <h2>GitLab Source Connection</h2>
              <p className="step-description">
                Configure the connection to your GitLab instance.
              </p>
              
              <div className="form-group">
                <label htmlFor="gitlab_url">GitLab URL *</label>
                <input
                  id="gitlab_url"
                  type="url"
                  value={projectData.gitlab_url}
                  onChange={(e) => handleChange('gitlab_url', e.target.value)}
                  placeholder="https://gitlab.com"
                />
                <span className="form-hint">
                  Enter the full URL of your GitLab instance
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="gitlab_token">Personal Access Token *</label>
                <input
                  id="gitlab_token"
                  type="password"
                  value={projectData.gitlab_token}
                  onChange={(e) => handleChange('gitlab_token', e.target.value)}
                  placeholder="Enter your GitLab PAT"
                />
                <span className="form-hint">
                  Token needs: api, read_repository, read_user scopes
                </span>
              </div>
            </div>
          )}

          {currentStep === 3 && (
            <div className="wizard-step-content">
              <h2>GitHub Target Connection</h2>
              <p className="step-description">
                Configure the connection to your GitHub account.
              </p>
              
              <div className="form-group">
                <label htmlFor="github_token">Personal Access Token *</label>
                <input
                  id="github_token"
                  type="password"
                  value={projectData.github_token}
                  onChange={(e) => handleChange('github_token', e.target.value)}
                  placeholder="Enter your GitHub PAT"
                />
                <span className="form-hint">
                  Token needs: repo, workflow, admin:org scopes
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="github_org">Organization/User (Optional)</label>
                <input
                  id="github_org"
                  type="text"
                  value={projectData.github_org}
                  onChange={(e) => handleChange('github_org', e.target.value)}
                  placeholder="organization-name or username"
                />
                <span className="form-hint">
                  Leave empty to use your personal account
                </span>
              </div>
            </div>
          )}

          {currentStep === 4 && (
            <div className="wizard-step-content">
              <h2>Review & Create</h2>
              <p className="step-description">
                Please review your project configuration before creating.
              </p>
              
              <div className="review-section">
                <h3>Basic Information</h3>
                <div className="review-item">
                  <strong>Project Name:</strong> {projectData.name}
                </div>
                {projectData.description && (
                  <div className="review-item">
                    <strong>Description:</strong> {projectData.description}
                  </div>
                )}
              </div>

              <div className="review-section">
                <h3>GitLab Source</h3>
                <div className="review-item">
                  <strong>URL:</strong> {projectData.gitlab_url}
                </div>
                <div className="review-item">
                  <strong>Token:</strong> ••••••••••••
                </div>
              </div>

              <div className="review-section">
                <h3>GitHub Target</h3>
                <div className="review-item">
                  <strong>Token:</strong> ••••••••••••
                </div>
                {projectData.github_org && (
                  <div className="review-item">
                    <strong>Organization:</strong> {projectData.github_org}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="wizard-actions">
          {currentStep > 1 && (
            <button
              onClick={handleBack}
              className="btn btn-secondary"
              disabled={loading}
            >
              Back
            </button>
          )}
          
          <div style={{ flex: 1 }} />
          
          <button
            onClick={() => navigate('/projects')}
            className="btn btn-secondary"
            disabled={loading}
          >
            Cancel
          </button>
          
          {currentStep < 4 ? (
            <button
              onClick={handleNext}
              className="btn btn-primary"
              disabled={loading}
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              className="btn btn-primary"
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
