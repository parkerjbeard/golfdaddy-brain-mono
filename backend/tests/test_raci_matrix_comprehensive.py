import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4
from typing import List
import asyncio
from datetime import datetime

from app.models.raci_matrix import (
    RaciMatrix, RaciActivity, RaciRole, RaciAssignment,
    CreateRaciMatrixPayload, UpdateRaciMatrixPayload,
    UpdateAssignmentsPayload, BulkAssignmentPayload,
    RaciMatrixType, RaciRoleType, RaciMatrixTemplate
)
from app.services.raci_service import RaciService
from app.repositories.raci_matrix_repository import RaciMatrixRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.exceptions import ResourceNotFoundError, BadRequestError


class TestRaciService:
    """Comprehensive tests for RACI matrix service functionality."""
    
    @pytest.fixture
    def raci_service(self):
        """Create a RaciService instance with mocked dependencies."""
        service = RaciService()
        service.user_repo = Mock(spec=UserRepository)
        service.matrix_repo = Mock(spec=RaciMatrixRepository)
        return service
    
    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    @pytest.fixture
    def sample_matrix(self):
        """Create a sample RACI matrix."""
        matrix_id = uuid4()
        return RaciMatrix(
            id=matrix_id,
            name="Test Matrix",
            description="Test Description",
            matrix_type=RaciMatrixType.INVENTORY_INBOUND,
            activities=[
                RaciActivity(id="act1", name="Activity 1", description="Test activity 1", order=1),
                RaciActivity(id="act2", name="Activity 2", description="Test activity 2", order=2),
                RaciActivity(id="act3", name="Activity 3", description="Test activity 3", order=3)
            ],
            roles=[
                RaciRole(id="role1", name="Role 1", title="Test Role 1", is_person=False, order=1),
                RaciRole(id="role2", name="Role 2", title="Test Role 2", is_person=False, order=2),
                RaciRole(id="role3", name="Role 3", title="Test Role 3", is_person=False, order=3)
            ],
            assignments=[
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="role2", role=RaciRoleType.ACCOUNTABLE),
                RaciAssignment(activity_id="act2", role_id="role1", role=RaciRoleType.CONSULTED),
                RaciAssignment(activity_id="act2", role_id="role3", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act2", role_id="role2", role=RaciRoleType.ACCOUNTABLE)
            ],
            is_active=True,
            created_by=uuid4()
        )
    
    # Test update_assignments method
    
    @pytest.mark.asyncio
    async def test_update_assignments_success(self, raci_service, sample_matrix):
        """Test successful update of assignments."""
        matrix_id = sample_matrix.id
        payload = UpdateAssignmentsPayload(
            assignments=[
                RaciAssignment(activity_id="act1", role_id="role3", role=RaciRoleType.INFORMED),
                RaciAssignment(activity_id="act3", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act3", role_id="role2", role=RaciRoleType.ACCOUNTABLE)
            ]
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        raci_service.matrix_repo.update_assignments = AsyncMock(return_value=True)
        
        success, warnings = await raci_service.update_assignments(matrix_id, payload)
        
        assert success is True
        assert len(warnings) == 0
        raci_service.matrix_repo.update_assignments.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_assignments_matrix_not_found(self, raci_service):
        """Test update assignments when matrix doesn't exist."""
        matrix_id = uuid4()
        payload = UpdateAssignmentsPayload(assignments=[])
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError):
            await raci_service.update_assignments(matrix_id, payload)
    
    @pytest.mark.asyncio
    async def test_update_assignments_invalid_activity(self, raci_service, sample_matrix):
        """Test update assignments with invalid activity ID."""
        matrix_id = sample_matrix.id
        payload = UpdateAssignmentsPayload(
            assignments=[
                RaciAssignment(activity_id="invalid_act", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.INFORMED)  # Add valid one
            ]
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        raci_service.matrix_repo.update_assignments = AsyncMock(return_value=True)
        
        success, warnings = await raci_service.update_assignments(matrix_id, payload)
        
        assert success is True
        assert len(warnings) == 1
        assert "invalid activity ID" in warnings[0]
    
    @pytest.mark.asyncio
    async def test_update_assignments_invalid_role(self, raci_service, sample_matrix):
        """Test update assignments with invalid role ID."""
        matrix_id = sample_matrix.id
        payload = UpdateAssignmentsPayload(
            assignments=[
                RaciAssignment(activity_id="act1", role_id="invalid_role", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="role2", role=RaciRoleType.CONSULTED)  # Add valid one
            ]
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        raci_service.matrix_repo.update_assignments = AsyncMock(return_value=True)
        
        success, warnings = await raci_service.update_assignments(matrix_id, payload)
        
        assert success is True
        assert len(warnings) == 1
        assert "invalid role ID" in warnings[0]
    
    @pytest.mark.asyncio
    async def test_update_assignments_all_invalid(self, raci_service, sample_matrix):
        """Test update assignments when all assignments are invalid."""
        matrix_id = sample_matrix.id
        payload = UpdateAssignmentsPayload(
            assignments=[
                RaciAssignment(activity_id="invalid_act1", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="invalid_role1", role=RaciRoleType.ACCOUNTABLE)
            ]
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        
        success, warnings = await raci_service.update_assignments(matrix_id, payload)
        
        assert success is False
        assert len(warnings) >= 1
        assert "No valid assignments to update" in warnings[-1]
    
    # Test bulk_assign method
    
    @pytest.mark.asyncio
    async def test_bulk_assign_success(self, raci_service, sample_matrix):
        """Test successful bulk assignment."""
        matrix_id = sample_matrix.id
        payload = BulkAssignmentPayload(
            activity_ids=["act1", "act2"],
            role_ids=["role1", "role2"],
            role_type=RaciRoleType.CONSULTED,
            notes="Bulk assigned",
            clear_existing=False
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        raci_service.matrix_repo.bulk_update_assignments = AsyncMock(return_value=4)
        
        updated_count, warnings = await raci_service.bulk_assign(matrix_id, payload)
        
        assert updated_count == 4
        assert len(warnings) == 0
        raci_service.matrix_repo.bulk_update_assignments.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bulk_assign_matrix_not_found(self, raci_service):
        """Test bulk assign when matrix doesn't exist."""
        matrix_id = uuid4()
        payload = BulkAssignmentPayload(
            activity_ids=["act1"],
            role_ids=["role1"],
            role_type=RaciRoleType.RESPONSIBLE,
            clear_existing=False
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError):
            await raci_service.bulk_assign(matrix_id, payload)
    
    @pytest.mark.asyncio
    async def test_bulk_assign_invalid_ids(self, raci_service, sample_matrix):
        """Test bulk assign with invalid IDs."""
        matrix_id = sample_matrix.id
        payload = BulkAssignmentPayload(
            activity_ids=["invalid_act1", "invalid_act2"],
            role_ids=["invalid_role1", "invalid_role2"],
            role_type=RaciRoleType.RESPONSIBLE,
            clear_existing=False
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        
        updated_count, warnings = await raci_service.bulk_assign(matrix_id, payload)
        
        assert updated_count == 0
        assert len(warnings) == 4  # 2 invalid activities + 2 invalid roles
    
    # Test validate_matrix_complete method
    
    @pytest.mark.asyncio
    async def test_validate_matrix_complete_valid(self, raci_service, sample_matrix):
        """Test comprehensive validation on a valid matrix."""
        # Ensure all activities have R and A
        sample_matrix.assignments.extend([
            RaciAssignment(activity_id="act3", role_id="role3", role=RaciRoleType.RESPONSIBLE),
            RaciAssignment(activity_id="act3", role_id="role1", role=RaciRoleType.ACCOUNTABLE)
        ])
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        raci_service.user_repo.get_user_by_id = AsyncMock(return_value=Mock())
        
        is_valid, result = await raci_service.validate_matrix_complete(sample_matrix.id)
        
        assert is_valid is True
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0
        assert result["stats"]["total_activities"] == 3
        assert result["stats"]["total_roles"] == 3
        assert result["stats"]["total_assignments"] == 7
    
    @pytest.mark.asyncio
    async def test_validate_matrix_complete_missing_r_and_a(self, raci_service):
        """Test validation with activities missing R and A assignments."""
        matrix = RaciMatrix(
            id=uuid4(),
            name="Test Matrix",
            description="Test",
            matrix_type=RaciMatrixType.CUSTOM,
            activities=[
                RaciActivity(id="act1", name="Activity 1", order=1),
                RaciActivity(id="act2", name="Activity 2", order=2)
            ],
            roles=[
                RaciRole(id="role1", name="Role 1", order=1)
            ],
            assignments=[
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.CONSULTED)
            ],
            is_active=True
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=matrix)
        
        is_valid, result = await raci_service.validate_matrix_complete(matrix.id)
        
        assert is_valid is False
        assert len(result["errors"]) >= 4  # Missing R and A for both activities
    
    @pytest.mark.asyncio
    async def test_validate_matrix_complete_multiple_accountable(self, raci_service):
        """Test validation with multiple accountable assignments."""
        matrix = RaciMatrix(
            id=uuid4(),
            name="Test Matrix",
            description="Test",
            matrix_type=RaciMatrixType.CUSTOM,
            activities=[
                RaciActivity(id="act1", name="Activity 1", order=1)
            ],
            roles=[
                RaciRole(id="role1", name="Role 1", order=1),
                RaciRole(id="role2", name="Role 2", order=2)
            ],
            assignments=[
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.ACCOUNTABLE),
                RaciAssignment(activity_id="act1", role_id="role2", role=RaciRoleType.ACCOUNTABLE)
            ],
            is_active=True
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=matrix)
        
        is_valid, result = await raci_service.validate_matrix_complete(matrix.id)
        
        assert len(result["warnings"]) >= 1
        assert "2 Accountable assignments" in result["warnings"][0]
    
    @pytest.mark.asyncio
    async def test_validate_matrix_complete_orphaned_assignments(self, raci_service):
        """Test validation with orphaned assignments."""
        matrix = RaciMatrix(
            id=uuid4(),
            name="Test Matrix",
            description="Test",
            matrix_type=RaciMatrixType.CUSTOM,
            activities=[
                RaciActivity(id="act1", name="Activity 1", order=1)
            ],
            roles=[
                RaciRole(id="role1", name="Role 1", order=1)
            ],
            assignments=[
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.ACCOUNTABLE),
                RaciAssignment(activity_id="invalid_act", role_id="role1", role=RaciRoleType.CONSULTED),
                RaciAssignment(activity_id="act1", role_id="invalid_role", role=RaciRoleType.INFORMED)
            ],
            is_active=True
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=matrix)
        
        is_valid, result = await raci_service.validate_matrix_complete(matrix.id)
        
        assert is_valid is False
        assert len(result["errors"]) >= 2  # Invalid activity and role references
    
    # Test get_matrix_templates method
    
    def test_get_matrix_templates(self, raci_service):
        """Test getting predefined matrix templates."""
        templates = raci_service.get_matrix_templates()
        
        assert len(templates) == 3
        
        # Check template IDs
        template_ids = [t.template_id for t in templates]
        assert "inventory_inbound_template" in template_ids
        assert "shipbob_issues_template" in template_ids
        assert "data_collection_template" in template_ids
        
        # Verify each template has required structure
        for template in templates:
            assert isinstance(template, RaciMatrixTemplate)
            assert len(template.activities) > 0
            assert len(template.roles) > 0
            assert len(template.assignments) > 0
            
            # Verify all assignments reference valid activities and roles
            activity_ids = {a.id for a in template.activities}
            role_ids = {r.id for r in template.roles}
            
            for assignment in template.assignments:
                assert assignment.activity_id in activity_ids
                assert assignment.role_id in role_ids
    
    def test_inventory_inbound_template_structure(self, raci_service):
        """Test the inventory inbound template structure."""
        templates = raci_service.get_matrix_templates()
        inventory_template = next(t for t in templates if t.template_id == "inventory_inbound_template")
        
        assert inventory_template.matrix_type == RaciMatrixType.INVENTORY_INBOUND
        assert len(inventory_template.activities) == 6
        assert len(inventory_template.roles) == 5
        
        # Verify each activity has at least R and A
        for activity in inventory_template.activities:
            activity_assignments = [a for a in inventory_template.assignments if a.activity_id == activity.id]
            roles_assigned = [a.role for a in activity_assignments]
            assert RaciRoleType.RESPONSIBLE in roles_assigned
            assert RaciRoleType.ACCOUNTABLE in roles_assigned
    
    # Test create_matrix_from_template method
    
    @pytest.mark.asyncio
    async def test_create_matrix_from_template_success(self, raci_service, sample_user):
        """Test creating a matrix from a template."""
        template_id = "inventory_inbound_template"
        name = "My Inventory Process"
        description = "Custom inventory process"
        created_by = sample_user.id
        
        expected_matrix = RaciMatrix(
            id=uuid4(),
            name=name,
            description=description,
            matrix_type=RaciMatrixType.INVENTORY_INBOUND,
            activities=[],
            roles=[],
            assignments=[],
            is_active=True,
            created_by=created_by
        )
        
        raci_service.user_repo.get_user_by_id = AsyncMock(return_value=sample_user)
        raci_service.matrix_repo.create_matrix = AsyncMock(return_value=expected_matrix)
        
        matrix, warnings = await raci_service.create_matrix_from_template(
            template_id, name, description, created_by
        )
        
        assert matrix.id == expected_matrix.id
        assert matrix.name == name
        assert matrix.description == description
        assert len(warnings) == 0
        
        # Verify create_matrix was called with template data
        create_call_args = raci_service.matrix_repo.create_matrix.call_args[0]
        payload = create_call_args[0]
        assert payload.name == name
        assert payload.matrix_type == RaciMatrixType.INVENTORY_INBOUND
        assert len(payload.activities) == 6
        assert len(payload.roles) == 5
        assert payload.metadata["created_from_template"] == template_id
    
    @pytest.mark.asyncio
    async def test_create_matrix_from_template_invalid_template(self, raci_service):
        """Test creating a matrix from invalid template ID."""
        with pytest.raises(BadRequestError) as exc_info:
            await raci_service.create_matrix_from_template(
                "invalid_template_id", "Test", None, uuid4()
            )
        assert "Template with ID 'invalid_template_id' not found" in str(exc_info.value)
    
    # Integration test for full workflow
    
    @pytest.mark.asyncio
    async def test_full_raci_workflow(self, raci_service, sample_user):
        """Test complete RACI matrix workflow."""
        user_id = sample_user.id
        
        # Step 1: Create matrix from template
        raci_service.user_repo.get_user_by_id = AsyncMock(return_value=sample_user)
        
        created_matrix = RaciMatrix(
            id=uuid4(),
            name="Test Workflow Matrix",
            description="Test",
            matrix_type=RaciMatrixType.INVENTORY_INBOUND,
            activities=[
                RaciActivity(id="act1", name="Activity 1", order=1),
                RaciActivity(id="act2", name="Activity 2", order=2)
            ],
            roles=[
                RaciRole(id="role1", name="Role 1", order=1),
                RaciRole(id="role2", name="Role 2", order=2)
            ],
            assignments=[
                RaciAssignment(activity_id="act1", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act1", role_id="role2", role=RaciRoleType.ACCOUNTABLE)
            ],
            is_active=True,
            created_by=user_id
        )
        
        raci_service.matrix_repo.create_matrix = AsyncMock(return_value=created_matrix)
        
        matrix, warnings = await raci_service.create_matrix_from_template(
            "inventory_inbound_template", "Test Workflow Matrix", "Test", user_id
        )
        
        assert matrix.id == created_matrix.id
        
        # Step 2: Validate initial state
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=created_matrix)
        
        is_valid, result = await raci_service.validate_matrix_complete(matrix.id)
        
        # Should have errors for missing R and A on act2
        assert is_valid is False
        assert len(result["errors"]) >= 2
        
        # Step 3: Update assignments to fix validation
        update_payload = UpdateAssignmentsPayload(
            assignments=[
                RaciAssignment(activity_id="act2", role_id="role1", role=RaciRoleType.RESPONSIBLE),
                RaciAssignment(activity_id="act2", role_id="role2", role=RaciRoleType.ACCOUNTABLE)
            ]
        )
        
        # Update the matrix for next validation
        created_matrix.assignments.extend(update_payload.assignments)
        raci_service.matrix_repo.update_assignments = AsyncMock(return_value=True)
        
        success, warnings = await raci_service.update_assignments(matrix.id, update_payload)
        assert success is True
        
        # Step 4: Validate again - should be valid now
        is_valid, result = await raci_service.validate_matrix_complete(matrix.id)
        assert is_valid is True
        assert len(result["errors"]) == 0
        
        # Step 5: Bulk assign consulted roles
        bulk_payload = BulkAssignmentPayload(
            activity_ids=["act1", "act2"],
            role_ids=["role1", "role2"],
            role_type=RaciRoleType.CONSULTED,
            notes="Everyone should be consulted",
            clear_existing=False
        )
        
        raci_service.matrix_repo.bulk_update_assignments = AsyncMock(return_value=4)
        
        updated_count, warnings = await raci_service.bulk_assign(matrix.id, bulk_payload)
        assert updated_count == 4
    
    # Test edge cases
    
    @pytest.mark.asyncio
    async def test_update_assignments_empty_payload(self, raci_service, sample_matrix):
        """Test update assignments with empty payload."""
        matrix_id = sample_matrix.id
        payload = UpdateAssignmentsPayload(assignments=[])
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        
        success, warnings = await raci_service.update_assignments(matrix_id, payload)
        
        assert success is False
        assert "No valid assignments to update" in warnings[0]
    
    @pytest.mark.asyncio
    async def test_bulk_assign_with_clear_existing(self, raci_service, sample_matrix):
        """Test bulk assign with clear_existing flag."""
        matrix_id = sample_matrix.id
        payload = BulkAssignmentPayload(
            activity_ids=["act1"],
            role_ids=["role1"],
            role_type=RaciRoleType.INFORMED,
            clear_existing=True
        )
        
        raci_service.matrix_repo.get_matrix_by_id = AsyncMock(return_value=sample_matrix)
        raci_service.matrix_repo.bulk_update_assignments = AsyncMock(return_value=1)
        
        updated_count, warnings = await raci_service.bulk_assign(matrix_id, payload)
        
        # Verify clear_existing was passed to repository
        call_args = raci_service.matrix_repo.bulk_update_assignments.call_args[0]
        assert call_args[5] is True  # clear_existing parameter