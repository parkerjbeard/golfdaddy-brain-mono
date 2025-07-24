import React from 'react'

function AppWrapper() {
  try {
    const App = require('./App').default;
    return <App />;
  } catch (error) {
    console.error('Failed to load App:', error);
    return (
      <div style={{ padding: '20px', color: 'red' }}>
        <h1>Error Loading App</h1>
        <pre>{error instanceof Error ? error.message : 'Unknown error'}</pre>
        <pre>{error instanceof Error ? error.stack : ''}</pre>
      </div>
    );
  }
}

export default AppWrapper