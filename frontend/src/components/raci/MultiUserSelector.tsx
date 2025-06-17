import * as React from "react";
import { CaretSortIcon, Cross2Icon } from "@radix-ui/react-icons";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { User } from "@/types/entities";

interface MultiUserSelectorProps {
  selectedUsers: User[];
  onSelectedUsersChange: (users: User[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
  allUsersList: User[];
  isLoading: boolean;
  error: string | null;
}

export function MultiUserSelector({
  selectedUsers,
  onSelectedUsersChange,
  placeholder = "Select users...",
  disabled = false,
  className,
  id,
  allUsersList,
  isLoading,
  error,
}: MultiUserSelectorProps) {
  const [open, setOpen] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleSelect = (currentValue: string) => {
    const user = allUsersList.find(
      (u) => u.name?.toLowerCase() === currentValue.toLowerCase()
    );
    if (user && user.name && !selectedUsers.find(su => su.id === user.id)) {
      onSelectedUsersChange([...selectedUsers, user]);
    }
    inputRef.current?.focus();
  };

  const handleRemoveUser = (userIdToRemove: string) => {
    onSelectedUsersChange(selectedUsers.filter(user => user.id !== userIdToRemove));
  };

  const availableUsers = allUsersList.filter(u => u.name && !selectedUsers.find(su => su.id === u.id));
  
  let buttonPlaceholderText = placeholder;
  if (isLoading) {
    buttonPlaceholderText = "Loading...";
  } else if (error) {
    buttonPlaceholderText = "Error loading users";
  }

  return (
    <div className={cn("group", className)} id={id}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between h-auto min-h-[2.25rem] items-start"
            disabled={disabled || isLoading || !!error}
            onClick={() => setOpen(!open)}
          >
            <div className="flex flex-wrap gap-1 items-center flex-grow">
              {selectedUsers.length === 0 && buttonPlaceholderText}
              {selectedUsers.map(user => (
                <Badge
                  variant="secondary"
                  key={user.id}
                  className="py-0.5 px-2 flex items-center gap-1"
                  onClick={(e) => { e.stopPropagation(); handleRemoveUser(user.id); }}
                >
                  {user.name || "Unnamed user"}
                  <Cross2Icon className="h-3 w-3 text-muted-foreground hover:text-foreground cursor-pointer" />
                </Badge>
              ))}
            </div>
            <CaretSortIcon className="ml-2 h-4 w-4 shrink-0 opacity-50 self-center" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
          <Command>
            <CommandInput 
              ref={inputRef}
              placeholder={isLoading ? "Loading..." : error ? "Error" : "Search users..."} 
              className="h-9" 
              disabled={isLoading || !!error}
            />
            {isLoading && <CommandEmpty>Loading...</CommandEmpty>}
            {error && <CommandEmpty>{error}</CommandEmpty>}
            {!isLoading && !error && (
              <>
                {availableUsers.length === 0 && selectedUsers.length > 0 && <CommandEmpty>All users selected or no more users.</CommandEmpty>}
                {availableUsers.length === 0 && selectedUsers.length === 0 && <CommandEmpty>No users found.</CommandEmpty>}
                {availableUsers.length > 0 && (
                  <CommandList>
                    <CommandGroup>
                      {availableUsers.map((user) => (
                        <CommandItem
                          key={user.id}
                          value={user.name || ''}
                          onSelect={() => {
                            const selectedUserObject = allUsersList.find(u => u.id === user.id);
                            handleSelect(selectedUserObject ? selectedUserObject.name || '' : '');
                          }}
                          className="cursor-pointer"
                          disabled={!user.name}
                        >
                          {user.name || "Unnamed user"}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                )}
              </>
            )}
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
} 