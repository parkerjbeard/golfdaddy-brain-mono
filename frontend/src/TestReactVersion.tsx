import React from 'react';
import ReactDOM from 'react-dom/client';

// Test without StrictMode and with explicit error boundary
export function testReact() {
  console.log('testReact called');
  
  const root = document.getElementById('root');
  if (!root) return;
  
  // Clear any existing content
  root.textContent = '';
  
  // Test 1: Direct render without StrictMode
  try {
    const reactRoot = ReactDOM.createRoot(root);
    reactRoot.render(
      React.createElement('div', {},
        React.createElement('h1', {}, 'React Version: ' + React.version),
        React.createElement('p', {}, 'No StrictMode'),
        React.createElement('p', {}, 'Time: ' + new Date().toLocaleTimeString())
      )
    );
    console.log('React rendered successfully');
  } catch (e) {
    console.error('React render failed:', e);
    // Safely display error without XSS vulnerability
    root.textContent = '';
    const heading = document.createElement('h1');
    heading.textContent = `React Error: ${e}`;
    root.appendChild(heading);
  }
}

// Call it immediately
testReact();