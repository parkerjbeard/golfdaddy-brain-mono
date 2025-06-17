import React from 'react'

export default function SimpleTest() {
  console.log('SimpleTest component rendering');
  
  return (
    <div style={{ padding: '20px', backgroundColor: '#f0f0f0', minHeight: '100vh' }}>
      <h1>React is working!</h1>
      <p>If you can see this, React is rendering properly.</p>
      <p>Current time: {new Date().toLocaleString()}</p>
      <button onClick={() => alert('Button clicked!')}>Test Button</button>
    </div>
  )
}