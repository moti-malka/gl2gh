# Frontend Implementation TODOs

## Critical Security Issues

### 1. Token Storage (High Priority)
- **Current**: Tokens stored in localStorage (vulnerable to XSS)
- **Action**: Migrate to httpOnly cookies or implement token encryption
- **File**: `src/contexts/AuthContext.js`, `src/services/api.js`

### 2. Password Requirements (Medium Priority)
- **Current**: Only checks minimum length
- **Action**: Add stronger requirements (mixed case, numbers, special chars)
- **File**: `src/pages/ProfilePage.js`

## Code Quality Improvements

### 3. WebSocket Reconnection Logic (High Priority)
- **Current**: No reconnection handling
- **Action**: Implement automatic reconnection with exponential backoff
- **File**: `src/services/websocket.js`

### 4. Remove Console Logging (Low Priority)
- **Current**: Console.log statements in production code
- **Action**: Replace with proper logging utility or environment-based logging
- **File**: `src/services/websocket.js`, various components

### 5. User Mapping API Integration (High Priority)
- **Current**: Using hardcoded mock data
- **Action**: Implement actual API calls to backend
- **File**: `src/pages/UserMappingPage.js`

### 6. Custom Confirmation Modal (Medium Priority)
- **Current**: Using window.confirm()
- **Action**: Create custom modal component
- **File**: `src/pages/RunDashboardPage.js`, `src/pages/ProjectsPage.js`

### 7. Remember Me Functionality (Low Priority)
- **Current**: Checkbox exists but not functional
- **Action**: Implement or remove
- **File**: `src/pages/LoginPage.js`

### 8. Save Mapping Input Handling (High Priority)
- **Current**: Hardcoded values instead of reading input
- **Action**: Implement controlled input or useRef pattern
- **File**: `src/pages/UserMappingPage.js` (modal)

## Missing Features (From Original Requirements)

### 9. Connection Management
- [ ] Connection list component
- [ ] GitLab connection test functionality
- [ ] GitHub connection test functionality
- [ ] Connection edit/delete

### 10. Secrets Entry
- [ ] Missing secrets list
- [ ] Secure masked input fields
- [ ] Bulk entry mode
- [ ] Skip optional secrets

### 11. Artifact Viewers
- [ ] Plan viewer with phase breakdown
- [ ] Conversion gaps viewer with categorization
- [ ] Verification report viewer with pass/fail indicators
- [ ] Artifact browser with tree view

### 12. Run History
- [ ] Dedicated run history page
- [ ] Advanced filtering options
- [ ] Run comparison feature

### 13. Theme Toggle
- [ ] Dark/light theme implementation
- [ ] Theme persistence
- [ ] System preference detection

### 14. Testing
- [ ] Component tests with React Testing Library
- [ ] E2E tests with Cypress/Playwright
- [ ] Integration tests for critical flows

## Performance Optimizations

### 15. Code Splitting
- [ ] Implement React.lazy for route-based splitting
- [ ] Lazy load heavy components
- [ ] Optimize bundle size

### 16. Data Caching
- [ ] Consider React Query for server state
- [ ] Implement cache invalidation strategies
- [ ] Add optimistic updates

### 17. Virtual Scrolling
- [ ] Implement for large lists (projects, runs, events)
- [ ] Consider react-window or react-virtualized

## Accessibility Improvements

### 18. ARIA Labels
- [ ] Add comprehensive ARIA labels
- [ ] Improve screen reader support
- [ ] Add keyboard navigation hints

### 19. Focus Management
- [ ] Implement focus traps for modals
- [ ] Add skip navigation links
- [ ] Ensure logical tab order

## UX Enhancements

### 20. Loading States
- [ ] Add skeleton screens for better perceived performance
- [ ] Implement progressive loading
- [ ] Add retry mechanisms

### 21. Error Messages
- [ ] More descriptive error messages
- [ ] Add suggestions for common errors
- [ ] Implement error recovery options

### 22. Help & Documentation
- [ ] Add tooltips for complex features
- [ ] Implement contextual help
- [ ] Create interactive tutorials

### 23. Batch Operations
- [ ] Multi-select for projects/runs
- [ ] Bulk delete/cancel
- [ ] Batch status updates

## API Integration Completeness

### 24. Missing API Endpoints
- [ ] User registration (if enabled)
- [ ] Connection management endpoints
- [ ] User mapping endpoints
- [ ] Secrets management endpoints
- [ ] Artifact download endpoints

## Documentation

### 25. Component Documentation
- [ ] Add JSDoc comments
- [ ] Create Storybook stories
- [ ] Document props and usage

### 26. Developer Guide
- [ ] Setup instructions
- [ ] Architecture overview
- [ ] Contribution guidelines
- [ ] Coding standards

## Priority Matrix

**High Priority (Do First)**
1. Token Storage Security
2. User Mapping API Integration
3. WebSocket Reconnection Logic
4. Save Mapping Input Handling

**Medium Priority (Do Soon)**
5. Password Requirements
6. Custom Confirmation Modal
7. Connection Management
8. Secrets Entry

**Low Priority (Do Eventually)**
9. Remove Console Logging
10. Remember Me Functionality
11. Theme Toggle
12. Code Splitting
