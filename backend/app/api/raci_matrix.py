from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID

from app.models.raci_matrix import (
    RaciMatrix, CreateRaciMatrixPayload, UpdateRaciMatrixPayload,
    RaciMatrixType
)
from app.services.raci_service import RaciService
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.core.exceptions import ResourceNotFoundError, DatabaseError, BadRequestError

router = APIRouter(prefix="/raci-matrices", tags=["raci-matrices"])

@router.get("/", response_model=List[RaciMatrix])
async def get_all_matrices(
    current_user: User = Depends(get_current_user)
):
    """Get all active RACI matrices."""
    try:
        raci_service = RaciService()
        matrices = await raci_service.get_all_matrices()
        return matrices
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch RACI matrices"
        )

@router.get("/{matrix_id}", response_model=RaciMatrix)
async def get_matrix(
    matrix_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Get a specific RACI matrix by ID."""
    try:
        raci_service = RaciService()
        matrix = await raci_service.get_matrix_by_id(matrix_id)
        
        if not matrix:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RACI matrix with ID {matrix_id} not found"
            )
        
        return matrix
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/type/{matrix_type}", response_model=List[RaciMatrix])
async def get_matrices_by_type(
    matrix_type: RaciMatrixType,
    current_user: User = Depends(get_current_user)
):
    """Get RACI matrices by type."""
    try:
        raci_service = RaciService()
        matrices = await raci_service.get_matrices_by_type(matrix_type)
        return matrices
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/", response_model=dict)
async def create_matrix(
    payload: CreateRaciMatrixPayload,
    current_user: User = Depends(get_current_user)
):
    """Create a new RACI matrix."""
    try:
        raci_service = RaciService()
        matrix, warnings = await raci_service.create_matrix(payload, current_user.id)
        
        return {
            "matrix": matrix,
            "warnings": warnings
        }
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except BadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{matrix_id}", response_model=dict)
async def update_matrix(
    matrix_id: UUID,
    payload: UpdateRaciMatrixPayload,
    current_user: User = Depends(get_current_user)
):
    """Update an existing RACI matrix."""
    try:
        raci_service = RaciService()
        matrix, warnings = await raci_service.update_matrix(matrix_id, payload)
        
        if not matrix:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RACI matrix with ID {matrix_id} not found"
            )
        
        return {
            "matrix": matrix,
            "warnings": warnings
        }
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{matrix_id}")
async def delete_matrix(
    matrix_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Delete a RACI matrix."""
    try:
        raci_service = RaciService()
        success = await raci_service.delete_matrix(matrix_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RACI matrix with ID {matrix_id} not found"
            )
        
        return {"message": "RACI matrix deleted successfully"}
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{matrix_id}/validate", response_model=dict)
async def validate_matrix(
    matrix_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Validate assignments in a RACI matrix."""
    try:
        raci_service = RaciService()
        is_valid, errors = await raci_service.validate_matrix_assignments(matrix_id)
        
        return {
            "is_valid": is_valid,
            "errors": errors
        }
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 