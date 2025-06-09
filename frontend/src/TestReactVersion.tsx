import React from 'react';
import ReactDOM from 'react-dom/client';

// Test without StrictMode and with explicit error boundary
export function testReact() {
  console.log('testReact called');
  
  const root = document.getElementById('root');
  if (!root) return;
  
  // Clear any existing content
  root.innerHTML = '';
  
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
    root.innerHTML = '<h1>React Error: ' + e + '</h1>';
  }
}

// Call it immediately
testReact();