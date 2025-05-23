import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
import { Layout } from "@/components/layout/Layout";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import AuthenticatedLogin from "@/components/auth/AuthenticatedLogin";
import CompanyDashboard from "./pages/CompanyDashboard";
import DepartmentDashboard from "./pages/DepartmentDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import EmployeeDetail from "./pages/EmployeeDetail";
import NotFound from "./pages/NotFound";
import UserManagementPage from "./pages/UserManagementPage";
import ManagerDashboardPage from "./pages/ManagerDashboardPage";
import TeamManagementPage from "./pages/TeamManagementPage";
import CreateRaciTaskPage from './pages/CreateRaciTaskPage';
import { UserRole } from "@/types/user";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <Router>
          <div>
            <main className="p-4">
              <Routes>
                {/* Public routes */}
                <Route 
                  path="/login" 
                  element={<AuthenticatedLogin variant="branded" />} 
                />
                
                {/* Protected routes with role-based access */}
                <Route 
                  path="/" 
                  element={
                    <ProtectedRoute>
                      <Layout><CompanyDashboard /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                <Route 
                  path="/department" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.DEVELOPER, UserRole.LEAD, UserRole.MANAGER, UserRole.ADMIN]}>
                      <Layout><DepartmentDashboard /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                {/* Admin-only routes */}
                <Route 
                  path="/admin" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.ADMIN]}>
                      <Layout><AdminDashboard /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                <Route 
                  path="/admin/users" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.ADMIN]}>
                      <Layout><UserManagementPage /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                <Route 
                  path="/admin/teams" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.ADMIN]}>
                      <Layout><TeamManagementPage /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                <Route 
                  path="/admin/employee/:id" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.ADMIN, UserRole.MANAGER]}>
                      <Layout><EmployeeDetail /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                {/* Manager-only routes */}
                <Route 
                  path="/manager-dashboard" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.MANAGER, UserRole.ADMIN]}>
                      <Layout><ManagerDashboardPage /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                {/* Task creation - accessible by developers and above */}
                <Route 
                  path="/create-raci-task" 
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.DEVELOPER, UserRole.LEAD, UserRole.MANAGER, UserRole.ADMIN]}>
                      <Layout><CreateRaciTaskPage /></Layout>
                    </ProtectedRoute>
                  } 
                />
                
                {/* Catch-all route */}
                <Route 
                  path="*" 
                  element={
                    <ProtectedRoute>
                      <Layout><NotFound /></Layout>
                    </ProtectedRoute>
                  } 
                />
              </Routes>
            </main>
          </div>
        </Router>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
