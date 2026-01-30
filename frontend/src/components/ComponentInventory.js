/**
 * ComponentInventory - Display detailed component inventory from discovery
 */
import React from 'react';
import './ComponentInventory.css';

export const ComponentInventory = ({ inventory }) => {
  if (!inventory) {
    return (
      <div className="component-inventory-empty">
        <p>No inventory data available</p>
      </div>
    );
  }

  const renderComponentCard = (title, icon, data, isAvailable) => {
    return (
      <div className={`component-card ${!isAvailable ? 'unavailable' : ''}`}>
        <div className="component-card-header">
          <span className="component-icon">{icon}</span>
          <h3>{title}</h3>
          <span className={`component-status ${isAvailable ? 'available' : 'unavailable'}`}>
            {isAvailable ? '✓' : '—'}
          </span>
        </div>
        <div className="component-card-body">
          {data.map((item, idx) => (
            <div key={idx} className="component-stat">
              <span className="stat-label">{item.label}</span>
              <span className="stat-value">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Repository component
  const repoData = inventory.repository || {};
  const repoStats = [
    { label: 'Branches', value: repoData.total_branches || 0 },
    { label: 'Tags', value: repoData.total_tags || 0 },
    { label: 'Commits', value: repoData.total_commits || 0 },
    { label: 'Size', value: `${repoData.total_size_mb?.toFixed(1) || 0} MB` },
    { label: 'LFS', value: repoData.has_lfs ? 'Yes' : 'No' }
  ];

  // CI/CD component
  const cicdData = inventory.ci_cd || {};
  const cicdStats = [
    { label: 'Projects with CI', value: cicdData.projects_with_ci || 0 },
    { label: 'Variables', value: cicdData.total_variables || 0 },
    { label: 'Environments', value: cicdData.total_environments || 0 },
    { label: 'Schedules', value: cicdData.total_schedules || 0 }
  ];

  // Issues component
  const issuesData = inventory.issues || {};
  const issuesStats = [
    { label: 'Open', value: issuesData.total_open || 0 },
    { label: 'Closed', value: issuesData.total_closed || 0 },
    { label: 'Labels', value: issuesData.total_labels || 0 },
    { label: 'Milestones', value: issuesData.total_milestones || 0 }
  ];

  // Merge Requests component
  const mrData = inventory.merge_requests || {};
  const mrStats = [
    { label: 'Open', value: mrData.total_open || 0 },
    { label: 'Merged', value: mrData.total_merged || 0 },
    { label: 'Closed', value: mrData.total_closed || 0 }
  ];

  // Wiki component
  const wikiData = inventory.wiki || {};
  const wikiStats = [
    { label: 'Projects with Wiki', value: wikiData.projects_with_wiki || 0 },
    { label: 'Total Pages', value: wikiData.total_pages || 0 }
  ];

  // Releases component
  const releasesData = inventory.releases || {};
  const releasesStats = [
    { label: 'Total Releases', value: releasesData.total_releases || 0 }
  ];

  // Settings component
  const settingsData = inventory.settings || {};
  const settingsStats = [
    { label: 'Protected Branches', value: settingsData.total_protected_branches || 0 },
    { label: 'Members', value: settingsData.total_members || 0 },
    { label: 'Webhooks', value: settingsData.total_webhooks || 0 },
    { label: 'Deploy Keys', value: settingsData.total_deploy_keys || 0 }
  ];

  return (
    <div className="component-inventory">
      <div className="inventory-header">
        <h2>📊 Component Inventory</h2>
        <p className="inventory-subtitle">
          Detailed analysis of {inventory.projects?.length || 0} project(s)
        </p>
      </div>

      <div className="component-grid">
        {renderComponentCard('Repository', '📁', repoStats, true)}
        {renderComponentCard('CI/CD', '⚙️', cicdStats, cicdData.projects_with_ci > 0)}
        {renderComponentCard('Issues', '📋', issuesStats, (issuesData.total_open + issuesData.total_closed) > 0)}
        {renderComponentCard('Merge Requests', '🔀', mrStats, (mrData.total_open + mrData.total_merged + mrData.total_closed) > 0)}
        {renderComponentCard('Wiki', '📖', wikiStats, wikiData.projects_with_wiki > 0)}
        {renderComponentCard('Releases', '🏷️', releasesStats, releasesData.total_releases > 0)}
        {renderComponentCard('Settings', '⚙️', settingsStats, true)}
      </div>
    </div>
  );
};
