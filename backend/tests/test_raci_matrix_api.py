import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4
import json
from datetime import datetime

from app.main import app
from app.models.user import User
from app.models.raci_matrix import (
    RaciMatrix, RaciActivity, RaciRole, RaciAssignment,
    RaciMatrixType, RaciRoleType, RaciMatrixTemplate
)
from app.auth.dependencies import get_current_user


class TestRaciMatrixAPI:
    """Test RACI matrix API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Create mock authenticated user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        return {"Authorization": "Bearer test-token"}
    
    @pytest.fixture
    def sample_matrix(self):
        """Create a sample RACI matrix."""
        return RaciMatrix(
            id=uuid4(),
            name="Test Matrix",
            description="Test Description",
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
            is_active=True
        )
    
    # Test update assignments endpoint
    
    @patch('app.api.raci_matrix.RaciService')
    def test_update_assignments_success(self, mock_service_class, client, mock_user, auth_headers, sample_matrix):
        """Test successful assignment update."""
        mock_service = mock_service_class.return_value
        mock_service.update_assignments = AsyncMock(return_value=(True, []))
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            payload = {
                "assignments": [
                    {
                        "activity_id": "act1",
                        "role_id": "role2",
                        "role": "C",
                        "notes": "Updated assignment"
                    }
                ]
            }
            
            response = client.patch(
                f"/api/v1/raci-matrices/{sample_matrix.id}/assignments",
                json=payload,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["warnings"] == []
    
    @patch('app.api.raci_matrix.RaciService')
    def test_update_assignments_with_warnings(self, mock_service_class, client, mock_user, auth_headers, sample_matrix):
        """Test assignment update with warnings."""
        mock_service = mock_service_class.return_value
        mock_service.update_assignments = AsyncMock(
            return_value=(True, ["Assignment references invalid activity ID: invalid_act"])
        )
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            payload = {
                "assignments": [
                    {
                        "activity_id": "invalid_act",
                        "role_id": "role1",
                        "role": "R"
                    }
                ]
            }
            
            response = client.patch(
                f"/api/v1/raci-matrices/{sample_matrix.id}/assignments",
                json=payload,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["warnings"]) == 1
            assert "invalid activity ID" in data["warnings"][0]
    
    @patch('app.api.raci_matrix.RaciService')
    def test_update_assignments_matrix_not_found(self, mock_service_class, client, mock_user, auth_headers):
        """Test update assignments for non-existent matrix."""
        from app.core.exceptions import ResourceNotFoundError
        
        mock_service = mock_service_class.return_value
        mock_service.update_assignments = AsyncMock(
            side_effect=ResourceNotFoundError(resource_name="RACI Matrix", resource_id="test-id")
        )
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            payload = {"assignments": []}
            
            response = client.patch(
                f"/api/v1/raci-matrices/{uuid4()}/assignments",
                json=payload,
                headers=auth_headers
            )
            
            assert response.status_code == 404
    
    # Test bulk assign endpoint
    
    @patch('app.api.raci_matrix.RaciService')
    def test_bulk_assign_success(self, mock_service_class, client, mock_user, auth_headers, sample_matrix):
        """Test successful bulk assignment."""
        mock_service = mock_service_class.return_value
        mock_service.bulk_assign = AsyncMock(return_value=(4, []))
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            payload = {
                "activity_ids": ["act1", "act2"],
                "role_ids": ["role1", "role2"],
                "role_type": "C",
                "notes": "Bulk assigned as consulted",
                "clear_existing": False
            }
            
            response = client.post(
                f"/api/v1/raci-matrices/{sample_matrix.id}/bulk-assign",
                json=payload,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["updated_count"] == 4
            assert data["warnings"] == []
    
    @patch('app.api.raci_matrix.RaciService')
    def test_bulk_assign_with_clear_existing(self, mock_service_class, client, mock_user, auth_headers, sample_matrix):
        """Test bulk assignment with clear existing flag."""
        mock_service = mock_service_class.return_value
        mock_service.bulk_assign = AsyncMock(return_value=(2, []))
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            payload = {
                "activity_ids": ["act1"],
                "role_ids": ["role1", "role2"],
                "role_type": "I",
                "clear_existing": True
            }
            
            response = client.post(
                f"/api/v1/raci-matrices/{sample_matrix.id}/bulk-assign",
                json=payload,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["updated_count"] == 2
    
    # Test validate complete endpoint
    
    @patch('app.api.raci_matrix.RaciService')
    def test_validate_complete_valid_matrix(self, mock_service_class, client, mock_user, auth_headers, sample_matrix):
        """Test comprehensive validation on valid matrix."""
        mock_service = mock_service_class.return_value
        mock_service.validate_matrix_complete = AsyncMock(
            return_value=(True, {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "stats": {
                    "total_activities": 2,
                    "total_roles": 2,
                    "total_assignments": 2,
                    "assignments_by_type": {"R": 1, "A": 1, "C": 0, "I": 0}
                }
            })
        )
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            response = client.post(
                f"/api/v1/raci-matrices/{sample_matrix.id}/validate-complete",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["is_valid"] is True
            assert len(data["errors"]) == 0
            assert data["stats"]["total_activities"] == 2
    
    @patch('app.api.raci_matrix.RaciService')
    def test_validate_complete_invalid_matrix(self, mock_service_class, client, mock_user, auth_headers, sample_matrix):
        """Test comprehensive validation on invalid matrix."""
        mock_service = mock_service_class.return_value
        mock_service.validate_matrix_complete = AsyncMock(
            return_value=(False, {
                "is_valid": False,
                "errors": [
                    "Activity 'Activity 2' has no Responsible (R) assignment",
                    "Activity 'Activity 2' has no Accountable (A) assignment"
                ],
                "warnings": ["Role 'Role 3' has no assignments"],
                "stats": {
                    "total_activities": 2,
                    "total_roles": 3,
                    "total_assignments": 2,
                    "assignments_by_type": {"R": 1, "A": 1, "C": 0, "I": 0}
                }
            })
        )
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            response = client.post(
                f"/api/v1/raci-matrices/{sample_matrix.id}/validate-complete",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["is_valid"] is False
            assert len(data["errors"]) == 2
            assert len(data["warnings"]) == 1
    
    # Test get templates endpoint
    
    @patch('app.api.raci_matrix.RaciService')
    def test_get_templates(self, mock_service_class, client, mock_user, auth_headers):
        """Test getting RACI matrix templates."""
        mock_service = mock_service_class.return_value
        mock_templates = [
            RaciMatrixTemplate(
                template_id="test_template",
                name="Test Template",
                description="Test template description",
                matrix_type=RaciMatrixType.CUSTOM,
                activities=[
                    RaciActivity(id="t_act1", name="Template Activity", order=1)
                ],
                roles=[
                    RaciRole(id="t_role1", name="Template Role", order=1)
                ],
                assignments=[
                    RaciAssignment(activity_id="t_act1", role_id="t_role1", role=RaciRoleType.RESPONSIBLE)
                ]
            )
        ]
        mock_service.get_matrix_templates = Mock(return_value=mock_templates)
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            response = client.get(
                "/api/v1/raci-matrices/templates",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["template_id"] == "test_template"
            assert data[0]["name"] == "Test Template"
    
    # Test create from template endpoint
    
    @patch('app.api.raci_matrix.RaciService')
    def test_create_from_template_success(self, mock_service_class, client, mock_user, auth_headers):
        """Test creating matrix from template."""
        created_matrix = RaciMatrix(
            id=uuid4(),
            name="My Process",
            description="Created from template",
            matrix_type=RaciMatrixType.INVENTORY_INBOUND,
            activities=[],
            roles=[],
            assignments=[],
            is_active=True
        )
        
        mock_service = mock_service_class.return_value
        mock_service.create_matrix_from_template = AsyncMock(
            return_value=(created_matrix, [])
        )
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            response = client.post(
                "/api/v1/raci-matrices/templates/inventory_inbound_template",
                params={
                    "name": "My Process",
                    "description": "Created from template"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["matrix"]["name"] == "My Process"
            assert data["warnings"] == []
    
    @patch('app.api.raci_matrix.RaciService')
    def test_create_from_template_invalid_template(self, mock_service_class, client, mock_user, auth_headers):
        """Test creating matrix from invalid template."""
        from app.core.exceptions import BadRequestError
        
        mock_service = mock_service_class.return_value
        mock_service.create_matrix_from_template = AsyncMock(
            side_effect=BadRequestError("Template with ID 'invalid_template' not found")
        )
        
        with patch.object(app.dependency_overrides, get_current_user.__name__, return_value=mock_user):
            response = client.post(
                "/api/v1/raci-matrices/templates/invalid_template",
                params={"name": "Test"},
                headers=auth_headers
            )
            
            assert response.status_code == 400
            assert "Template with ID 'invalid_template' not found" in response.json()["detail"]
    
    # Test authentication requirements
    
    def test_endpoints_require_authentication(self, client):
        """Test that all endpoints require authentication."""
        matrix_id = uuid4()
        
        # All requests should fail with API key required error (500 status due to middleware exception handling)
        # The API uses API key authentication middleware, not JWT
        
        # Test update assignments
        response = client.patch(f"/api/v1/raci-matrices/{matrix_id}/assignments", json={"assignments": []})
        assert response.status_code == 500
        assert "API key required" in response.text or "authentication" in response.text.lower()
        
        # Test bulk assign
        response = client.post(f"/api/v1/raci-matrices/{matrix_id}/bulk-assign", json={
            "activity_ids": [], "role_ids": [], "role_type": "R", "clear_existing": False
        })
        assert response.status_code == 500
        assert "API key required" in response.text or "authentication" in response.text.lower()
        
        # Test validate complete
        response = client.post(f"/api/v1/raci-matrices/{matrix_id}/validate-complete")
        assert response.status_code == 500
        assert "API key required" in response.text or "authentication" in response.text.lower()
        
        # Test get templates
        response = client.get("/api/v1/raci-matrices/templates")
        assert response.status_code == 500
        assert "API key required" in response.text or "authentication" in response.text.lower()
        
        # Test create from template
        response = client.post("/api/v1/raci-matrices/templates/test", params={"name": "Test"})
        assert response.status_code == 500
        assert "API key required" in response.text or "authentication" in response.text.lower()