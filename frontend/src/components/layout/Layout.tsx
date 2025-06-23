import { AppSidebar } from "./AppSidebar";
import { ReactNode } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { DevRoleSelector } from "../DevRoleSelector";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex min-h-screen w-full flex-col bg-background">
        {/* <Navbar> Removed Navbar component usage
        </Navbar> */}
        <div className="flex flex-1 w-full">
          <AppSidebar collapsible="none" />
          <SidebarInset className="animate-fade-in">
            <main className="flex-1 pt-6 px-4 md:px-6 pb-12">
              <div className="mx-auto max-w-7xl">
                {children}
              </div>
            </main>
          </SidebarInset>
        </div>
      </div>
      <DevRoleSelector />
    </SidebarProvider>
  );
}
