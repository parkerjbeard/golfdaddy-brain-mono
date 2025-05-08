import React from 'react';
import TeamCard from './TeamCard'; // Assuming TeamCard component in the same directory
import { Team, User } from '@/types'; // Assuming types are in @/types

interface TeamListProps {
  teams: Team[];
  users: User[]; // All users, for assigning to teams
  onAssignUser: (userId: string, teamId: string | null) => void;
  onAddTeamMember: (teamId: string, userId: string) => void;
  onRemoveTeamMember: (teamId: string, userId: string) => void;
}

const TeamList: React.FC<TeamListProps> = ({ teams, users, onAssignUser, onAddTeamMember, onRemoveTeamMember }) => {
  if (!teams.length) {
    return <p className="text-center text-gray-500">No teams created yet. Click "Create New Team" to get started.</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {teams.map(team => (
        <TeamCard
          key={team.id}
          team={team}
          allUsers={users} // Pass all users to TeamCard for the dropdown
          onAssignUser={onAssignUser} // This might be handled within TeamCard or passed down further
          onAddTeamMember={onAddTeamMember}
          onRemoveTeamMember={onRemoveTeamMember}
        />
      ))}
    </div>
  );
};

export default TeamList; 