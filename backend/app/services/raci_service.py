import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.core.exceptions import BadRequestError, ResourceNotFoundError
from app.models.raci_matrix import (
    BulkAssignmentPayload,
    CreateRaciMatrixPayload,
    RaciActivity,
    RaciAssignment,
    RaciMatrix,
    RaciMatrixTemplate,
    RaciMatrixType,
    RaciRole,
    UpdateAssignmentsPayload,
    UpdateRaciMatrixPayload,
)
from app.repositories.raci_matrix_repository import RaciMatrixRepository
from app.repositories.user_repository import UserRepository

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

    async def update_matrix(
        self, matrix_id: UUID, payload: UpdateRaciMatrixPayload
    ) -> Tuple[Optional[RaciMatrix], List[str]]:
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

    # New methods for enhanced RACI functionality

    async def update_assignments(self, matrix_id: UUID, payload: UpdateAssignmentsPayload) -> Tuple[bool, List[str]]:
        """Update specific assignments in a RACI matrix."""
        warnings = []

        # Verify matrix exists
        matrix = await self.matrix_repo.get_matrix_by_id(matrix_id)
        if not matrix:
            raise ResourceNotFoundError(resource_name="RACI Matrix", resource_id=str(matrix_id))

        # Validate assignments
        activity_ids = {activity.id for activity in matrix.activities}
        role_ids = {role.id for role in matrix.roles}

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

        if not valid_assignments:
            return False, ["No valid assignments to update"]

        # Update assignments
        success = await self.matrix_repo.update_assignments(matrix_id, valid_assignments)

        if success:
            logger.info(f"Updated {len(valid_assignments)} assignments for RACI matrix: {matrix_id}")

        return success, warnings

    async def bulk_assign(self, matrix_id: UUID, payload: BulkAssignmentPayload) -> Tuple[int, List[str]]:
        """Perform bulk assignment operations."""
        warnings = []

        # Verify matrix exists
        matrix = await self.matrix_repo.get_matrix_by_id(matrix_id)
        if not matrix:
            raise ResourceNotFoundError(resource_name="RACI Matrix", resource_id=str(matrix_id))

        # Validate activity and role IDs
        activity_ids = {activity.id for activity in matrix.activities}
        role_ids = {role.id for role in matrix.roles}

        valid_activity_ids = []
        for activity_id in payload.activity_ids:
            if activity_id not in activity_ids:
                warn_msg = f"Activity ID {activity_id} not found in matrix"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
            else:
                valid_activity_ids.append(activity_id)

        valid_role_ids = []
        for role_id in payload.role_ids:
            if role_id not in role_ids:
                warn_msg = f"Role ID {role_id} not found in matrix"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
            else:
                valid_role_ids.append(role_id)

        if not valid_activity_ids or not valid_role_ids:
            return 0, warnings

        # Perform bulk update
        updated_count = await self.matrix_repo.bulk_update_assignments(
            matrix_id,
            valid_activity_ids,
            valid_role_ids,
            payload.role_type.value,
            payload.notes,
            payload.clear_existing,
        )

        logger.info(f"Bulk assigned {updated_count} RACI assignments for matrix: {matrix_id}")
        return updated_count, warnings

    async def validate_matrix_complete(self, matrix_id: UUID) -> Tuple[bool, Dict[str, Any]]:
        """Enhanced validation with more comprehensive checks."""
        result = {"is_valid": True, "errors": [], "warnings": [], "stats": {}}

        matrix = await self.matrix_repo.get_matrix_by_id(matrix_id)
        if not matrix:
            result["is_valid"] = False
            result["errors"].append("Matrix not found")
            return False, result

        activity_ids = {activity.id for activity in matrix.activities}
        role_ids = {role.id for role in matrix.roles}

        # Basic validation
        is_valid, errors = await self.validate_matrix_assignments(matrix_id)
        result["errors"].extend(errors)

        # Additional validations

        # Check for orphaned assignments
        for assignment in matrix.assignments:
            if assignment.activity_id not in activity_ids:
                result["errors"].append(f"Assignment references invalid activity ID: {assignment.activity_id}")
            if assignment.role_id not in role_ids:
                result["errors"].append(f"Assignment references invalid role ID: {assignment.role_id}")

        # Check for activities without any assignments
        for activity in matrix.activities:
            activity_assignments = [a for a in matrix.assignments if a.activity_id == activity.id]
            if not activity_assignments:
                result["warnings"].append(f"Activity '{activity.name}' has no assignments")

        # Check for roles without any assignments
        for role in matrix.roles:
            role_assignments = [a for a in matrix.assignments if a.role_id == role.id]
            if not role_assignments:
                result["warnings"].append(f"Role '{role.name}' has no assignments")

        # Check for multiple accountable (A) assignments per activity
        for activity in matrix.activities:
            activity_assignments = [a for a in matrix.assignments if a.activity_id == activity.id]
            accountable_count = sum(1 for a in activity_assignments if a.role == "A")
            if accountable_count > 1:
                result["warnings"].append(
                    f"Activity '{activity.name}' has {accountable_count} Accountable assignments (should have only 1)"
                )

        # Collect statistics
        result["stats"] = {
            "total_activities": len(matrix.activities),
            "total_roles": len(matrix.roles),
            "total_assignments": len(matrix.assignments),
            "assignments_by_type": {},
        }

        # Count assignments by type
        for role_type in ["R", "A", "C", "I"]:
            count = sum(1 for a in matrix.assignments if a.role == role_type)
            result["stats"]["assignments_by_type"][role_type] = count

        result["is_valid"] = len(result["errors"]) == 0

        return result["is_valid"], result

    def get_matrix_templates(self) -> List[RaciMatrixTemplate]:
        """Get predefined RACI matrix templates."""
        templates = []

        # Inventory Inbound Process Template
        templates.append(
            RaciMatrixTemplate(
                template_id="inventory_inbound_template",
                name="Inventory Inbound Process",
                description="Standard RACI matrix for inventory receiving and processing",
                matrix_type=RaciMatrixType.INVENTORY_INBOUND,
                activities=[
                    RaciActivity(
                        id="recv_1",
                        name="Receive Shipment",
                        description="Physical receipt of inventory shipment",
                        order=1,
                    ),
                    RaciActivity(
                        id="recv_2",
                        name="Verify Contents",
                        description="Check shipment against purchase order",
                        order=2,
                    ),
                    RaciActivity(
                        id="recv_3",
                        name="Quality Inspection",
                        description="Inspect items for damage or defects",
                        order=3,
                    ),
                    RaciActivity(
                        id="recv_4",
                        name="Update Inventory System",
                        description="Enter received items into inventory management system",
                        order=4,
                    ),
                    RaciActivity(
                        id="recv_5",
                        name="Store Items",
                        description="Put away items in designated warehouse locations",
                        order=5,
                    ),
                    RaciActivity(
                        id="recv_6",
                        name="Report Discrepancies",
                        description="Document and report any issues found",
                        order=6,
                    ),
                ],
                roles=[
                    RaciRole(
                        id="role_wh_mgr",
                        name="Warehouse Manager",
                        title="Warehouse Operations Manager",
                        is_person=False,
                        order=1,
                    ),
                    RaciRole(
                        id="role_recv_clerk",
                        name="Receiving Clerk",
                        title="Inventory Receiving Specialist",
                        is_person=False,
                        order=2,
                    ),
                    RaciRole(
                        id="role_qa", name="QA Inspector", title="Quality Assurance Inspector", is_person=False, order=3
                    ),
                    RaciRole(
                        id="role_inv_ctrl",
                        name="Inventory Controller",
                        title="Inventory Control Specialist",
                        is_person=False,
                        order=4,
                    ),
                    RaciRole(
                        id="role_purchasing", name="Purchasing", title="Purchasing Department", is_person=False, order=5
                    ),
                ],
                assignments=[
                    # Receive Shipment
                    RaciAssignment(activity_id="recv_1", role_id="role_recv_clerk", role="R"),
                    RaciAssignment(activity_id="recv_1", role_id="role_wh_mgr", role="A"),
                    RaciAssignment(activity_id="recv_1", role_id="role_purchasing", role="I"),
                    # Verify Contents
                    RaciAssignment(activity_id="recv_2", role_id="role_recv_clerk", role="R"),
                    RaciAssignment(activity_id="recv_2", role_id="role_wh_mgr", role="A"),
                    RaciAssignment(activity_id="recv_2", role_id="role_purchasing", role="C"),
                    # Quality Inspection
                    RaciAssignment(activity_id="recv_3", role_id="role_qa", role="R"),
                    RaciAssignment(activity_id="recv_3", role_id="role_wh_mgr", role="A"),
                    RaciAssignment(activity_id="recv_3", role_id="role_recv_clerk", role="C"),
                    # Update Inventory System
                    RaciAssignment(activity_id="recv_4", role_id="role_inv_ctrl", role="R"),
                    RaciAssignment(activity_id="recv_4", role_id="role_wh_mgr", role="A"),
                    RaciAssignment(activity_id="recv_4", role_id="role_recv_clerk", role="I"),
                    # Store Items
                    RaciAssignment(activity_id="recv_5", role_id="role_recv_clerk", role="R"),
                    RaciAssignment(activity_id="recv_5", role_id="role_wh_mgr", role="A"),
                    RaciAssignment(activity_id="recv_5", role_id="role_inv_ctrl", role="I"),
                    # Report Discrepancies
                    RaciAssignment(activity_id="recv_6", role_id="role_recv_clerk", role="R"),
                    RaciAssignment(activity_id="recv_6", role_id="role_wh_mgr", role="A"),
                    RaciAssignment(activity_id="recv_6", role_id="role_purchasing", role="I"),
                    RaciAssignment(activity_id="recv_6", role_id="role_qa", role="C"),
                ],
            )
        )

        # ShipBob Issues Resolution Template
        templates.append(
            RaciMatrixTemplate(
                template_id="shipbob_issues_template",
                name="ShipBob Issues Resolution",
                description="RACI matrix for handling ShipBob fulfillment issues",
                matrix_type=RaciMatrixType.SHIPBOB_ISSUES,
                activities=[
                    RaciActivity(
                        id="sb_1",
                        name="Identify Issue",
                        description="Detect and document ShipBob fulfillment issue",
                        order=1,
                    ),
                    RaciActivity(
                        id="sb_2", name="Assess Impact", description="Evaluate customer and business impact", order=2
                    ),
                    RaciActivity(
                        id="sb_3",
                        name="Contact ShipBob",
                        description="Initiate communication with ShipBob support",
                        order=3,
                    ),
                    RaciActivity(
                        id="sb_4", name="Implement Resolution", description="Execute agreed resolution steps", order=4
                    ),
                    RaciActivity(
                        id="sb_5", name="Customer Communication", description="Update affected customers", order=5
                    ),
                    RaciActivity(
                        id="sb_6",
                        name="Monitor Resolution",
                        description="Track resolution progress and effectiveness",
                        order=6,
                    ),
                ],
                roles=[
                    RaciRole(
                        id="role_ops_mgr",
                        name="Operations Manager",
                        title="Operations Manager",
                        is_person=False,
                        order=1,
                    ),
                    RaciRole(
                        id="role_cs_rep",
                        name="Customer Service Rep",
                        title="Customer Service Representative",
                        is_person=False,
                        order=2,
                    ),
                    RaciRole(
                        id="role_fulfillment",
                        name="Fulfillment Coordinator",
                        title="Fulfillment Coordinator",
                        is_person=False,
                        order=3,
                    ),
                    RaciRole(
                        id="role_cs_mgr", name="CS Manager", title="Customer Service Manager", is_person=False, order=4
                    ),
                ],
                assignments=[
                    # Identify Issue
                    RaciAssignment(activity_id="sb_1", role_id="role_cs_rep", role="R"),
                    RaciAssignment(activity_id="sb_1", role_id="role_cs_mgr", role="A"),
                    RaciAssignment(activity_id="sb_1", role_id="role_fulfillment", role="I"),
                    # Assess Impact
                    RaciAssignment(activity_id="sb_2", role_id="role_cs_mgr", role="R"),
                    RaciAssignment(activity_id="sb_2", role_id="role_ops_mgr", role="A"),
                    RaciAssignment(activity_id="sb_2", role_id="role_cs_rep", role="C"),
                    # Contact ShipBob
                    RaciAssignment(activity_id="sb_3", role_id="role_fulfillment", role="R"),
                    RaciAssignment(activity_id="sb_3", role_id="role_ops_mgr", role="A"),
                    RaciAssignment(activity_id="sb_3", role_id="role_cs_mgr", role="I"),
                    # Implement Resolution
                    RaciAssignment(activity_id="sb_4", role_id="role_fulfillment", role="R"),
                    RaciAssignment(activity_id="sb_4", role_id="role_ops_mgr", role="A"),
                    RaciAssignment(activity_id="sb_4", role_id="role_cs_mgr", role="C"),
                    # Customer Communication
                    RaciAssignment(activity_id="sb_5", role_id="role_cs_rep", role="R"),
                    RaciAssignment(activity_id="sb_5", role_id="role_cs_mgr", role="A"),
                    RaciAssignment(activity_id="sb_5", role_id="role_ops_mgr", role="I"),
                    # Monitor Resolution
                    RaciAssignment(activity_id="sb_6", role_id="role_fulfillment", role="R"),
                    RaciAssignment(activity_id="sb_6", role_id="role_ops_mgr", role="A"),
                    RaciAssignment(activity_id="sb_6", role_id="role_cs_mgr", role="I"),
                ],
            )
        )

        # Data Collection Process Template
        templates.append(
            RaciMatrixTemplate(
                template_id="data_collection_template",
                name="Data Collection Process",
                description="RACI matrix for systematic data collection and analysis",
                matrix_type=RaciMatrixType.DATA_COLLECTION,
                activities=[
                    RaciActivity(
                        id="dc_1",
                        name="Define Requirements",
                        description="Specify data collection requirements and objectives",
                        order=1,
                    ),
                    RaciActivity(
                        id="dc_2",
                        name="Design Collection Method",
                        description="Create data collection methodology and tools",
                        order=2,
                    ),
                    RaciActivity(
                        id="dc_3", name="Collect Data", description="Execute data collection according to plan", order=3
                    ),
                    RaciActivity(
                        id="dc_4", name="Validate Data", description="Verify data quality and completeness", order=4
                    ),
                    RaciActivity(
                        id="dc_5",
                        name="Analyze Data",
                        description="Perform data analysis and generate insights",
                        order=5,
                    ),
                    RaciActivity(
                        id="dc_6", name="Report Findings", description="Create and distribute data reports", order=6
                    ),
                ],
                roles=[
                    RaciRole(
                        id="role_data_mgr", name="Data Manager", title="Data Management Lead", is_person=False, order=1
                    ),
                    RaciRole(id="role_analyst", name="Data Analyst", title="Data Analyst", is_person=False, order=2),
                    RaciRole(
                        id="role_bus_owner",
                        name="Business Owner",
                        title="Business Process Owner",
                        is_person=False,
                        order=3,
                    ),
                    RaciRole(id="role_it", name="IT Support", title="IT Support Specialist", is_person=False, order=4),
                ],
                assignments=[
                    # Define Requirements
                    RaciAssignment(activity_id="dc_1", role_id="role_bus_owner", role="R"),
                    RaciAssignment(activity_id="dc_1", role_id="role_data_mgr", role="A"),
                    RaciAssignment(activity_id="dc_1", role_id="role_analyst", role="C"),
                    # Design Collection Method
                    RaciAssignment(activity_id="dc_2", role_id="role_analyst", role="R"),
                    RaciAssignment(activity_id="dc_2", role_id="role_data_mgr", role="A"),
                    RaciAssignment(activity_id="dc_2", role_id="role_it", role="C"),
                    RaciAssignment(activity_id="dc_2", role_id="role_bus_owner", role="I"),
                    # Collect Data
                    RaciAssignment(activity_id="dc_3", role_id="role_analyst", role="R"),
                    RaciAssignment(activity_id="dc_3", role_id="role_data_mgr", role="A"),
                    RaciAssignment(activity_id="dc_3", role_id="role_it", role="C"),
                    # Validate Data
                    RaciAssignment(activity_id="dc_4", role_id="role_analyst", role="R"),
                    RaciAssignment(activity_id="dc_4", role_id="role_data_mgr", role="A"),
                    RaciAssignment(activity_id="dc_4", role_id="role_bus_owner", role="C"),
                    # Analyze Data
                    RaciAssignment(activity_id="dc_5", role_id="role_analyst", role="R"),
                    RaciAssignment(activity_id="dc_5", role_id="role_data_mgr", role="A"),
                    RaciAssignment(activity_id="dc_5", role_id="role_bus_owner", role="C"),
                    # Report Findings
                    RaciAssignment(activity_id="dc_6", role_id="role_analyst", role="R"),
                    RaciAssignment(activity_id="dc_6", role_id="role_data_mgr", role="A"),
                    RaciAssignment(activity_id="dc_6", role_id="role_bus_owner", role="I"),
                    RaciAssignment(activity_id="dc_6", role_id="role_it", role="I"),
                ],
            )
        )

        return templates

    async def create_matrix_from_template(
        self, template_id: str, name: str, description: Optional[str], created_by: UUID
    ) -> Tuple[RaciMatrix, List[str]]:
        """Create a new RACI matrix from a predefined template."""
        templates = self.get_matrix_templates()

        # Find the template
        template = next((t for t in templates if t.template_id == template_id), None)
        if not template:
            raise BadRequestError(f"Template with ID '{template_id}' not found")

        # Create payload from template
        payload = CreateRaciMatrixPayload(
            name=name,
            description=description or template.description,
            matrix_type=template.matrix_type,
            activities=template.activities,
            roles=template.roles,
            assignments=template.assignments,
            metadata={"created_from_template": template_id},
        )

        # Create the matrix
        return await self.create_matrix(payload, created_by)
