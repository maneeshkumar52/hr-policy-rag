"""Tests for JWT auth and RBAC."""
import pytest
from src.auth import create_test_token, validate_token, MOCK_USERS


def test_validate_token_employee():
    token = create_test_token("user-001")
    user = validate_token(f"Bearer {token}")
    assert user.role == "employee"
    assert user.clearance_level == 1


def test_validate_token_manager():
    token = create_test_token("user-002")
    user = validate_token(f"Bearer {token}")
    assert user.role == "manager"
    assert user.clearance_level == 2


def test_validate_token_hr_admin():
    token = create_test_token("user-003")
    user = validate_token(f"Bearer {token}")
    assert user.role == "hr_admin"
    assert user.clearance_level == 3


def test_invalid_token_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        validate_token("Bearer invalid-token-here")
    assert exc_info.value.status_code == 401


def test_no_token_returns_dev_user():
    user = validate_token(None)
    assert user is not None
    assert user.role == "employee"
