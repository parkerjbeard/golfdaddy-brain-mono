import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Test component to check if basic routing works
const TestComponent = ({ name }: { name: string }) => (
  <div style={{ padding: '20px', border: '1px solid #ccc', margin: '10px' }}>
    <h2>{name} Component</h2>
    <p>This component is rendering correctly</p>
  </div>
)

// Test component to check environment variables
const EnvCheck = () => {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY
  
  return (
    <div style={{ padding: '20px', backgroundColor: '#f9f9f9' }}>
      <h3>Environment Variables Check:</h3>
      <ul>
        <li>VITE_SUPABASE_URL: {supabaseUrl ? '✅ Set' : '❌ Missing'}</li>
        <li>VITE_SUPABASE_ANON_KEY: {supabaseAnonKey ? '✅ Set' : '❌ Missing'}</li>
      </ul>
    </div>
  )
}

// Test the App structure without auth
export default function TestApp() {
  console.log('TestApp rendering...')
  
  return (
    <div>
      <h1 style={{ padding: '20px', backgroundColor: '#333', color: 'white' }}>
        Test App - Debugging React Routing
      </h1>
      
      <EnvCheck />
      
      <div style={{ padding: '20px' }}>
        <h2>Testing React Router:</h2>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<TestComponent name="Home" />} />
            <Route path="/test" element={<TestComponent name="Test" />} />
          </Routes>
        </BrowserRouter>
      </div>
      
      <div style={{ padding: '20px', backgroundColor: '#eee' }}>
        <h3>Console Check:</h3>
        <p>Open browser console to see any errors</p>
        <button onClick={() => console.log('Button clicked - React events working!')}>
          Test Console Log
        </button>
      </div>
    </div>
  )
}