import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'

function DebugInfo() {
  const { session, loading } = useAuth()
  
  return (
    <div style={{ padding: '20px', backgroundColor: '#f0f0f0' }}>
      <h2>Debug Info</h2>
      <p>Loading: {loading ? 'Yes' : 'No'}</p>
      <p>Session: {session ? 'Exists' : 'None'}</p>
      <p>User: {session?.user?.email || 'Not logged in'}</p>
    </div>
  )
}

function SimpleProtectedPage() {
  return (
    <div style={{ padding: '20px' }}>
      <h1>Protected Page</h1>
      <p>If you see this, you are logged in!</p>
    </div>
  )
}

function DebugApp() {
  const [renderStage, setRenderStage] = useState('initial')
  
  useEffect(() => {
    console.log('DebugApp mounted')
    setRenderStage('mounted')
  }, [])
  
  console.log('DebugApp rendering, stage:', renderStage)
  
  return (
    <div>
      <h1 style={{ padding: '20px' }}>Debug App - Stage: {renderStage}</h1>
      <BrowserRouter>
        <AuthProvider>
          <DebugInfo />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <SimpleProtectedPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  )
}

export default DebugApp