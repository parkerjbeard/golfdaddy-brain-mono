import { useCallback, useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import { secureStorage } from "@/services/secureStorage";
import api from "@/services/api/endpoints";
import { UserResponse } from "@/types/user";
import {
  CalendarDays,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  PlayCircle,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Trash2,
} from "lucide-react";

type StoredOpenAIKey = {
  key: string;
  savedAt: number;
};

const OPENAI_KEY_STORAGE_KEY = "admin_openai_api_key";

export const AdminSettingsButton = () => {
  const [isOpen, setIsOpen] = useState(false);

  // OpenAI key management
  const [openAiKeyInput, setOpenAiKeyInput] = useState("");
  const [hasStoredKey, setHasStoredKey] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [isSavingKey, setIsSavingKey] = useState(false);
  const [showKey, setShowKey] = useState(false);

  // Manual analysis
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [analysisDate, setAnalysisDate] = useState<string>(() => format(new Date(), "yyyy-MM-dd"));
  const [isRunningUserAnalysis, setIsRunningUserAnalysis] = useState(false);
  const [isRunningBatch, setIsRunningBatch] = useState(false);

  // Ops utilities
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [healthSummary, setHealthSummary] = useState<string | null>(null);
  const [refreshingZapier, setRefreshingZapier] = useState(false);
  const [archiveDays, setArchiveDays] = useState("180");
  const [archiving, setArchiving] = useState(false);

  const selectedUserLabel = useMemo(() => {
    const found = users.find((u) => u.id === selectedUserId);
    return found?.name || found?.email || "Selected user";
  }, [users, selectedUserId]);

  const loadStoredKey = useCallback(async () => {
    const stored = await secureStorage.getItem<StoredOpenAIKey>(OPENAI_KEY_STORAGE_KEY);
    if (stored?.key) {
      setHasStoredKey(true);
      setLastSavedAt(stored.savedAt || null);
    } else {
      setHasStoredKey(false);
      setLastSavedAt(null);
    }
  }, []);

  const handleSaveKey = async () => {
    const trimmed = openAiKeyInput.trim();
    if (!trimmed) {
      toast({
        title: "Missing key",
        description: "Enter an OpenAI API key before saving.",
        variant: "destructive",
      });
      return;
    }

    setIsSavingKey(true);
    try {
      const payload: StoredOpenAIKey = { key: trimmed, savedAt: Date.now() };
      await secureStorage.setItem(OPENAI_KEY_STORAGE_KEY, payload, {
        tags: ["admin", "openai"],
        // 180 days default - can be cleared sooner by admin
        expiresIn: 1000 * 60 * 60 * 24 * 180,
      });
      await loadStoredKey();
      setOpenAiKeyInput("");
      toast({
        title: "Key saved securely",
        description: "Stored with client-side encryption. Remember to configure the backend as well.",
      });
    } catch (error) {
      toast({
        title: "Save failed",
        description: error instanceof Error ? error.message : "Unable to save API key",
        variant: "destructive",
      });
    } finally {
      setIsSavingKey(false);
    }
  };

  const handleClearKey = async () => {
    setIsSavingKey(true);
    try {
      await secureStorage.removeItem(OPENAI_KEY_STORAGE_KEY);
      setHasStoredKey(false);
      setLastSavedAt(null);
      setOpenAiKeyInput("");
      toast({ title: "Key removed", description: "The stored OpenAI key was cleared from this device." });
    } catch (error) {
      toast({
        title: "Clear failed",
        description: error instanceof Error ? error.message : "Unable to clear stored key",
        variant: "destructive",
      });
    } finally {
      setIsSavingKey(false);
    }
  };

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const response = await api.users.getUsers();
      const list = Array.isArray(response?.users) ? response.users : response;
      setUsers(list || []);
      if (!selectedUserId && list?.length) {
        setSelectedUserId(list[0].id);
      }
    } catch (error) {
      toast({
        title: "Could not load users",
        description: error instanceof Error ? error.message : "Failed to fetch users list",
        variant: "destructive",
      });
    } finally {
      setUsersLoading(false);
    }
  }, [selectedUserId]);

  const runUserAnalysis = async () => {
    if (!selectedUserId) {
      toast({
        title: "Pick a user",
        description: "Select who should be analyzed before running the job.",
        variant: "destructive",
      });
      return;
    }

    setIsRunningUserAnalysis(true);
    try {
      const apiResponse = await api.dailyAnalysis.triggerUserAnalysis(selectedUserId, analysisDate);
      const result = apiResponse?.data ?? apiResponse;
      const hoursText = result?.total_hours ? ` Est. hours: ${result.total_hours}` : "";
      toast({
        title: "Analysis triggered",
        description:
          result?.message || `Job queued for ${selectedUserLabel} on ${analysisDate}.${hoursText}`,
      });
    } catch (error) {
      toast({
        title: "Run failed",
        description: error instanceof Error ? error.message : "Unable to run analysis",
        variant: "destructive",
      });
    } finally {
      setIsRunningUserAnalysis(false);
    }
  };

  const runBatchAnalysis = async () => {
    setIsRunningBatch(true);
    try {
      const apiResponse = await api.dailyAnalysis.triggerBatchAnalysis(analysisDate);
      const result = apiResponse?.data ?? apiResponse;
      const total = Array.isArray(result?.results) ? result.results.length : undefined;
      toast({
        title: "Batch run started",
        description: result?.message || `Triggered analysis for ${total ?? "all"} users on ${analysisDate}.`,
      });
    } catch (error) {
      toast({
        title: "Batch failed",
        description: error instanceof Error ? error.message : "Unable to start batch analysis",
        variant: "destructive",
      });
    } finally {
      setIsRunningBatch(false);
    }
  };

  const runHealthCheck = async () => {
    setCheckingHealth(true);
    try {
      const response = await api.system.getHealthCheck();
      const data = response?.data || response;
      const status = data?.status || "unknown";
      const openAi = data?.checks?.openai_api?.status || data?.openai_api?.status;
      const github = data?.checks?.github_api?.status || data?.github_api?.status;
      setHealthSummary(`Overall: ${status}${openAi ? ` • OpenAI: ${openAi}` : ""}${github ? ` • GitHub: ${github}` : ""}`);
      toast({
        title: "Health check complete",
        description: `System status: ${status}`,
      });
    } catch (error) {
      toast({
        title: "Health check failed",
        description: error instanceof Error ? error.message : "Unable to reach health endpoint",
        variant: "destructive",
      });
    } finally {
      setCheckingHealth(false);
    }
  };

  const refreshZapierData = async () => {
    setRefreshingZapier(true);
    try {
      const response = await api.zapier.refreshDashboardData();
      const result = response?.data ?? response;
      toast({
        title: "Dashboard refresh sent",
        description: result?.message || "Zapier refresh webhook dispatched.",
      });
    } catch (error) {
      toast({
        title: "Refresh failed",
        description: error instanceof Error ? error.message : "Unable to refresh dashboard data",
        variant: "destructive",
      });
    } finally {
      setRefreshingZapier(false);
    }
  };

  const runArchive = async () => {
    const days = Number(archiveDays);
    if (!Number.isFinite(days) || days <= 0) {
      toast({
        title: "Invalid days",
        description: "Enter how many days of data should be retained before archiving.",
        variant: "destructive",
      });
      return;
    }

    setArchiving(true);
    try {
      const response = await api.archive.archiveOldData(days);
      const result = response?.data ?? response;
      toast({
        title: "Archive triggered",
        description: result?.message || `Archiving data older than ${days} days.`,
      });
    } catch (error) {
      toast({
        title: "Archive failed",
        description: error instanceof Error ? error.message : "Unable to start archive job",
        variant: "destructive",
      });
    } finally {
      setArchiving(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadStoredKey();
      if (!users.length) {
        fetchUsers();
      }
    }
  }, [isOpen, loadStoredKey, fetchUsers, users.length]);

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button size="sm" variant="outline" className="gap-2">
          <Settings2 className="h-4 w-4" />
          Admin settings
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-xl flex flex-col max-h-[90vh]">
        <SheetHeader className="space-y-1">
          <SheetTitle>Admin controls</SheetTitle>
          <SheetDescription>
            Securely manage AI config, run manual analyses, and trigger maintenance jobs.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-4 overflow-y-auto pr-1">
          <div className="space-y-3 rounded-lg border p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <KeyRound className="h-4 w-4 text-primary" />
                  OpenAI API key
                </div>
                <p className="text-xs text-muted-foreground">
                  Stored client-side with Web Crypto encryption; never sent unless backend uses it explicitly.
                </p>
              </div>
              <Badge variant={hasStoredKey ? "secondary" : "outline"}>
                {hasStoredKey ? "Stored" : "Missing"}
              </Badge>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="openai-key">API key</Label>
              <div className="flex gap-2">
                <Input
                  id="openai-key"
                  type={showKey ? "text" : "password"}
                  placeholder="sk-..."
                  autoComplete="off"
                  value={openAiKeyInput}
                  onChange={(e) => setOpenAiKeyInput(e.target.value)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowKey((prev) => !prev)}
                  aria-label={showKey ? "Hide key" : "Show key"}
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              {lastSavedAt && (
                <p className="text-xs text-muted-foreground">
                  Last saved {format(new Date(lastSavedAt), "MMM d, yyyy HH:mm")}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleClearKey}
                disabled={!hasStoredKey || isSavingKey}
              >
                <Trash2 className="mr-1 h-4 w-4" />
                Forget key
              </Button>
              <Button type="button" size="sm" onClick={handleSaveKey} disabled={isSavingKey}>
                {isSavingKey && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                Save securely
              </Button>
            </div>
          </div>

          <div className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <PlayCircle className="h-4 w-4 text-primary" />
              Manual analysis
            </div>
            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label htmlFor="analysis-date">Analysis date</Label>
                <div className="flex gap-2">
                  <Input
                    id="analysis-date"
                    type="date"
                    max={format(new Date(), "yyyy-MM-dd")}
                    value={analysisDate}
                    onChange={(e) => setAnalysisDate(e.target.value)}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setAnalysisDate(format(new Date(), "yyyy-MM-dd"))}
                    aria-label="Use today"
                  >
                    <CalendarDays className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="grid gap-2">
                <Label>User to analyze</Label>
                <Select
                  value={selectedUserId}
                  onValueChange={setSelectedUserId}
                  disabled={usersLoading || !users.length}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={usersLoading ? "Loading users..." : "Select user"} />
                  </SelectTrigger>
                  <SelectContent>
                    {users.map((user) => (
                      <SelectItem key={user.id} value={user.id}>
                        {user.name || user.email || user.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Runs the per-user daily commit analysis immediately for the chosen date.
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={runUserAnalysis}
                  disabled={isRunningUserAnalysis}
                >
                  {isRunningUserAnalysis && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                  Run for user
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={runBatchAnalysis}
                  disabled={isRunningBatch}
                >
                  {isRunningBatch && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                  Run for everyone
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <ShieldCheck className="h-4 w-4 text-primary" />
              Health + maintenance
            </div>
            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">System health</p>
                <p className="text-xs text-muted-foreground">
                  Check API, OpenAI, GitHub, and circuit breaker status.
                </p>
                {healthSummary && (
                  <p className="mt-1 text-xs text-foreground">{healthSummary}</p>
                )}
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={runHealthCheck}
                disabled={checkingHealth}
              >
                {checkingHealth && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                Run check
              </Button>
            </div>

            <Separator />

            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Refresh dashboards</p>
                <p className="text-xs text-muted-foreground">
                  Re-sync KPI/Zapier data without waiting for the next schedule.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={refreshZapierData}
                disabled={refreshingZapier}
              >
                {refreshingZapier && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                <RefreshCw className="mr-1 h-4 w-4" />
                Refresh
              </Button>
            </div>

            <Separator />

            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">Archive old data</p>
                <span className="text-xs text-muted-foreground">Keeps DB lean</span>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={30}
                  value={archiveDays}
                  onChange={(e) => setArchiveDays(e.target.value)}
                  className="w-28"
                />
                <span className="text-xs text-muted-foreground">days of history to retain</span>
              </div>
              <div className="flex justify-end">
                <Button type="button" size="sm" variant="outline" onClick={runArchive} disabled={archiving}>
                  {archiving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                  Start archive
                </Button>
              </div>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};
