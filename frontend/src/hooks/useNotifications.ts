import { Notification } from '@/types/notifications'
import { create } from 'zustand'
import { toast } from '@/hooks/use-toast'

// Mock notifications for demo purposes
const mockNotifications: Notification[] = [
  {
    id: '1',
    title: 'New Project Assigned',
    message: 'You have been assigned to the Q3 Marketing Campaign.',
    createdAt: new Date(Date.now() - 3600000).toISOString(),
    read: false,
  },
  {
    id: '2',
    title: 'Performance Review',
    message: 'Your quarterly performance review is scheduled for next week.',
    createdAt: new Date(Date.now() - 86400000).toISOString(),
    read: false,
  },
  {
    id: '3',
    title: 'System Maintenance',
    message: 'The system will be down for maintenance this Saturday from 2-4 AM.',
    createdAt: new Date(Date.now() - 172800000).toISOString(),
    read: true,
  },
]

interface NotificationState {
  notifications: Notification[]
  unreadCount: number
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  dismissNotification: (id: string) => void
  addNotification: (notification: Omit<Notification, 'id' | 'createdAt'>) => void
}

export const useNotifications = create<NotificationState>((set, get) => ({
  notifications: mockNotifications,
  unreadCount: mockNotifications.filter((n) => !n.read).length,
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
  addNotification: (notification) =>
    set((state) => {
      const newNotification: Notification = {
        ...notification,
        id: Date.now().toString(),
        createdAt: new Date().toISOString(),
        read: false,
      }
      toast({
        title: 'New notification',
        description: notification.title,
      })
      return {
        notifications: [newNotification, ...state.notifications],
        unreadCount: state.unreadCount + 1,
      }
    }),
}))
