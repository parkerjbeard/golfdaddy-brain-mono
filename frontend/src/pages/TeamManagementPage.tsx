import React, { useEffect } from 'react';
import TeamList from '@/components/TeamList';
import AddTeamModal from '@/components/AddTeamModal';
import { mockTeams, mockUsers } from '@/data/mockData';
import { useAppStore } from '@/store/useAppStore';

const TeamManagementPage: React.FC = () => {
  const {
    teams,
    users,
    setTeams,
    setUsers,
    addTeam,
    assignUserToTeam,
  } = useAppStore();
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);

  // initialize mock data once
  useEffect(() => {
    if (teams.length === 0 && users.length === 0) {
      setTeams(mockTeams);
      setUsers(mockUsers);
    }
  }, [teams.length, users.length, setTeams, setUsers]);

  const handleAddTeam = (teamName: string) => {
    addTeam(teamName)
  };

  const handleAssignUserToTeam = (userId: string, teamId: string | null) => {
    assignUserToTeam(userId, teamId)
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