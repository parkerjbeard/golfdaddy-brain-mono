
import React from 'react';
import { cn } from "@/lib/utils";
import { Notification } from "@/types/notifications";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface NotificationItemProps {
  notification: Notification;
  onDismiss: (id: string) => void;
}

export const NotificationItem = ({ notification, onDismiss }: NotificationItemProps) => {
  const { id, title, message, createdAt, read } = notification;
  
  return (
    <div className={cn(
      "p-4 border-b last:border-b-0 relative",
      !read && "bg-muted/40"
    )}>
      <div className="pr-6">
        <h4 className="text-sm font-medium">{title}</h4>
        <p className="text-xs text-muted-foreground mt-1">{message}</p>
        <time className="text-xs text-muted-foreground mt-1 block">
          {new Date(createdAt).toLocaleString()}
        </time>
      </div>
      <Button 
        variant="ghost" 
        size="icon" 
        className="absolute top-2 right-2 h-6 w-6" 
        onClick={() => onDismiss(id)}
      >
        <X className="h-3 w-3" />
        <span className="sr-only">Dismiss</span>
      </Button>
    </div>
  );
};
