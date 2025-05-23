/**
 * Advanced store selectors with memoization and computed values
 */

import { useMemo } from 'react';
import { useTaskStore } from './taskStore';
import { useUserStore } from './userStore';
import { Task, TaskStatus } from '@/types/entities';
import { UserResponse, UserRole } from '@/types/user';

// Task Selectors
export const useTaskSelectors = () => {
  const {
    getTaskById,
    getTasksByStatus,
    getTasksByAssignee,
    getTasksByPriority,
    getOverdueTasks,
    getTasksDueToday,
    getTasksDueThisWeek,
    getFilteredTasks,
    getSearchResults,
    getUserTaskStats,
    getTaskStats,
    statusFilter,
    assigneeFilter,
    dueDateFilter,
    priorityFilter,
    searchQuery,
  } = useTaskStore();

  // Memoized selectors for performance
  const taskStats = useMemo(() => getTaskStats(), [getTaskStats]);
  
  const filteredTasks = useMemo(() => getFilteredTasks(), [
    getFilteredTasks,
    statusFilter,
    assigneeFilter,
    dueDateFilter,
    priorityFilter,
    searchQuery,
  ]);

  const overdueTasks = useMemo(() => getOverdueTasks(), [getOverdueTasks]);
  const tasksDueToday = useMemo(() => getTasksDueToday(), [getTasksDueToday]);
  const tasksDueThisWeek = useMemo(() => getTasksDueThisWeek(), [getTasksDueThisWeek]);

  // Task priority analysis
  const taskPriorityAnalysis = useMemo(() => {
    const stats = getTaskStats();
    const total = stats.total;
    
    if (total === 0) return { distribution: {}, recommendations: [] };

    const distribution = Object.entries(stats.byPriority).map(([priority, count]) => ({
      priority,
      count,
      percentage: Math.round((count / total) * 100),
    }));

    const recommendations = [];
    const highPriorityCount = stats.byPriority['high'] || 0;
    const highPriorityPercentage = (highPriorityCount / total) * 100;

    if (highPriorityPercentage > 30) {
      recommendations.push('Consider reducing high-priority tasks to improve focus');
    }
    if (stats.overdue > 0) {
      recommendations.push(`Address ${stats.overdue} overdue tasks immediately`);
    }

    return { distribution, recommendations };
  }, [getTaskStats]);

  return {
    // Direct selectors
    getTaskById,
    getTasksByStatus,
    getTasksByAssignee,
    getTasksByPriority,
    getUserTaskStats,
    
    // Memoized data
    taskStats,
    filteredTasks,
    overdueTasks,
    tasksDueToday,
    tasksDueThisWeek,
    taskPriorityAnalysis,
    
    // Search results
    searchResults: searchQuery ? getSearchResults() : [],
    hasActiveFilters: !!(statusFilter || assigneeFilter || dueDateFilter || priorityFilter || searchQuery),
  };
};

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

// Combined Cross-Store Selectors
export const useCombinedSelectors = () => {
  const taskStore = useTaskStore();
  const userStore = useUserStore();

  // User workload analysis
  const userWorkloadAnalysis = useMemo(() => {
    const users = userStore.getFilteredUsers();
    const workloads = users.map(user => {
      const stats = taskStore.getUserTaskStats(user.id);
      const workloadScore = calculateWorkloadScore(stats);
      
      return {
        user,
        stats,
        workloadScore,
        status: getWorkloadStatus(workloadScore),
      };
    });

    // Sort by workload score (highest first)
    workloads.sort((a, b) => b.workloadScore - a.workloadScore);

    return workloads;
  }, [taskStore.getUserTaskStats, userStore.getFilteredUsers]);

  // Team performance metrics
  const teamPerformanceMetrics = useMemo(() => {
    const teams = Object.entries(userStore.teams);
    
    return teams.map(([teamId, memberIds]) => {
      const members = memberIds.map(id => userStore.getUserById(id)).filter(Boolean) as UserResponse[];
      
      let totalTasks = 0;
      let completedTasks = 0;
      let overdueTasks = 0;
      
      members.forEach(member => {
        const stats = taskStore.getUserTaskStats(member.id);
        totalTasks += stats.total;
        completedTasks += stats.byStatus[TaskStatus.DONE] || 0;
        overdueTasks += stats.overdue;
      });

      const completionRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;
      const overdueRate = totalTasks > 0 ? Math.round((overdueTasks / totalTasks) * 100) : 0;

      return {
        teamId,
        memberCount: members.length,
        totalTasks,
        completedTasks,
        overdueTasks,
        completionRate,
        overdueRate,
        performanceScore: calculateTeamPerformanceScore(completionRate, overdueRate),
      };
    });
  }, [userStore.teams, userStore.getUserById, taskStore.getUserTaskStats]);

  // Task assignment recommendations
  const taskAssignmentRecommendations = useMemo(() => {
    const workloads = userWorkloadAnalysis;
    const underutilized = workloads.filter(w => w.status === 'light');
    const overloaded = workloads.filter(w => w.status === 'heavy' || w.status === 'critical');

    const recommendations = [];

    if (overloaded.length > 0 && underutilized.length > 0) {
      overloaded.forEach(overloadedUser => {
        const suitableAssignees = underutilized
          .filter(u => u.user.role === overloadedUser.user.role || canHandleRole(u.user.role, overloadedUser.user.role))
          .slice(0, 2);

        if (suitableAssignees.length > 0) {
          recommendations.push({
            type: 'redistribute',
            from: overloadedUser.user,
            to: suitableAssignees.map(u => u.user),
            reason: `${overloadedUser.user.first_name} has ${overloadedUser.stats.total} tasks (${overloadedUser.stats.overdue} overdue)`,
          });
        }
      });
    }

    return recommendations;
  }, [userWorkloadAnalysis]);

  return {
    userWorkloadAnalysis,
    teamPerformanceMetrics,
    taskAssignmentRecommendations,
  };
};

