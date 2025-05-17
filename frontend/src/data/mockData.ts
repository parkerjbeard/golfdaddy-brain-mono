import { Team, User } from '@/types'

export const mockUsers: User[] = [
  { id: '1', name: 'Alice Smith' },
  { id: '2', name: 'Bob Johnson' },
  { id: '3', name: 'Charlie Rose' },
]

export const mockTeams: Team[] = [
  { id: 'team-1', name: 'Developers', members: [mockUsers[0]] },
  { id: 'team-2', name: 'Designers', members: [mockUsers[1]] },
]
