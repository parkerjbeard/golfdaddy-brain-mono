import React, { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
// Removed StoreProvider import to prevent infinite auth loops
import { ProtectedRoute } from './components/ProtectedRoute'
import { AuthenticatedLayout } from './components/layout/AuthenticatedLayout'
import { LoginPage } from './pages/LoginPage'
import { Toaster } from './components/ui/toaster'

// Lazy load pages that might have circular dependencies
const CompanyDashboard = lazy(() => import('./pages/CompanyDashboard'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const ManagerDashboardPage = lazy(() => import('./pages/ManagerDashboardPage'))
const MyDashboard = lazy(() => import('./pages/MyDashboard'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const TeamManagementPage = lazy(() => import('./pages/TeamManagementPage'))
const DocumentationPage = lazy(() => import('./pages/DocumentationPage'))
const EmployeeDetail = lazy(() => import('./pages/EmployeeDetail'))
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'))
const CreateRaciMatrixPage = lazy(() => import('./pages/CreateRaciMatrixPage'))
const DepartmentDashboard = lazy(() => import('./pages/DepartmentDashboard'))
const NotFound = lazy(() => import('./pages/NotFound'))

// Loading component
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
  </div>
)

function App() {
  console.log('App component rendering...');
  
  // Log route changes
  React.useEffect(() => {
    console.log('Current location:', window.location.pathname);
  }, []);
  
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<PageLoader />}>
          <Routes>
              {/* Public routes */}
              <Route path="/login" element={<LoginPage />} />
              
              {/* Protected routes */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AuthenticatedLayout />
                  </ProtectedRoute>
                }
              >
                {/* Default redirect to dashboard */}
                <Route index element={<Navigate to="/dashboard" replace />} />
                
                {/* Company dashboard - accessible to all authenticated users */}
                <Route path="dashboard" element={<CompanyDashboard />} />
                
                {/* User's personal dashboard */}
                <Route path="my-dashboard" element={<MyDashboard />} />
                
                {/* Profile page */}
                <Route path="profile" element={<ProfilePage />} />
                
                {/* Admin-only routes */}
                <Route
                  path="admin"
                  element={
                    <ProtectedRoute requiredRoles={['admin']}>
                      <AdminDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="users"
                  element={
                    <ProtectedRoute requiredRoles={['admin']}>
                      <UserManagementPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="teams"
                  element={
                    <ProtectedRoute requiredRoles={['admin']}>
                      <TeamManagementPage />
                    </ProtectedRoute>
                  }
                />
                
                {/* Manager routes */}
                <Route
                  path="manager"
                  element={
                    <ProtectedRoute requiredRoles={['manager', 'admin']}>
                      <ManagerDashboardPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="department"
                  element={
                    <ProtectedRoute requiredRoles={['manager', 'admin']}>
                      <DepartmentDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="employees/:id"
                  element={
                    <ProtectedRoute requiredRoles={['manager', 'admin']}>
                      <EmployeeDetail />
                    </ProtectedRoute>
                  }
                />
                
                {/* Documentation routes */}
                <Route path="docs" element={<DocumentationPage />} />
                
                {/* RACI matrices */}
                <Route path="raci/create" element={<CreateRaciMatrixPage />} />
                
                {/* 404 */}
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </Suspense>
          <Toaster />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App