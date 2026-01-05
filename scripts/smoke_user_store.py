"""Smoke test for user store: insert and fetch a test user idempotently.

Verifies database connectivity, model persistence, and password hashing.
"""

import json
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

# Add repo root to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.db import SessionLocal
from api.models import User
from api.security.passwords import hash_password, verify_password


def main() -> int:
    load_dotenv()  # Load environment variables

    email = "smoke@example.com"
    plain_password = "Password123!demo"
    user_id = str(uuid4())

    with SessionLocal() as db:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"User with email '{email}' already exists. Skipping insertion.")
            # Verify password on existing user
            if not verify_password(plain_password, existing_user.password_hash):
                print("Password verification failed for existing user.")
                return 1
    
            print("Password verified successfully.")
    
            # Fetch and print safe fields
            output = {
                "id": existing_user.id,
                "email": existing_user.email,
                "is_active": existing_user.is_active,
                "subscription_status": existing_user.subscription_status,
            }
            print(json.dumps(output, default=str))
            return 0

        # Create new user
        password_hash = hash_password(plain_password)
        new_user = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            is_active=True,
        )
        db.add(new_user)

        try:
            db.commit()
            db.refresh(new_user)  # Ensure updated_at is set
        except IntegrityError:
            db.rollback()
            print(f"Failed to insert user with email '{email}'. Possible duplicate.")
            return 1

        # Fetch by email to verify
        fetched_user = db.query(User).filter(User.email == email).first()
        if not fetched_user:
            print("Failed to fetch inserted user.")
            return 1

        # Verify password
        if not verify_password(plain_password, fetched_user.password_hash):
            print("Password verification failed.")
            return 1

        print("Password verified successfully.")

        # Print safe fields (omit password_hash)
        output = {
            "id": fetched_user.id,
            "email": fetched_user.email,
            "is_active": fetched_user.is_active,
            "subscription_status": fetched_user.subscription_status,
        }
        print(json.dumps(output, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
