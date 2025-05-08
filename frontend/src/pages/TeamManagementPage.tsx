import React from 'react';
import TeamList from '@/components/TeamList';
import AddTeamModal from '@/components/AddTeamModal';
import { mockTeams, mockUsers } from '@/data/mockData'; // Import mock data
import { Team, User } from '@/types';

const TeamManagementPage: React.FC = () => {
  const [teams, setTeams] = React.useState<Team[]>(mockTeams);
  const [users, setUsers] = React.useState<User[]>(mockUsers);
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);

  const handleAddTeam = (teamName: string) => {
    const newTeam: Team = {
      id: String(Date.now()), // Simple ID generation
      name: teamName,
      members: [],
    };
    setTeams(prevTeams => [...prevTeams, newTeam]);
  };

  const handleAssignUserToTeam = (userId: string, teamId: string | null) => {
    // Update user's teamId
    setUsers(prevUsers =>
      prevUsers.map(user =>
        user.id === userId ? { ...user, teamId: teamId ?? undefined } : user
      )
    );

    // Update team members
    setTeams(prevTeams =>
      prevTeams.map(team => {
        const userToMove = users.find(u => u.id === userId);
        if (!userToMove) return team;

        // Add to new team if this is the target team
        if (team.id === teamId && !team.members.some(m => m.id === userId)) {
          return { ...team, members: [...team.members, userToMove] };
        }
        // Remove from this team if it's not the target team but contains the user
        if (team.id !== teamId && team.members.some(m => m.id === userId)) {
          return { ...team, members: team.members.filter(member => member.id !== userId) };
        }
        return team;
      })
    );
  };

  const handleAddTeamMember = (teamId: string, userId: string) => {
    handleAssignUserToTeam(userId, teamId);
  };

  const handleRemoveTeamMember = (teamId: string, userId: string) => {
    // When removing, we set the teamId to null for the user
    handleAssignUserToTeam(userId, null);
    // The team membership will be updated by handleAssignUserToTeam through the user's teamId change
  };

  return (
    <div className="container mx-auto p-4 bg-gray-50 min-h-screen">
      <header className="mb-8 flex justify-between items-center">
        <h1 className="text-4xl font-bold text-gray-800">Team Management</h1>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-semibold py-3 px-6 rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-0.5 transition duration-300 ease-in-out"
        >
          Create New Team
        </button>
      </header>

      <TeamList
        teams={teams}
        users={users} // Pass all users for selection logic in TeamCard
        onAssignUser={handleAssignUserToTeam} // This prop might be redundant if handled by add/remove
        onAddTeamMember={handleAddTeamMember}
        onRemoveTeamMember={handleRemoveTeamMember}
      />

      {isAddModalOpen && (
        <AddTeamModal
          onClose={() => setIsAddModalOpen(false)}
          onAddTeam={handleAddTeam}
        />
      )}
    </div>
  );
};

export default TeamManagementPage; 