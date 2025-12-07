import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from fba_bench_api.api.dependencies import get_tenant_context, TenantContext
from fba_bench_api.api.security import SECRET_KEY, ALGORITHM

@pytest.mark.asyncio
async def test_get_tenant_context_valid_token():
    """Test that a valid token returns the correct TenantContext."""
    payload = {
        "tenant_id": "tenant-123",
        "sub": "user-456",
        "roles": ["admin", "editor"]
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    ctx = await get_tenant_context(credentials)
    
    assert isinstance(ctx, TenantContext)
    assert ctx.tenant_id == "tenant-123"
    assert ctx.user_id == "user-456"
    assert ctx.roles == ["admin", "editor"]

@pytest.mark.asyncio
async def test_get_tenant_context_missing_claims():
    """Test that a token missing required claims raises 401."""
    # Missing tenant_id
    payload = {
        "sub": "user-456",
        "roles": ["admin"]
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    with pytest.raises(HTTPException) as exc_info:
        await get_tenant_context(credentials)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Token missing required tenant or user claims" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_tenant_context_invalid_token():
    """Test that an invalid token raises 401."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.string")
    
    with pytest.raises(HTTPException) as exc_info:
        await get_tenant_context(credentials)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate tenant context" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_tenant_context_missing_credentials():
    """Test that missing credentials raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_tenant_context(None)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Missing authentication credentials" in exc_info.value.detail
