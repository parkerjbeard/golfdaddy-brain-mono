
import { useState, useEffect, useCallback } from 'react';
import { Notification } from '@/types/notifications';
import { toast } from "@/hooks/use-toast";

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
];

export const useNotifications = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Load notifications (in a real app, this would fetch from an API)
  useEffect(() => {
    setNotifications(mockNotifications);
    setUnreadCount(mockNotifications.filter(notif => !notif.read).length);
  }, []);

  // Mark a notification as read
  const markAsRead = useCallback((id: string) => {
    setNotifications(prev => 
      prev.map(notif => 
        notif.id === id ? { ...notif, read: true } : notif
      )
    );
    
    // Update unread count
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, []);

  // Mark all notifications as read
  const markAllAsRead = useCallback(() => {
    setNotifications(prev => 
      prev.map(notif => ({ ...notif, read: true }))
    );
    setUnreadCount(0);
  }, []);

  // Dismiss a notification
  const dismissNotification = useCallback((id: string) => {
    const notification = notifications.find(n => n.id === id);
    setNotifications(prev => prev.filter(notif => notif.id !== id));
    
    // If we're removing an unread notification, update count
    if (notification && !notification.read) {
      setUnreadCount(prev => Math.max(0, prev - 1));
    }

    toast({
      title: "Notification dismissed",
      description: "The notification has been removed.",
    });
  }, [notifications]);

  // Get a new notification (simulated)
  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'createdAt'>) => {
    const newNotification: Notification = {
      ...notification,
      id: Date.now().toString(),
      createdAt: new Date().toISOString(),
    };
    
    setNotifications(prev => [newNotification, ...prev]);
    setUnreadCount(prev => prev + 1);
    
    toast({
      title: "New notification",
      description: notification.title,
    });
  }, []);

  return {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    dismissNotification,
    addNotification,
  };
};
