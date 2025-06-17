import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole } from '@/types/user';
import { 
  BarChart, 
  ChevronLeft, 
  FileText, 
  Home, 
  Menu, 
  User,
  X 
} from 'lucide-react';
import { useState } from 'react';
import { useIsMobile } from '@/hooks/use-mobile';

export function Sidebar() {
  const { user } = useAuth();
  const location = useLocation();
  const isMobile = useIsMobile();
  const [isOpen, setIsOpen] = useState(!isMobile);

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const toggleSidebar = () => {
    setIsOpen(!isOpen);
  };

  return (
    <>
      {/* Mobile overlay */}
      {isMobile && isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
          onClick={() => setIsOpen(false)}
        ></div>
      )}

      {/* Toggle button for mobile */}
      {isMobile && (
        <button
          className="fixed bottom-6 right-6 z-50 rounded-full bg-primary p-3 text-primary-foreground shadow-lg hover:bg-primary/90"
          onClick={toggleSidebar}
          aria-label="Toggle sidebar"
        >
          {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-40 w-64 transform bg-sidebar text-sidebar-foreground transition-transform duration-200 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } ${isMobile ? 'md:hidden' : 'hidden md:block'}`}
      >
        <div className="flex h-full flex-col border-r">
          {/* Header */}
          <div className="flex h-16 items-center justify-between border-b px-4">
            <Link to="/" className="flex items-center gap-2">
              <svg 
                viewBox="0 0 24 24" 
                className="h-6 w-6 text-primary" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2"
                strokeLinecap="round" 
                strokeLinejoin="round"
              >
                <rect width="20" height="14" x="2" y="5" rx="2" />
                <path d="M2 10h20" />
              </svg>
              <span className="font-semibold">ExecutivePulse</span>
            </Link>
            
            {!isMobile && (
              <button
                className="text-muted-foreground hover:text-foreground"
                onClick={toggleSidebar}
                aria-label="Toggle sidebar"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* Nav links */}
          <nav className="flex-1 overflow-y-auto p-4">
            <ul className="space-y-2">
              <li>
                <Link
                  to="/"
                  className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive('/') 
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
                      : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                  }`}
                  onClick={() => isMobile && setIsOpen(false)}
                >
                  <Home className="h-5 w-5" />
                  Company Dashboard
                </Link>
              </li>

              {user?.team && (
                <li>
                  <Link
                    to="/department"
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive('/department') 
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
                        : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                    }`}
                    onClick={() => isMobile && setIsOpen(false)}
                  >
                    <Home className="h-5 w-5" />
                    Department Dashboard
                  </Link>
                </li>
              )}

              <li>
                <Link
                  to="/documentation"
                  className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive('/documentation') 
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
                      : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                  }`}
                  onClick={() => isMobile && setIsOpen(false)}
                >
                  <FileText className="h-5 w-5" />
                  Documentation
                </Link>
              </li>

              {(user?.role === UserRole.ADMIN) && (
                <li>
                  <Link
                    to="/admin"
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive('/admin') 
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
                        : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                    }`}
                    onClick={() => isMobile && setIsOpen(false)}
                  >
                    <BarChart className="h-5 w-5" />
                    Administration
                  </Link>
                </li>
              )}
            </ul>
          </nav>

          {/* Footer */}
          {user && (
            <div className="border-t p-4">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  {user.avatar_url ? (
                    <img 
                      src={user.avatar_url} 
                      alt={user.name || 'User Avatar'} 
                      className="h-8 w-8 rounded-full object-cover" 
                    />
                  ) : (
                    <User className="h-5 w-5 text-primary" />
                  )}
                </div>
                <div className="flex-1 truncate">
                  <div className="text-sm font-medium">{user.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                    {user.team && ` • ${user.team}`}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
