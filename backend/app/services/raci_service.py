import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging
from datetime import datetime

from app.models.user import User
from app.models.raci_matrix import (
    RaciMatrix, CreateRaciMatrixPayload, UpdateRaciMatrixPayload,
    RaciMatrixType, RaciActivity, RaciRole, RaciAssignment
)
from app.repositories.user_repository import UserRepository
from app.repositories.raci_matrix_repository import RaciMatrixRepository
from app.core.exceptions import ResourceNotFoundError, DatabaseError, BadRequestError

logger = logging.getLogger(__name__)

class RaciService:
    """Service for managing RACI matrices and validating RACI assignments."""
    
    def __init__(self):
        # Instantiate repositories directly
        # In a larger app, consider dependency injection framework
        self.user_repo = UserRepository()
        self.matrix_repo = RaciMatrixRepository()

    # RACI Matrix Management Methods
    
    async def get_all_matrices(self) -> List[RaciMatrix]:
        """Get all active RACI matrices."""
        return await self.matrix_repo.get_all_matrices()
    
    async def get_matrix_by_id(self, matrix_id: UUID) -> Optional[RaciMatrix]:
        """Get a specific RACI matrix by ID."""
        return await self.matrix_repo.get_matrix_by_id(matrix_id)
    
    async def get_matrices_by_type(self, matrix_type: RaciMatrixType) -> List[RaciMatrix]:
        """Get RACI matrices by type."""
        return await self.matrix_repo.get_matrices_by_type(matrix_type)
    
    async def create_matrix(self, payload: CreateRaciMatrixPayload, created_by: UUID) -> Tuple[RaciMatrix, List[str]]:
        """Create a new RACI matrix with validation."""
        warnings = []
        
        # Validate that the creator exists
        creator = await self.user_repo.get_user_by_id(created_by)
        if not creator:
            raise ResourceNotFoundError(resource_name="Creator User", resource_id=str(created_by))
        
        # Validate role assignments against real users if user_id is specified
        for role in payload.roles:
            if role.user_id:
                user = await self.user_repo.get_user_by_id(role.user_id)
                if not user:
                    warn_msg = f"User ID {role.user_id} for role '{role.name}' not found. Role will be created but not linked to a user."
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
        
        # Validate that all assignments reference valid activities and roles
        activity_ids = {activity.id for activity in payload.activities}
        role_ids = {role.id for role in payload.roles}
        
        valid_assignments = []
        for assignment in payload.assignments:
            if assignment.activity_id not in activity_ids:
                warn_msg = f"Assignment references invalid activity ID: {assignment.activity_id}"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                continue
            
            if assignment.role_id not in role_ids:
                warn_msg = f"Assignment references invalid role ID: {assignment.role_id}"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                continue
            
            valid_assignments.append(assignment)
        
        # Update payload with valid assignments
        payload.assignments = valid_assignments
        
        # Create the matrix
        matrix = await self.matrix_repo.create_matrix(payload, created_by)
        
        logger.info(f"RACI matrix '{matrix.name}' created successfully with {len(warnings)} warnings.")
        return matrix, warnings
    
    async def update_matrix(self, matrix_id: UUID, payload: UpdateRaciMatrixPayload) -> Tuple[Optional[RaciMatrix], List[str]]:
        """Update an existing RACI matrix with validation."""
        warnings = []
        
        # Check if matrix exists
        existing_matrix = await self.matrix_repo.get_matrix_by_id(matrix_id)
        if not existing_matrix:
            raise ResourceNotFoundError(resource_name="RACI Matrix", resource_id=str(matrix_id))
        
        # Validate role assignments against real users if user_id is specified
        if payload.roles:
            for role in payload.roles:
                if role.user_id:
                    user = await self.user_repo.get_user_by_id(role.user_id)
                    if not user:
                        warn_msg = f"User ID {role.user_id} for role '{role.name}' not found. Role will be updated but not linked to a user."
                        logger.warning(warn_msg)
                        warnings.append(warn_msg)
        
        # Validate assignments if provided
        if payload.assignments and payload.activities and payload.roles:
            activity_ids = {activity.id for activity in payload.activities}
            role_ids = {role.id for role in payload.roles}
            
            valid_assignments = []
            for assignment in payload.assignments:
                if assignment.activity_id not in activity_ids:
                    warn_msg = f"Assignment references invalid activity ID: {assignment.activity_id}"
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                    continue
                
                if assignment.role_id not in role_ids:
                    warn_msg = f"Assignment references invalid role ID: {assignment.role_id}"
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                    continue
                
                valid_assignments.append(assignment)
            
            payload.assignments = valid_assignments
        
        # Update the matrix
        updated_matrix = await self.matrix_repo.update_matrix(matrix_id, payload)
        
        if updated_matrix:
            logger.info(f"RACI matrix '{updated_matrix.name}' updated successfully with {len(warnings)} warnings.")
        
        return updated_matrix, warnings
    
    async def delete_matrix(self, matrix_id: UUID) -> bool:
        """Soft delete a RACI matrix."""
        existing_matrix = await self.matrix_repo.get_matrix_by_id(matrix_id)
        if not existing_matrix:
            raise ResourceNotFoundError(resource_name="RACI Matrix", resource_id=str(matrix_id))
        
        result = await self.matrix_repo.delete_matrix(matrix_id)
        
        if result:
            logger.info(f"RACI matrix '{existing_matrix.name}' deleted successfully.")
        
        return result
    
    async def validate_matrix_assignments(self, matrix_id: UUID) -> Tuple[bool, List[str]]:
        """Validate all assignments in a RACI matrix."""
        errors = []
        
        matrix = await self.matrix_repo.get_matrix_by_id(matrix_id)
        if not matrix:
            return False, ["Matrix not found"]
        
        activity_ids = {activity.id for activity in matrix.activities}
        role_ids = {role.id for role in matrix.roles}
        
        # Check for invalid references in assignments
        for assignment in matrix.assignments:
            if assignment.activity_id not in activity_ids:
                errors.append(f"Assignment references invalid activity ID: {assignment.activity_id}")
            
            if assignment.role_id not in role_ids:
                errors.append(f"Assignment references invalid role ID: {assignment.role_id}")
        
        # Check for missing critical assignments (each activity should have at least one R and one A)
        for activity in matrix.activities:
            activity_assignments = [a for a in matrix.assignments if a.activity_id == activity.id]
            
            has_responsible = any(a.role == "R" for a in activity_assignments)
            has_accountable = any(a.role == "A" for a in activity_assignments)
            
            if not has_responsible:
                errors.append(f"Activity '{activity.name}' has no Responsible (R) assignment")
            
            if not has_accountable:
                errors.append(f"Activity '{activity.name}' has no Accountable (A) assignment")
        
        # Check for user references that don't exist
        for role in matrix.roles:
            if role.user_id:
                user = await self.user_repo.get_user_by_id(role.user_id)
                if not user:
                    errors.append(f"Role '{role.name}' references non-existent user ID: {role.user_id}")
        
        return len(errors) == 0, errors