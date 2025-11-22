import { ReactNode, useMemo } from "react";
import { Link } from "react-router-dom";
import { Clock3, RefreshCw, Sparkles } from "lucide-react";
import { AppSidebar } from "./AppSidebar";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const freshnessLabel = useMemo(() => {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }, []);

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex min-h-screen w-full flex-col bg-background">
        <div className="flex flex-1 w-full">
          <AppSidebar collapsible="none" />
          <SidebarInset className="animate-fade-in">
            <header className="sticky top-0 z-10 px-4 md:px-6 py-3 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 border-b">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3">
                  <SidebarTrigger className="md:hidden" />
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock3 className="h-4 w-4" />
                    <span>Updated {freshnessLabel}</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 md:gap-3">
                  <Button variant="outline" size="sm" className="gap-2" onClick={() => window.location.reload()}>
                    <RefreshCw className="h-4 w-4" />
                    Refresh
                  </Button>

                  <Separator orientation="vertical" className="hidden h-6 md:block" />

                  <Button asChild size="sm" className="gap-2">
                    <Link to="/raci/create">
                      <Sparkles className="h-4 w-4" />
                      New Task
                    </Link>
                  </Button>
                </div>
              </div>
            </header>

            <main className="flex-1 pt-6 px-4 md:px-6 pb-12">
              <div className="mx-auto max-w-7xl">
                {children}
              </div>
            </main>
          </SidebarInset>
        </div>
      </div>
    </SidebarProvider>
  );
}
