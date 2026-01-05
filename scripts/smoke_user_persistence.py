"""Smoke test for user persistence layer.

Verifies database connectivity, user insertion (idempotent), and retrieval.
Assumes migrations have been applied (run `alembic upgrade head` first).
"""

import uuid

from api.db import get_session
from api.models import User
from api.security import hash_password

SAMPLE_EMAIL = "smoke_user@example.com"
SAMPLE_PASSWORD = "testpass123"


def main() -> None:
    """Run the smoke test."""
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(SAMPLE_PASSWORD)

    with get_session() as session:
        # Check if user exists
        existing_user = session.query(User).filter(User.email == SAMPLE_EMAIL).first()
        if existing_user:
            print(f"Found existing user: id={existing_user.id} email={existing_user.email} is_active={existing_user.is_active} subscription_status={existing_user.subscription_status}")
            return

        # Create new user
        new_user = User(
            id=user_id,
            email=SAMPLE_EMAIL,
            password_hash=hashed_password,
            is_active=True,
            subscription_status=None,
        )
        session.add(new_user)
        session.commit()

        # Verify insertion
        fetched_user = session.query(User).filter(User.email == SAMPLE_EMAIL).first()
        if fetched_user:
            print(f"Created user: id={fetched_user.id} email={fetched_user.email} is_active={fetched_user.is_active} subscription_status={fetched_user.subscription_status}")
        else:
            raise ValueError("Failed to fetch inserted user")


if __name__ == "__main__":
    main()
