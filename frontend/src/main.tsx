import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// Global error handler
window.addEventListener('error', (event) => {
  const errorDiv = document.getElementById('error-display');
  if (errorDiv) {
    // Clear any existing content safely
    errorDiv.textContent = '';
    
    // Create elements safely to prevent XSS
    const heading = document.createElement('h3');
    heading.textContent = 'Runtime Error:';
    
    const pre = document.createElement('pre');
    pre.textContent = `${event.error}\n${event.error?.stack || ''}`;
    pre.style.cssText = 'overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;';
    
    errorDiv.appendChild(heading);
    errorDiv.appendChild(pre);
    errorDiv.style.display = 'block';
  }
});

window.addEventListener('unhandledrejection', (event) => {
  // Unhandled promise rejection
});

// Error Boundary
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Error caught by boundary
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', backgroundColor: '#fee', border: '1px solid #fcc' }}>
          <h2 style={{ color: '#c00' }}>Application Error</h2>
          <details style={{ marginTop: '10px' }}>
            <summary>Error Details</summary>
            <pre style={{ marginTop: '10px', fontSize: '12px' }}>
              {this.state.error?.toString()}
              {'\n\n'}
              {this.state.error?.stack}
            </pre>
          </details>
          <button 
            onClick={() => window.location.reload()} 
            style={{ marginTop: '10px', padding: '5px 10px' }}
          >
            Reload Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

const container = document.getElementById('root');
if (!container) {
  // Root element not found
} else {
  // Add error display div
  const errorDiv = document.createElement('div');
  errorDiv.id = 'error-display';
  errorDiv.style.cssText = 'display:none; position:fixed; top:0; left:0; right:0; background:#fee; padding:20px; z-index:10000; border-bottom:2px solid #f00;';
  document.body.insertBefore(errorDiv, document.body.firstChild);
  
  try {
    const root = createRoot(container);
    
    root.render(
      <React.StrictMode>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </React.StrictMode>
    );
  } catch (error) {
    // Safely display error without XSS vulnerability
    container.textContent = '';
    const heading = document.createElement('h1');
    heading.style.color = 'red';
    heading.textContent = `Mount Error: ${error}`;
    container.appendChild(heading);
  }
}