---
applyTo: "frontend/**/*.js,frontend/**/*.jsx,frontend/**/*.css"
---
# React Frontend Instructions

## Component Structure
```javascript
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import './ComponentName.css';

function ComponentName({ prop1, prop2 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get('/endpoint');
        setData(response.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="loading">Loading...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="component-name">
      {/* Component content */}
    </div>
  );
}

export default ComponentName;
```

## File Organization
- `src/components/` - Reusable UI components
- `src/pages/` - Page-level components (routes)
- `src/services/` - API service modules
- `src/contexts/` - React context providers
- `src/styles/` - CSS files

## CSS Conventions
- Use the GitHub-inspired theme from `styles/github-theme.css`
- BEM-like naming: `.component-name`, `.component-name__element`, `.component-name--modifier`
- Prefer existing utility classes where available
- CSS file should match component name

## API Calls
```javascript
// Use the api service
import api from '../services/api';

// GET request
const response = await api.get('/projects');

// POST request
const response = await api.post('/projects', { name: 'New Project' });

// With error handling
try {
  const response = await api.post('/auth/login', credentials);
  // Handle success
} catch (error) {
  // error.response.data contains server error
  setError(error.response?.data?.detail || 'Request failed');
}
```

## WebSocket (Socket.IO)
```javascript
import { useEffect } from 'react';
import io from 'socket.io-client';

useEffect(() => {
  const socket = io();
  
  socket.on('event_name', (data) => {
    // Handle real-time event
  });
  
  return () => socket.disconnect();
}, []);
```

## Routing
Routes are defined in `App.js`. To add a new page:
1. Create component in `src/pages/`
2. Add route in `App.js`:
```javascript
<Route path="/new-page" element={<NewPage />} />
```

## State Management
- Use React hooks (`useState`, `useEffect`, `useContext`)
- For shared state, use Context API (see `src/contexts/`)
- Keep component state local when possible
