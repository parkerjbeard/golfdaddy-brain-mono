from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.user import User, UserRole


def test_user_model_valid_role_coercion():
    data = {
        "id": uuid4(),
        "email": "test@example.com",
        "role": "developer",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    user = User(**data)
    assert user.role == UserRole.DEVELOPER


def test_user_model_invalid_email():
    with pytest.raises(ValidationError):
        User(
            id=uuid4(),
            email="not-email",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )


def test_user_model_missing_id():
    with pytest.raises(ValidationError):
        User(email="a@b.com", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