// Helper functions
function calculateWorkloadScore(stats: ReturnType<typeof useTaskStore.getState>['getUserTaskStats']): number {
  const { total, overdue, byStatus } = stats;
  const inProgress = byStatus[TaskStatus.IN_PROGRESS] || 0;
  const open = byStatus[TaskStatus.OPEN] || 0;
  const assigned = byStatus[TaskStatus.ASSIGNED] || 0;
  
  // Weighted scoring: overdue tasks have highest impact
  return (overdue * 3) + (inProgress * 2) + ((open + assigned) * 1);
}

function getWorkloadStatus(score: number): 'light' | 'moderate' | 'heavy' | 'critical' {
  if (score >= 20) return 'critical';
  if (score >= 12) return 'heavy';
  if (score >= 6) return 'moderate';
  return 'light';
}

function calculateTeamPerformanceScore(completionRate: number, overdueRate: number): number {
  // Performance score: completion rate minus penalty for overdue tasks
  return Math.max(0, completionRate - (overdueRate * 2));
}

function canHandleRole(assigneeRole: UserRole, taskOwnerRole: UserRole): boolean {
  // Role hierarchy: ADMIN > MANAGER > DEVELOPER > USER
  const roleHierarchy = {
    [UserRole.ADMIN]: 4,
    [UserRole.MANAGER]: 3,
    [UserRole.DEVELOPER]: 2,
    [UserRole.USER]: 1,
  };

  return roleHierarchy[assigneeRole] >= roleHierarchy[taskOwnerRole];
}

// Hook for dashboard-specific selectors
export const useDashboardSelectors = () => {
  const taskSelectors = useTaskSelectors();
  const userSelectors = useUserSelectors();
  const combinedSelectors = useCombinedSelectors();

  // Dashboard-specific computed values
  const dashboardMetrics = useMemo(() => {
    const taskStats = taskSelectors.taskStats;
    const userStats = userSelectors.userStats;
    
    return {
      // Key metrics
      totalTasks: taskStats.total,
      totalUsers: userStats.total,
      completionRate: taskStats.total > 0 
        ? Math.round(((taskStats.byStatus[TaskStatus.DONE] || 0) / taskStats.total) * 100)
        : 0,
      overdueCount: taskStats.overdue,
      
      // Trends (would need historical data in real implementation)
      trends: {
        tasksCreatedThisWeek: taskStats.total, // Placeholder
        tasksCompletedThisWeek: taskStats.byStatus[TaskStatus.DONE] || 0,
        newUsersThisMonth: userStats.total, // Placeholder
      },
      
      // Alerts
      alerts: [
        ...(taskStats.overdue > 0 ? [`${taskStats.overdue} overdue tasks need attention`] : []),
        ...(taskSelectors.taskPriorityAnalysis.recommendations || []),
        ...(userSelectors.teamAnalysis.recommendations || []),
      ],
    };
  }, [taskSelectors, userSelectors]);

  return {
    ...taskSelectors,
    ...userSelectors,
    ...combinedSelectors,
    dashboardMetrics,
  };
};