import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ToastProvider } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { ProfilePage } from './pages/ProfilePage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectWizardPage } from './pages/ProjectWizardPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { RunCreationPage } from './pages/RunCreationPage';
import { RunDashboardPage } from './pages/RunDashboardPage';
import { UserMappingPage } from './pages/UserMappingPage';
import './App.css';

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ToastProvider>
          <Router>
            <AppContent />
          </Router>
        </ToastProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}

function AppContent() {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <div className="App">
      {isAuthenticated && (
        <header className="App-header">
          <nav className="navbar">
            <div className="nav-brand">
              <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
                <h1>gl2gh</h1>
                <span className="tagline">GitLab → GitHub Migration Platform</span>
              </Link>
            </div>
            <div className="nav-links">
              <Link to="/projects">Projects</Link>
              <Link to="/docs">Docs</Link>
              {user && (
                <div className="user-menu">
                  <Link to="/profile" className="user-name">{user.username}</Link>
                  <button onClick={logout} className="btn-link">
                    Logout
                  </button>
                </div>
              )}
            </div>
          </nav>
        </header>
      )}
      
      <main className="main-content">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              isAuthenticated ? (
                <Navigate to="/projects" replace />
              ) : (
                <HomePage />
              )
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects"
            element={
              <ProtectedRoute>
                <ProjectsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/new"
            element={
              <ProtectedRoute requireRole="operator">
                <ProjectWizardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:id"
            element={
              <ProtectedRoute>
                <ProjectDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:projectId/runs/new"
            element={
              <ProtectedRoute requireRole="operator">
                <RunCreationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:projectId/user-mapping"
            element={
              <ProtectedRoute requireRole="operator">
                <UserMappingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/runs/:runId"
            element={
              <ProtectedRoute>
                <RunDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route path="/docs" element={<DocsPage />} />
        </Routes>
      </main>
      
      <footer className="App-footer">
        <p>gl2gh Migration Platform v0.1.0</p>
      </footer>
    </div>
  );
}

function HomePage() {
  return (
    <div className="page home-page">
      <div className="hero">
        <h1>Welcome to gl2gh</h1>
        <p className="subtitle">
          Agentic Migration Platform for GitLab → GitHub
        </p>
        <div className="features">
          <div className="feature-card">
            <h3>🔍 Discovery</h3>
            <p>Scan GitLab groups and assess migration readiness</p>
          </div>
          <div className="feature-card">
            <h3>🔄 Transform</h3>
            <p>Convert GitLab CI to GitHub Actions</p>
          </div>
          <div className="feature-card">
            <h3>✅ Verify</h3>
            <p>Validate migration success</p>
          </div>
        </div>
        <div className="cta">
          <Link to="/projects" className="btn btn-primary">
            Get Started
          </Link>
        </div>
      </div>
    </div>
  );
}



function DocsPage() {
  return (
    <div className="page docs-page">
      <h1>Documentation</h1>
      <div className="docs-content">
        <section>
          <h2>Getting Started</h2>
          <p>
            The gl2gh platform helps you migrate from GitLab to GitHub with
            an intelligent, agent-based approach.
          </p>
        </section>
        <section>
          <h2>Migration Stages</h2>
          <ul>
            <li><strong>Discover:</strong> Scan GitLab groups and projects</li>
            <li><strong>Export:</strong> Extract repository and CI configuration</li>
            <li><strong>Transform:</strong> Convert GitLab CI to GitHub Actions</li>
            <li><strong>Plan:</strong> Generate migration execution plan</li>
            <li><strong>Apply:</strong> Execute migration to GitHub</li>
            <li><strong>Verify:</strong> Validate migration results</li>
          </ul>
        </section>
      </div>
    </div>
  );
}

export default App;
