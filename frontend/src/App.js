import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <header className="App-header">
          <nav className="navbar">
            <div className="nav-brand">
              <h1>gl2gh</h1>
              <span className="tagline">GitLab → GitHub Migration Platform</span>
            </div>
            <div className="nav-links">
              <Link to="/">Home</Link>
              <Link to="/projects">Projects</Link>
              <Link to="/docs">Docs</Link>
            </div>
          </nav>
        </header>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/docs" element={<DocsPage />} />
          </Routes>
        </main>
        
        <footer className="App-footer">
          <p>gl2gh Migration Platform v0.1.0</p>
        </footer>
      </div>
    </Router>
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

function ProjectsPage() {
  return (
    <div className="page projects-page">
      <div className="page-header">
        <h1>Migration Projects</h1>
        <button className="btn btn-primary">+ New Project</button>
      </div>
      <div className="content">
        <div className="empty-state">
          <p>No migration projects yet.</p>
          <p className="hint">Create your first project to get started.</p>
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
