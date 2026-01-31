# Add React Component

Create a new React component following gl2gh frontend patterns.

## Component Requirements
- Functional component with hooks
- Use existing CSS from `styles/github-theme.css`
- Handle loading and error states
- Use api service for HTTP calls

## Reference Files
- [App.js](../../frontend/src/App.js) - Routing
- [api.js](../../frontend/src/services/api.js) - API service
- [github-theme.css](../../frontend/src/styles/github-theme.css) - Styles

## Component Template
```javascript
import React, { useState, useEffect } from 'react';
import api from '../services/api';

function NewComponent({ prop1 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch data
  }, []);

  if (loading) return <div className="loading">Loading...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="new-component">
      {/* Content */}
    </div>
  );
}

export default NewComponent;
```

## Checklist
1. [ ] Create component in `frontend/src/components/` or `pages/`
2. [ ] Add CSS if needed
3. [ ] Update routing in `App.js` if it's a page
4. [ ] Test component manually
