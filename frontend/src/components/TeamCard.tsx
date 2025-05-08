import React, { useState } from 'react';
import { Team, User } from '@/types';

interface TeamCardProps {
  team: Team;
  allUsers: User[];
  onAssignUser: (userId: string, teamId: string | null) => void;
  onAddTeamMember: (teamId: string, userId: string) => void;
  onRemoveTeamMember: (teamId: string, userId: string) => void;
}

const TeamCard: React.FC<TeamCardProps> = ({ team, allUsers, onAddTeamMember, onRemoveTeamMember }) => {
  const [selectedUser, setSelectedUser] = useState<string>('');

  const availableUsers = allUsers.filter(user => !team.members.some(member => member.id === user.id) && !user.teamId);

  const handleAddMember = () => {
    if (selectedUser) {
      onAddTeamMember(team.id, selectedUser);
      setSelectedUser(''); // Reset dropdown
    }
  };

  return (
    <div className="bg-white shadow-lg rounded-lg p-6 transform hover:scale-105 transition-transform duration-300">
      <h3 className="text-xl font-semibold text-gray-700 mb-3">{team.name}</h3>
      
      <div className="mb-4">
        <h4 className="text-md font-medium text-gray-600 mb-2">Members ({team.members.length}):</h4>
        {team.members.length > 0 ? (
          <ul className="list-disc list-inside pl-4 space-y-1">
            {team.members.map(member => (
              <li key={member.id} className="text-sm text-gray-700 flex justify-between items-center">
                {member.name}
                <button 
                  onClick={() => onRemoveTeamMember(team.id, member.id)}
                  className="text-red-500 hover:text-red-700 text-xs ml-2"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500 italic">No members yet.</p>
        )}
      </div>

      {availableUsers.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-md font-medium text-gray-600 mb-2">Add Member:</h4>
          <div className="flex space-x-2">
            <select 
              value={selectedUser}
              onChange={(e) => setSelectedUser(e.target.value)}
              className="block w-full p-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="" disabled>Select a user</option>
              {availableUsers.map(user => (
                <option key={user.id} value={user.id}>{user.name}</option>
              ))}
            </select>
            <button 
              onClick={handleAddMember}
              disabled={!selectedUser}
              className="px-4 py-2 bg-indigo-500 text-white rounded-md hover:bg-indigo-600 disabled:bg-gray-300 transition duration-150 ease-in-out"
            >
              Add
            </button>
          </div>
        </div>
      )}
       {availableUsers.length === 0 && team.members.length > 0 && (
        <p className="text-sm text-gray-400 mt-4 pt-4 border-t border-gray-200">All available users are in this team.</p>
      )}
      {availableUsers.length === 0 && team.members.length === 0 && allUsers.filter(u => !u.teamId).length === 0 && (
         <p className="text-sm text-gray-400 mt-4 pt-4 border-t border-gray-200">No unassigned users available to add.</p>
      )}
    </div>
  );
};

export default TeamCard; 