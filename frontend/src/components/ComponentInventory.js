/**
 * ComponentInventory - Compact professional inventory display
 */
import React from 'react';
import './ComponentInventory.css';

export const ComponentInventory = ({ inventory }) => {
  if (!inventory) return null;

  const components = [
    {
      key: 'repository',
      label: 'Repository',
      icon: '📁',
      data: inventory.repository || {},
      stats: (d) => [
        { label: 'Branches', value: d.total_branches || 0 },
        { label: 'Tags', value: d.total_tags || 0 },
        { label: 'Commits', value: d.total_commits || 0 },
      ],
      hasContent: () => true
    },
    {
      key: 'ci_cd',
      label: 'CI/CD',
      icon: '⚙️',
      data: inventory.ci_cd || {},
      stats: (d) => [
        { label: 'Pipelines', value: d.projects_with_ci || 0 },
        { label: 'Environments', value: d.total_environments || 0 },
        { label: 'Variables', value: d.total_variables || 0 },
      ],
      hasContent: (d) => d.projects_with_ci > 0
    },
    {
      key: 'issues',
      label: 'Issues',
      icon: '📋',
      data: inventory.issues || {},
      stats: (d) => [
        { label: 'Open', value: d.total_open || 0 },
        { label: 'Closed', value: d.total_closed || 0 },
        { label: 'Labels', value: d.total_labels || 0 },
      ],
      hasContent: (d) => (d.total_open || 0) + (d.total_closed || 0) > 0
    },
    {
      key: 'merge_requests',
      label: 'Merge Requests',
      icon: '🔀',
      data: inventory.merge_requests || {},
      stats: (d) => [
        { label: 'Open', value: d.total_open || 0 },
        { label: 'Merged', value: d.total_merged || 0 },
      ],
      hasContent: (d) => (d.total_open || 0) + (d.total_merged || 0) > 0
    },
    {
      key: 'wiki',
      label: 'Wiki',
      icon: '📖',
      data: inventory.wiki || {},
      stats: (d) => [
        { label: 'Pages', value: d.total_pages || 0 },
      ],
      hasContent: (d) => d.total_pages > 0
    },
    {
      key: 'releases',
      label: 'Releases',
      icon: '🏷️',
      data: inventory.releases || {},
      stats: (d) => [
        { label: 'Total', value: d.total_releases || 0 },
      ],
      hasContent: (d) => d.total_releases > 0
    },
    {
      key: 'settings',
      label: 'Settings',
      icon: '🔒',
      data: inventory.settings || {},
      stats: (d) => [
        { label: 'Protected', value: d.total_protected_branches || 0 },
        { label: 'Members', value: d.total_members || 0 },
      ],
      hasContent: (d) => (d.total_protected_branches || 0) + (d.total_members || 0) > 0
    },
  ];

  // Count total items to migrate
  const totalItems = 
    (inventory.issues?.total_open || 0) + 
    (inventory.issues?.total_closed || 0) +
    (inventory.merge_requests?.total_open || 0) +
    (inventory.merge_requests?.total_merged || 0) +
    (inventory.releases?.total_releases || 0) +
    (inventory.wiki?.total_pages || 0);

  return (
    <div className="inventory-panel">
      <div className="inventory-summary">
        <div className="inventory-title">
          <span className="inventory-icon">📊</span>
          <div>
            <h3>Discovery Complete</h3>
            <p>{inventory.projects?.length || 1} project • {totalItems} items to migrate</p>
          </div>
        </div>
      </div>
      
      <div className="inventory-grid">
        {components.map((comp) => {
          const hasContent = comp.hasContent(comp.data);
          const stats = comp.stats(comp.data);
          
          return (
            <div key={comp.key} className={`inventory-item ${hasContent ? 'active' : 'empty'}`}>
              <div className="inventory-item-header">
                <span className="item-icon">{comp.icon}</span>
                <span className="item-label">{comp.label}</span>
                {hasContent && <span className="item-badge">✓</span>}
              </div>
              <div className="inventory-item-stats">
                {stats.map((stat, i) => (
                  <div key={i} className="stat">
                    <span className="stat-value">{stat.value}</span>
                    <span className="stat-label">{stat.label}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
