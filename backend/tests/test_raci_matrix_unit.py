"""Unit tests for RACI matrix functionality that don't require API calls."""

import pytest
from app.services.raci_service import RaciService
from app.models.raci_matrix import (
    RaciRoleType, RaciMatrixType, RaciMatrixTemplate
)


class TestRaciTemplates:
    """Test RACI matrix templates functionality."""
    
    def test_get_matrix_templates_returns_three_templates(self):
        """Test that get_matrix_templates returns exactly 3 templates."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        assert len(templates) == 3
    
    def test_template_ids_are_correct(self):
        """Test that template IDs match expected values."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        template_ids = [t.template_id for t in templates]
        assert "inventory_inbound_template" in template_ids
        assert "shipbob_issues_template" in template_ids
        assert "data_collection_template" in template_ids
    
    def test_inventory_template_structure(self):
        """Test the inventory inbound template has correct structure."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        inventory_template = next(t for t in templates if t.template_id == "inventory_inbound_template")
        
        # Check basic properties
        assert inventory_template.name == "Inventory Inbound Process"
        assert inventory_template.matrix_type == RaciMatrixType.INVENTORY_INBOUND
        assert len(inventory_template.activities) == 6
        assert len(inventory_template.roles) == 5
        
        # Check activity names
        activity_names = [a.name for a in inventory_template.activities]
        assert "Receive Shipment" in activity_names
        assert "Verify Contents" in activity_names
        assert "Quality Inspection" in activity_names
        assert "Update Inventory System" in activity_names
        assert "Store Items" in activity_names
        assert "Report Discrepancies" in activity_names
        
        # Check role names
        role_names = [r.name for r in inventory_template.roles]
        assert "Warehouse Manager" in role_names
        assert "Receiving Clerk" in role_names
        assert "QA Inspector" in role_names
        assert "Inventory Controller" in role_names
        assert "Purchasing" in role_names
    
    def test_all_templates_have_valid_assignments(self):
        """Test that all templates have valid activity-role assignments."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        for template in templates:
            # Get all activity and role IDs
            activity_ids = {a.id for a in template.activities}
            role_ids = {r.id for r in template.roles}
            
            # Check each assignment references valid IDs
            for assignment in template.assignments:
                assert assignment.activity_id in activity_ids, f"Invalid activity ID {assignment.activity_id} in template {template.template_id}"
                assert assignment.role_id in role_ids, f"Invalid role ID {assignment.role_id} in template {template.template_id}"
                assert assignment.role in [RaciRoleType.RESPONSIBLE, RaciRoleType.ACCOUNTABLE, 
                                         RaciRoleType.CONSULTED, RaciRoleType.INFORMED]
    
    def test_all_activities_have_r_and_a_assignments(self):
        """Test that all activities in templates have at least one R and one A assignment."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        for template in templates:
            for activity in template.activities:
                # Get all assignments for this activity
                activity_assignments = [a for a in template.assignments if a.activity_id == activity.id]
                assignment_roles = [a.role for a in activity_assignments]
                
                # Check for R and A
                assert RaciRoleType.RESPONSIBLE in assignment_roles, \
                    f"Activity {activity.name} in template {template.template_id} has no Responsible assignment"
                assert RaciRoleType.ACCOUNTABLE in assignment_roles, \
                    f"Activity {activity.name} in template {template.template_id} has no Accountable assignment"
    
    def test_shipbob_template_activities(self):
        """Test ShipBob template has correct activities."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        shipbob_template = next(t for t in templates if t.template_id == "shipbob_issues_template")
        
        assert len(shipbob_template.activities) == 6
        activity_names = [a.name for a in shipbob_template.activities]
        assert "Identify Issue" in activity_names
        assert "Assess Impact" in activity_names
        assert "Contact ShipBob" in activity_names
        assert "Implement Resolution" in activity_names
        assert "Customer Communication" in activity_names
        assert "Monitor Resolution" in activity_names
    
    def test_data_collection_template_roles(self):
        """Test data collection template has correct roles."""
        service = RaciService()
        templates = service.get_matrix_templates()
        
        data_template = next(t for t in templates if t.template_id == "data_collection_template")
        
        assert len(data_template.roles) == 4
        role_names = [r.name for r in data_template.roles]
        assert "Data Manager" in role_names
        assert "Data Analyst" in role_names
        assert "Business Owner" in role_names
        assert "IT Support" in role_names