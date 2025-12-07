"""
Centralized dependency wiring for FastAPI.
Provides singletons of ConnectionManager, ExperimentManager, and SimulationManager.
"""

import os
from typing import Any, Dict, Optional, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from fba_bench_api.api.connection import ConnectionManager
from fba_bench_api.api.experiment import ExperimentManager
from fba_bench_api.api.security import ALGORITHM, SECRET_KEY
from fba_bench_api.api.simulation import SimulationManager

# Shared singletons
connection_manager = ConnectionManager()
experiment_manager = ExperimentManager()
simulation_manager = SimulationManager()

__all__ = [
    "ConnectionManager",
    "ExperimentManager",
    "SimulationManager",
    "connection_manager",
    "experiment_manager",
    "simulation_manager",
    "get_current_user",
    "get_tenant_context",
    "TenantContext",
]

security = HTTPBearer(auto_error=False)


def get_current_user(token: str = Depends(security)) -> Optional[Dict[str, Any]]:
    """
    Get current user dependency. In test mode (AUTH_ENABLED=false), returns anonymous user.
    """
    if os.getenv("AUTH_ENABLED", "false").lower() != "true":
        return {"sub": "anonymous", "roles": []}
    
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


class TenantContext(BaseModel):
    tenant_id: str
    user_id: str
    roles: List[str]


async def get_tenant_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TenantContext:
    """
    Extract tenant context from Authorization header using JWT validation.
    
    In production, this integrates with Auth0 or similar IAM to decode JWT claims 
    for tenant_id, user_id, and roles.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    token = credentials.credentials
    
    try:
        # Verify and decode the JWT token
        # Note: In a real multi-tenant setup, you might need to fetch the public key 
        # from the identity provider (e.g., Auth0 JWKS endpoint) instead of using a shared secret.
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Extract claims. Adjust these keys based on your actual JWT structure.
        # For example, Auth0 might use custom namespaced claims like 'https://myapp.com/tenant_id'
        tenant_id = payload.get("tenant_id")
        user_id = payload.get("sub") or payload.get("user_id")
        roles = payload.get("roles", [])
        
        if not tenant_id or not user_id:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required tenant or user claims",
            )

        return TenantContext(tenant_id=tenant_id, user_id=user_id, roles=roles)
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate tenant context: {str(e)}",
        )
    except HTTPException:
        # Re-raise HTTPExceptions (like the one for missing claims)
        raise
    except Exception as e:
        # Catch-all for other errors to ensure we don't leak internal details but still fail safe
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
