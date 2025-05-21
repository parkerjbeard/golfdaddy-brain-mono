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
import { getUsers as fetchUsers } from "@/lib/apiService";

interface MultiUserSelectorProps {
  selectedUsers: User[];
  onSelectedUsersChange: (users: User[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
}

export function MultiUserSelector({
  selectedUsers,
  onSelectedUsersChange,
  placeholder = "Select users...",
  disabled = false,
  className,
  id
}: MultiUserSelectorProps) {
  const [open, setOpen] = React.useState(false);
  const [allUsers, setAllUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    async function loadUsers() {
      setLoading(true);
      setError(null);
      try {
        const fetchedUsers = await fetchUsers(null);
        setAllUsers(fetchedUsers);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load users");
        console.error("MultiUserSelector error:", err);
      }
      setLoading(false);
    }
    loadUsers();
  }, []);

  const handleSelect = (currentValue: string) => {
    const user = allUsers.find(
      (u) => u.name.toLowerCase() === currentValue.toLowerCase()
    );
    if (user && !selectedUsers.find(su => su.id === user.id)) {
      onSelectedUsersChange([...selectedUsers, user]);
    }
    // Keep popover open for multi-select or close, depending on UX preference
    // setOpen(false); 
    inputRef.current?.focus(); // Keep focus in input for further selections
  };

  const handleRemoveUser = (userIdToRemove: string) => {
    onSelectedUsersChange(selectedUsers.filter(user => user.id !== userIdToRemove));
  };

  const availableUsers = allUsers.filter(u => !selectedUsers.find(su => su.id === u.id));

  return (
    <div className={cn("group", className)} id={id}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between h-auto min-h-[2.25rem] items-start"
            disabled={disabled || loading}
            onClick={() => setOpen(!open)}
          >
            <div className="flex flex-wrap gap-1 items-center flex-grow">
              {selectedUsers.length === 0 && (loading ? "Loading..." : error ? "Error" : placeholder)}
              {selectedUsers.map(user => (
                <Badge
                  variant="secondary"
                  key={user.id}
                  className="py-0.5 px-2 flex items-center gap-1"
                  onClick={(e) => { e.stopPropagation(); handleRemoveUser(user.id); }}
                >
                  {user.name}
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
              placeholder={error ? "Could not load" : "Search users..."} 
              className="h-9" 
              disabled={loading || !!error}
            />
            {!error && !loading && availableUsers.length === 0 && selectedUsers.length > 0 && <CommandEmpty>All users selected or no more users.</CommandEmpty>}
            {!error && !loading && availableUsers.length === 0 && selectedUsers.length === 0 && <CommandEmpty>No users found.</CommandEmpty>}
            {error && <CommandEmpty>{error}</CommandEmpty>}
            {loading && !error && <CommandEmpty>Loading...</CommandEmpty>}
            {!loading && !error && (
              <CommandList>
                <CommandGroup>
                  {availableUsers.map((user) => (
                    <CommandItem
                      key={user.id}
                      value={user.name} // Use user.name for matching
                      onSelect={handleSelect}
                      className="cursor-pointer"
                    >
                      {user.name}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            )}
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
} 