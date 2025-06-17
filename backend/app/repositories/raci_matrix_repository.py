from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime

from app.models.raci_matrix import (
    RaciMatrix, CreateRaciMatrixPayload, UpdateRaciMatrixPayload,
    RaciMatrixType, RaciActivity, RaciRole, RaciAssignment
)
from app.config.supabase_client import get_supabase_client
from app.core.exceptions import DatabaseError, ResourceNotFoundError

logger = logging.getLogger(__name__)

class RaciMatrixRepository:
    """Repository for RACI matrix data access operations using Supabase."""
    
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_all_matrices(self) -> List[RaciMatrix]:
        """Get all active RACI matrices from database."""
        try:
            # Get matrices
            response = self.supabase.table('raci_matrices').select('*').eq('is_active', True).execute()
            matrices_data = response.data
            
            if not matrices_data:
                return []
            
            matrices = []
            for matrix_data in matrices_data:
                matrix = await self._build_complete_matrix(matrix_data)
                if matrix:
                    matrices.append(matrix)
            
            return matrices
        except Exception as e:
            logger.error(f"Failed to fetch RACI matrices: {e}")
            raise DatabaseError("Failed to fetch RACI matrices")
    
    async def get_matrix_by_id(self, matrix_id: UUID) -> Optional[RaciMatrix]:
        """Get a RACI matrix by ID from database."""
        try:
            # Get matrix
            response = self.supabase.table('raci_matrices').select('*').eq('id', str(matrix_id)).execute()
            
            if not response.data:
                return None
            
            matrix_data = response.data[0]
            return await self._build_complete_matrix(matrix_data)
            
        except Exception as e:
            logger.error(f"Failed to fetch RACI matrix {matrix_id}: {e}")
            raise DatabaseError(f"Failed to fetch RACI matrix {matrix_id}")
    
    async def get_matrices_by_type(self, matrix_type: RaciMatrixType) -> List[RaciMatrix]:
        """Get RACI matrices by type from database."""
        try:
            response = self.supabase.table('raci_matrices').select('*').eq('matrix_type', matrix_type.value).eq('is_active', True).execute()
            matrices_data = response.data
            
            if not matrices_data:
                return []
            
            matrices = []
            for matrix_data in matrices_data:
                matrix = await self._build_complete_matrix(matrix_data)
                if matrix:
                    matrices.append(matrix)
            
            return matrices
        except Exception as e:
            logger.error(f"Failed to fetch RACI matrices by type {matrix_type}: {e}")
            raise DatabaseError(f"Failed to fetch RACI matrices by type {matrix_type}")
    
    async def create_matrix(self, payload: CreateRaciMatrixPayload, created_by: Optional[UUID]) -> RaciMatrix:
        """Create a new RACI matrix in database."""
        try:
            # Create the main matrix record
            matrix_data = {
                'name': payload.name,
                'description': payload.description,
                'matrix_type': payload.matrix_type.value,
                'metadata': payload.metadata or {},
                'created_by': str(created_by) if created_by else None
            }
            
            response = self.supabase.table('raci_matrices').insert(matrix_data).execute()
            
            if not response.data:
                raise DatabaseError("Failed to create RACI matrix")
            
            matrix_record = response.data[0]
            matrix_id = matrix_record['id']
            
            # Create activities
            for activity in payload.activities:
                activity_data = {
                    'matrix_id': matrix_id,
                    'activity_id': activity.id,
                    'name': activity.name,
                    'description': activity.description,
                    'order_index': activity.order
                }
                self.supabase.table('raci_activities').insert(activity_data).execute()
            
            # Create roles
            for role in payload.roles:
                role_data = {
                    'matrix_id': matrix_id,
                    'role_id': role.id,
                    'name': role.name,
                    'title': role.title,
                    'user_id': str(role.user_id) if role.user_id else None,
                    'is_person': role.is_person,
                    'order_index': role.order
                }
                self.supabase.table('raci_roles').insert(role_data).execute()
            
            # Create assignments
            for assignment in payload.assignments:
                assignment_data = {
                    'matrix_id': matrix_id,
                    'activity_id': assignment.activity_id,
                    'role_id': assignment.role_id,
                    'role': assignment.role.value,
                    'notes': assignment.notes
                }
                self.supabase.table('raci_assignments').insert(assignment_data).execute()
            
            # Return the complete matrix
            created_matrix = await self.get_matrix_by_id(UUID(matrix_id))
            
            if not created_matrix:
                raise DatabaseError("Failed to retrieve created RACI matrix")
            
            logger.info(f"Created new RACI matrix: {matrix_id}")
            return created_matrix
            
        except Exception as e:
            logger.error(f"Failed to create RACI matrix: {e}")
            raise DatabaseError(f"Failed to create RACI matrix: {str(e)}")
    
    async def update_matrix(self, matrix_id: UUID, payload: UpdateRaciMatrixPayload) -> Optional[RaciMatrix]:
        """Update an existing RACI matrix in database."""
        try:
            # Check if matrix exists
            existing = await self.get_matrix_by_id(matrix_id)
            if not existing:
                return None
            
            # Update main matrix record
            update_data = {}
            if payload.name is not None:
                update_data['name'] = payload.name
            if payload.description is not None:
                update_data['description'] = payload.description
            if payload.metadata is not None:
                update_data['metadata'] = payload.metadata
            if payload.is_active is not None:
                update_data['is_active'] = payload.is_active
            
            if update_data:
                self.supabase.table('raci_matrices').update(update_data).eq('id', str(matrix_id)).execute()
            
            # Update activities if provided
            if payload.activities is not None:
                # Delete existing activities
                self.supabase.table('raci_activities').delete().eq('matrix_id', str(matrix_id)).execute()
                
                # Insert new activities
                for activity in payload.activities:
                    activity_data = {
                        'matrix_id': str(matrix_id),
                        'activity_id': activity.id,
                        'name': activity.name,
                        'description': activity.description,
                        'order_index': activity.order
                    }
                    self.supabase.table('raci_activities').insert(activity_data).execute()
            
            # Update roles if provided
            if payload.roles is not None:
                # Delete existing roles
                self.supabase.table('raci_roles').delete().eq('matrix_id', str(matrix_id)).execute()
                
                # Insert new roles
                for role in payload.roles:
                    role_data = {
                        'matrix_id': str(matrix_id),
                        'role_id': role.id,
                        'name': role.name,
                        'title': role.title,
                        'user_id': str(role.user_id) if role.user_id else None,
                        'is_person': role.is_person,
                        'order_index': role.order
                    }
                    self.supabase.table('raci_roles').insert(role_data).execute()
            
            # Update assignments if provided
            if payload.assignments is not None:
                # Delete existing assignments
                self.supabase.table('raci_assignments').delete().eq('matrix_id', str(matrix_id)).execute()
                
                # Insert new assignments
                for assignment in payload.assignments:
                    assignment_data = {
                        'matrix_id': str(matrix_id),
                        'activity_id': assignment.activity_id,
                        'role_id': assignment.role_id,
                        'role': assignment.role.value,
                        'notes': assignment.notes
                    }
                    self.supabase.table('raci_assignments').insert(assignment_data).execute()
            
            # Return the updated matrix
            updated_matrix = await self.get_matrix_by_id(matrix_id)
            
            if updated_matrix:
                logger.info(f"Updated RACI matrix: {matrix_id}")
            
            return updated_matrix
            
        except Exception as e:
            logger.error(f"Failed to update RACI matrix {matrix_id}: {e}")
            raise DatabaseError(f"Failed to update RACI matrix {matrix_id}")
    
    async def delete_matrix(self, matrix_id: UUID) -> bool:
        """Soft delete a RACI matrix by setting is_active to False."""
        try:
            response = self.supabase.table('raci_matrices').update({'is_active': False}).eq('id', str(matrix_id)).execute()
            
            if response.data:
                logger.info(f"Deleted RACI matrix: {matrix_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete RACI matrix {matrix_id}: {e}")
            raise DatabaseError(f"Failed to delete RACI matrix {matrix_id}")
    
    async def _build_complete_matrix(self, matrix_data: Dict[str, Any]) -> Optional[RaciMatrix]:
        """Build a complete RaciMatrix object with activities, roles, and assignments."""
        try:
            matrix_id = matrix_data['id']
            
            # Get activities
            activities_response = self.supabase.table('raci_activities').select('*').eq('matrix_id', matrix_id).order('order_index').execute()
            activities = []
            
            for activity_data in activities_response.data:
                activities.append(RaciActivity(
                    id=activity_data['activity_id'],
                    name=activity_data['name'],
                    description=activity_data['description'],
                    order=activity_data['order_index']
                ))
            
            # Get roles
            roles_response = self.supabase.table('raci_roles').select('*').eq('matrix_id', matrix_id).order('order_index').execute()
            roles = []
            
            for role_data in roles_response.data:
                roles.append(RaciRole(
                    id=role_data['role_id'],
                    name=role_data['name'],
                    title=role_data['title'],
                    user_id=UUID(role_data['user_id']) if role_data['user_id'] else None,
                    is_person=role_data['is_person'],
                    order=role_data['order_index']
                ))
            
            # Get assignments
            assignments_response = self.supabase.table('raci_assignments').select('*').eq('matrix_id', matrix_id).execute()
            assignments = []
            
            for assignment_data in assignments_response.data:
                assignments.append(RaciAssignment(
                    activity_id=assignment_data['activity_id'],
                    role_id=assignment_data['role_id'],
                    role=assignment_data['role'],
                    notes=assignment_data['notes']
                ))
            
            # Build the complete matrix
            return RaciMatrix(
                id=UUID(matrix_data['id']),
                name=matrix_data['name'],
                description=matrix_data['description'],
                matrix_type=RaciMatrixType(matrix_data['matrix_type']),
                activities=activities,
                roles=roles,
                assignments=assignments,
                metadata=matrix_data['metadata'] or {},
                is_active=matrix_data['is_active'],
                created_by=UUID(matrix_data['created_by']) if matrix_data['created_by'] else None,
                created_at=datetime.fromisoformat(matrix_data['created_at'].replace('Z', '+00:00')) if matrix_data['created_at'] else None,
                updated_at=datetime.fromisoformat(matrix_data['updated_at'].replace('Z', '+00:00')) if matrix_data['updated_at'] else None
            )
            
        except Exception as e:
            logger.error(f"Failed to build complete matrix for {matrix_data.get('id', 'unknown')}: {e}")
            return None 