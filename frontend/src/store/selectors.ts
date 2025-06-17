/**
 * Advanced store selectors with memoization and computed values
 */

import { useMemo } from 'react';
import { useUserStore } from './userStore';
import { UserResponse, UserRole } from '@/types/user';

// User Selectors
export const useUserSelectors = () => {
  const {
    getUserById,
    getUsersByRole,
    getUsersByTeam,
    getTeamMembers,
    getFilteredUsers,
    getSearchResults,
    getUserStats,
    roleFilter,
    teamFilter,
    searchQuery,
    teams,
  } = useUserStore();

  // Memoized selectors
  const userStats = useMemo(() => getUserStats(), [getUserStats]);
  
  const filteredUsers = useMemo(() => getFilteredUsers(), [
    getFilteredUsers,
    roleFilter,
    teamFilter,
    searchQuery,
  ]);

  // Role distribution analysis
  const roleDistribution = useMemo(() => {
    const stats = getUserStats();
    const total = stats.total;
    
    if (total === 0) return [];

    return Object.entries(stats.byRole).map(([role, count]) => ({
      role: role as UserRole,
      count,
      percentage: Math.round((count / total) * 100),
    }));
  }, [getUserStats]);

  // Team size analysis
  const teamAnalysis = useMemo(() => {
    const teamSizes = Object.entries(teams).map(([teamId, memberIds]) => ({
      teamId,
      size: memberIds.length,
    }));

    const averageTeamSize = teamSizes.length > 0 
      ? Math.round(teamSizes.reduce((sum, team) => sum + team.size, 0) / teamSizes.length)
      : 0;

    const recommendations = [];
    const largeTeams = teamSizes.filter(team => team.size > 10);
    const smallTeams = teamSizes.filter(team => team.size < 3);

    if (largeTeams.length > 0) {
      recommendations.push(`Consider splitting large teams: ${largeTeams.map(t => t.teamId).join(', ')}`);
    }
    if (smallTeams.length > 0) {
      recommendations.push(`Consider merging small teams: ${smallTeams.map(t => t.teamId).join(', ')}`);
    }

    return {
      teamSizes,
      averageTeamSize,
      recommendations,
    };
  }, [teams]);

  return {
    // Direct selectors
    getUserById,
    getUsersByRole,
    getUsersByTeam,
    getTeamMembers,
    
    // Memoized data
    userStats,
    filteredUsers,
    roleDistribution,
    teamAnalysis,
    
    // Search results
    searchResults: searchQuery ? getSearchResults() : [],
    hasActiveFilters: !!(roleFilter || teamFilter || searchQuery),
  };
};

// Combined Cross-Store Selectors (simplified without tasks)
export const useCombinedSelectors = () => {
  const userStore = useUserStore();

  // Team metrics without task data
  const teamMetrics = useMemo(() => {
    const teams = Object.entries(userStore.teams);
    
    return teams.map(([teamId, memberIds]) => {
      const members = memberIds.map(id => userStore.getUserById(id)).filter(Boolean) as UserResponse[];
      
      return {
        teamId,
        memberCount: members.length,
        members: members.map(member => ({
          id: member.id,
          name: member.first_name + ' ' + member.last_name,
          role: member.role,
        })),
      };
    });
  }, [userStore.teams, userStore.getUserById]);

  return {
    teamMetrics,
  };
};

// Hook for dashboard-specific selectors
export const useDashboardSelectors = () => {
  const userSelectors = useUserSelectors();
  const combinedSelectors = useCombinedSelectors();

  // Dashboard-specific computed values
  const dashboardMetrics = useMemo(() => {
    const userStats = userSelectors.userStats;
    
    return {
      // Key metrics
      totalUsers: userStats.total,
      
      // Trends (would need historical data in real implementation)
      trends: {
        newUsersThisMonth: userStats.total, // Placeholder
      },
      
      // Alerts
      alerts: [
        ...(userSelectors.teamAnalysis.recommendations || []),
      ],
    };
  }, [userSelectors]);

  return {
    ...userSelectors,
    ...combinedSelectors,
    dashboardMetrics,
  };
};