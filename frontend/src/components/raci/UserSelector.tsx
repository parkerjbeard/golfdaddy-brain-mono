import * as React from "react";
import { CaretSortIcon, CheckIcon } from "@radix-ui/react-icons";
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
import { User } from "@/types/entities";

interface UserSelectorProps {
  selectedUser?: User | null;
  onSelectUser: (user: User | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
  allUsersList: User[];
  isLoading: boolean;
  error: string | null;
}

export function UserSelector({
  selectedUser,
  onSelectUser,
  placeholder = "Select user...",
  disabled = false,
  className,
  id,
  allUsersList,
  isLoading,
  error,
}: UserSelectorProps) {
  const [open, setOpen] = React.useState(false);

  const handleSelect = (currentValue: string) => {
    const user = allUsersList.find(
      (u) => u.name.toLowerCase() === currentValue.toLowerCase()
    );
    onSelectUser(user || null);
    setOpen(false);
  };

  let buttonText = placeholder;
  if (isLoading) {
    buttonText = "Loading users...";
  } else if (error) {
    buttonText = "Error loading users";
  } else if (selectedUser) {
    buttonText = selectedUser.name;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild id={id}>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("w-full justify-between", className)}
          disabled={disabled || isLoading || !!error}
        >
          {buttonText}
          <CaretSortIcon className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0 border-0">
        <Command>
          <CommandInput 
            placeholder={isLoading ? "Loading..." : error ? "Error" : "Search user..."} 
            className="h-9 focus:ring-0" 
            disabled={isLoading || !!error}
          />
          {isLoading && <CommandEmpty>Loading...</CommandEmpty>}
          {error && <CommandEmpty>{error}</CommandEmpty>}
          {!isLoading && !error && (
            <>
              {allUsersList.length === 0 ? (
                <CommandEmpty>No users found.</CommandEmpty>
              ) : (
                <CommandList>
                  <CommandGroup>
                    {allUsersList.map((user) => (
                      <CommandItem
                        key={user.id}
                        value={user.name || ''}
                        onSelect={() => {
                          const selectedUserObject = allUsersList.find(u => u.id === user.id);
                          handleSelect(selectedUserObject ? selectedUserObject.name || '' : '');
                        }}
                        disabled={!user.name}
                      >
                        {user.name || "Unnamed user"} 
                        {selectedUser?.id === user.id && (
                          <CheckIcon className="ml-auto h-4 w-4" />
                        )}
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
  );
} 