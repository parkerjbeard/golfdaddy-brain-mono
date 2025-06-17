import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { 
  BarChart, 
  FileText, 
  Home,
  ClipboardList,
  LogOut,
  User as UserIcon
} from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface AppSidebarProps {
  collapsible?: "offcanvas" | "icon" | "none";
}

export function AppSidebar({ collapsible }: AppSidebarProps) {
  const { session, signOut } = useAuth();
  const user = session?.user;
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path || (path === '/tasks' && location.pathname.startsWith('/tasks'));
  };

  const handleSignOut = () => {
    signOut();
  };

  // Get display name and avatar from user metadata or fallback to email/defaults
  const displayName = user?.user_metadata?.name || user?.email?.split('@')[0] || 'User';
  const avatarUrl = user?.user_metadata?.avatar_url;

  return (
    <Sidebar collapsible={collapsible}>
      {/* <SidebarHeader className="h-16">
        // This header was acting as a spacer for the Navbar, now removed
      </SidebarHeader> */}

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Executive Dashboard</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton 
                  isActive={isActive('/')} 
                  asChild 
                  tooltip="Company Dashboard"
                >
                  <Link to="/">
                    <Home className="h-5 w-5" />
                    <span>Executive Overview</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              
              <SidebarMenuItem>
                <SidebarMenuButton 
                  isActive={isActive('/admin')} 
                  asChild 
                  tooltip="Admin Dashboard"
                >
                  <Link to="/admin">
                    <BarChart className="h-5 w-5" />
                    <span>Admin Dashboard</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton 
                  isActive={isActive('/manager')} 
                  asChild 
                  tooltip="Manager Dashboard"
                >
                  <Link to="/manager">
                    <ClipboardList className="h-5 w-5" />
                    <span>Manager Dashboard</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>


            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Resources</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton 
                  isActive={isActive('/docs')} 
                  asChild 
                  tooltip="Documentation"
                >
                  <Link to="/docs">
                    <FileText className="h-5 w-5" />
                    <span>Documentation</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {user && (
        <SidebarFooter className="border-t p-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild className="w-full">
              <Button variant="ghost" className="flex items-center justify-start gap-3 w-full h-auto px-2 py-2 text-left">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={avatarUrl || undefined} alt={displayName} />
                  <AvatarFallback>
                    {displayName.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 truncate">
                  <div className="text-sm font-medium">{displayName}</div>
                  <p className="text-xs leading-none text-muted-foreground truncate">{user.email}</p>
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" side="top" className="mb-1 w-[calc(var(--sidebar-width)_-_1rem)]">
              <DropdownMenuLabel>
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">{displayName}</p>
                  <p className="text-xs leading-none text-muted-foreground">{user.email}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleSignOut}>
                <LogOut className="mr-2 h-4 w-4" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarFooter>
      )}
      
      <SidebarRail />
    </Sidebar>
  );
}
