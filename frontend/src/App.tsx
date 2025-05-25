import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
import { Layout } from "@/components/layout/Layout";
import CompanyDashboard from "./pages/CompanyDashboard";
import DepartmentDashboard from "./pages/DepartmentDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import EmployeeDetail from "./pages/EmployeeDetail";
import LoginPage from "./pages/LoginPage";
import NotFound from "./pages/NotFound";
import UserManagementPage from "./pages/UserManagementPage";
import ManagerDashboardPage from "./pages/ManagerDashboardPage";
import TeamManagementPage from "./pages/TeamManagementPage";
import CreateRaciTaskPage from './pages/CreateRaciTaskPage';

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
                <Route path="/login" element={<LoginPage />} />
                <Route path="/" element={<Layout><CompanyDashboard /></Layout>} />
                <Route path="/department" element={<Layout><DepartmentDashboard /></Layout>} />
                <Route path="/admin" element={<Layout><AdminDashboard /></Layout>} />
                <Route path="/admin/users" element={<Layout><UserManagementPage /></Layout>} />
                <Route path="/admin/teams" element={<Layout><TeamManagementPage /></Layout>} />
                <Route path="/admin/employee/:id" element={<Layout><EmployeeDetail /></Layout>} />
                <Route path="/manager-dashboard" element={<Layout><ManagerDashboardPage /></Layout>} />
                <Route path="/create-raci-task" element={<Layout><CreateRaciTaskPage /></Layout>} />
                <Route path="*" element={<Layout><NotFound /></Layout>} />
              </Routes>
            </main>
          </div>
        </Router>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
