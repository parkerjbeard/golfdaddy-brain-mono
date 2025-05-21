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
import { getUsers as fetchUsers } from "@/lib/apiService";

interface UserSelectorProps {
  selectedUser?: User | null;
  onSelectUser: (user: User | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
}

export function UserSelector({
  selectedUser,
  onSelectUser,
  placeholder = "Select user...",
  disabled = false,
  className,
  id
}: UserSelectorProps) {
  const [open, setOpen] = React.useState(false);
  const [users, setUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function loadUsers() {
      setLoading(true);
      setError(null);
      try {
        const fetchedUsers = await fetchUsers(null);
        setUsers(fetchedUsers);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load users");
        console.error("UserSelector error:", err);
      }
      setLoading(false);
    }
    loadUsers();
  }, []);

  const handleSelect = (currentValue: string) => {
    const user = users.find(
      (u) => u.name.toLowerCase() === currentValue.toLowerCase()
    );
    onSelectUser(user || null);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild id={id}>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("w-full justify-between", className)}
          disabled={disabled || loading}
        >
          {selectedUser
            ? selectedUser.name
            : loading ? "Loading users..." : error ? "Error loading" : placeholder}
          <CaretSortIcon className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
        <Command>
          <CommandInput placeholder={error ? "Could not load" : "Search user..."} className="h-9" disabled={loading || !!error}/>
          {!error && !loading && <CommandEmpty>No user found.</CommandEmpty>}
          {error && <CommandEmpty>{error}</CommandEmpty>}
          {loading && !error && <CommandEmpty>Loading...</CommandEmpty>}
          {!loading && !error && (
            <CommandList>
              <CommandGroup>
                {users.map((user) => (
                  <CommandItem
                    key={user.id}
                    value={user.name} // Use user.name for matching in Command; ensure names are unique or use ID and display name
                    onSelect={handleSelect}
                  >
                    {user.name}
                    {selectedUser?.id === user.id && (
                      <CheckIcon className="ml-auto h-4 w-4" />
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          )}
        </Command>
      </PopoverContent>
    </Popover>
  );
} 