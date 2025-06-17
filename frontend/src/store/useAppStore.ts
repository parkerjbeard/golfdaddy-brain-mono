import { create } from 'zustand'
import { Notification } from '@/types/notifications'
import { Team, User } from '@/types'
import { toast } from '@/hooks/use-toast'

interface AppState {
  notifications: Notification[]
  unreadCount: number
  teams: Team[]
  users: User[]
  setTeams: (teams: Team[]) => void
  setUsers: (users: User[]) => void
  addTeam: (name: string) => void
  assignUserToTeam: (userId: string, teamId: string | null) => void
  addNotification: (notification: Omit<Notification, 'id' | 'createdAt'>) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  dismissNotification: (id: string) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  teams: [],
  users: [],
  setTeams: (teams) => set({ teams }),
  setUsers: (users) => set({ users }),
  addTeam: (name) =>
    set((state) => ({
      teams: [
        ...state.teams,
        { id: Date.now().toString(), name, members: [] },
      ],
    })),
  assignUserToTeam: (userId, teamId) =>
    set((state) => {
      const user = state.users.find((u) => u.id === userId)
      if (!user) return state
      const updatedUsers = state.users.map((u) =>
        u.id === userId ? { ...u, teamId: teamId ?? undefined } : u
      )
      const updatedTeams = state.teams.map((team) => ({
        ...team,
        members: team.members.filter((m) => m.id !== userId),
      }))
      if (teamId) {
        const idx = updatedTeams.findIndex((t) => t.id === teamId)
        if (idx >= 0) {
          updatedTeams[idx] = {
            ...updatedTeams[idx],
            members: [...updatedTeams[idx].members, user],
          }
        }
      }
      return { users: updatedUsers, teams: updatedTeams }
    }),
  addNotification: (notification) =>
    set((state) => {
      const newNotification: Notification = {
        ...notification,
        id: Date.now().toString(),
        createdAt: new Date().toISOString(),
        read: false,
      }
      toast({ title: 'New notification', description: notification.title })
      return {
        notifications: [newNotification, ...state.notifications],
        unreadCount: state.unreadCount + 1,
      }
    }),
  markAsRead: (id) =>
    set((state) => {
      const notifications = state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      )
      return {
        notifications,
        unreadCount: notifications.filter((n) => !n.read).length,
      }
    }),
  markAllAsRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    })),
  dismissNotification: (id) =>
    set((state) => {
      const notification = state.notifications.find((n) => n.id === id)
      const notifications = state.notifications.filter((n) => n.id !== id)
      const unreadCount = notifications.filter((n) => !n.read).length
      if (notification) {
        toast({
          title: 'Notification dismissed',
          description: 'The notification has been removed.',
        })
      }
      return { notifications, unreadCount }
    }),
}))
