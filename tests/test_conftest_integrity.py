import pytest
from sqlalchemy import text

def test_db_session_fixture(db_session):
    """Verify that the db_session fixture works and can execute queries."""
    result = db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1

def test_test_user_fixture(test_user):
    """Verify that the test_user fixture creates a user."""
    assert test_user.email == "test@example.com"
    assert test_user.id == "test-uuid-123"

def test_client_fixture(client):
    """Verify that the client fixture works."""
    # Just check that it's not None, actual requests might fail if routes aren't set up
    assert client is not None