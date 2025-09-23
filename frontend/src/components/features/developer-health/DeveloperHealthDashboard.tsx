import React, { useState, useEffect, useCallback } from 'react';
import { getDeveloperDailySummary, DeveloperDailySummary } from '@/services/developerInsightsApi';
import api from '@/services/api';
import DailySummaryCard from './DailySummaryCard';
import CommitList from './CommitList';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { format, subDays } from 'date-fns'; // For date formatting and default value

import { useAuth } from '@/contexts/AuthContext'; 

interface User {
  id: string;
  name: string;
}

const DeveloperHealthDashboard: React.FC = () => {
  const { session } = useAuth();
  const token = session?.access_token || null;

  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(
    format(subDays(new Date(), 1), 'yyyy-MM-dd') // Default to yesterday
  );
  const [summaryData, setSummaryData] = useState<DeveloperDailySummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  // Fetch users on mount
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const fetchedUsers = await api.users.getUsers();
        setUsers(fetchedUsers);
        // Select the first user by default if available
        if (fetchedUsers.length > 0 && !selectedUserId) {
          setSelectedUserId(fetchedUsers[0].id);
        }
      } catch (err) {
        console.error("Failed to fetch users:", err);
        setError(err instanceof Error ? err : new Error("Failed to load users"));
      }
    };
    fetchUsers();
  }, [token]); // Rerun if token changes

  // Fetch summary data when user or date changes
  const fetchSummary = useCallback(async () => {
    if (!selectedUserId || !selectedDate) {
      setSummaryData(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    setSummaryData(null); // Clear previous data

    try {
      const data = await getDeveloperDailySummary(selectedUserId, selectedDate, token);
      setSummaryData(data);
    } catch (err) {
      console.error("Fetch summary error:", err);
      setError(err instanceof Error ? err : new Error("Failed to load summary data"));
    } finally {
      setIsLoading(false);
    }
  }, [selectedUserId, selectedDate, token]);

  // Trigger fetch on initial load or when dependencies change
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-2xl font-bold">Developer Daily Health</h1>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4 p-4 border rounded-lg bg-card text-card-foreground">
        {/* User Select */}
        <div className="flex-1 min-w-[200px]">
          <Label htmlFor="user-select">Developer</Label>
          <Select 
            value={selectedUserId || ""} 
            onValueChange={setSelectedUserId}
            disabled={users.length === 0}
          >
            <SelectTrigger id="user-select">
              <SelectValue placeholder="Select developer..." />
            </SelectTrigger>
            <SelectContent>
              {users.map((user) => (
                <SelectItem key={user.id} value={user.id}>
                  {user.name}
                </SelectItem>
              ))}
              {users.length === 0 && <SelectItem value="loading" disabled>Loading...</SelectItem>}
            </SelectContent>
          </Select>
        </div>

        {/* Date Select */}
        <div className="flex-1 min-w-[150px]">
          <Label htmlFor="date-select">Date</Label>
          <Input
            id="date-select"
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={format(new Date(), 'yyyy-MM-dd')} // Don't allow future dates
          />
        </div>

        {/* Refresh Button (optional) */}
        {/* <Button onClick={fetchSummary} disabled={isLoading || !selectedUserId}>
          {isLoading ? 'Loading...' : 'Refresh'}
        </Button> */}
      </div>

      {/* Display Area */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Summary Card */}
        <div className="md:col-span-1">
          <DailySummaryCard summary={summaryData} isLoading={isLoading} error={error} />
        </div>

        {/* Commit List */}
        <div className="md:col-span-2">
           <CommitList 
             commits={summaryData?.individual_commits || []} 
             isLoading={isLoading && !summaryData} // Show loading state only when overall data is loading
            />
        </div>
      </div>
    </div>
  );
};

export default DeveloperHealthDashboard; 
