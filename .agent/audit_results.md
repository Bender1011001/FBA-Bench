# Production Readiness Audit Report Card

**Date:** 2026-01-05
**Auditor:** Antigravity (Principal Security Researcher)

## 1. Executive Summary
The codebase is **NOT production-ready** and contains **CRITICAL** security vulnerabilities that would lead to immediate compromise if deployed. While the core simulation logic is sophisticated, the security layer is effectively "dummy" mode by default, secrets are exposed in the repository, and key architectural components ("God Classes") pose significant stability risks under load.

## 2. Prioritized Action List

| Severity | Issue | File/Line | Suggested Fix |
| :--- | :--- | :--- | :--- |
| **CRITICAL** | **Secrets Committed to Repo** | `.env`, `.env.prod` | Remove immediately. Revoke all exposed keys (OpenAI, Stripe). Use a secrets manager. |
| **CRITICAL** | **Auth Disabled by Default** | `dependencies.py:43` | Remove `AUTH_ENABLED` check. Secure by default. Authentication must be opt-out, not opt-in. |
| **CRITICAL** | **Session Invalidation** | `api/security.py:15` | `SECRET_KEY` is random on startup. Tokens die on restart. Load from env or fail. |
| **HIGH** | **WebSocket Auth Bypass** | `realtime.py:313` | Remove logic allowing "dev/demo" bypass if token is missing. Enforce JWT. |
| **HIGH** | **Resource Leak** | `AgentManager.py:325` | `EventBus` shim does not support `unsubscribe`. Listeners leak on reload/stop. Fix `EventBus` shim. |
| **MEDIUM** | **God Class Anti-Pattern** | `AgentManager.py` | 1200+ LOC. Splits responsibilities. Break into `LifecycleManager` vs `Orchestrator`. |
| **MEDIUM** | **Swallowed Exceptions** | `AgentManager.py:605` | Errors logged but often swallowed in decision loops. Improve error visibility. |

---

## 3. Code Fixes (Critical & High)

### Fix 1: Secure Authentication Dependencies (Critical)
**File:** `src/fba_bench_api/api/dependencies.py`
**Issue:** Auth is skipped if `AUTH_ENABLED` is not "true".
**Fix:** Remove the bypass. Fail if auth is missing.

```python
def get_current_user(token: str = Depends(security)) -> Optional[Dict[str, Any]]:
    """
    Get current user dependency. 
    REMOVED: Unsafe 'AUTH_ENABLED' bypass. Auth is now mandatory.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    try:
        # Pydantic/FastAPI might pass the object, extract credentials
        token_str = token.credentials if hasattr(token, "credentials") else str(token)
        payload = jwt.decode(token_str, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
```

### Fix 2: Stable & Secure Secret Key (Critical)
**File:** `src/fba_bench_api/api/security.py`
**Issue:** `SECRET_KEY` generated dynamically invalidates sessions on restart.
**Fix:** Enforce loading from environment.

```python
import os

# JWT Configuration
# CRITICAL: Fail safely if SECRET_KEY is missing in production
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Allow loose defaults ONLY in non-production if explicitly flagged, otherwise fail
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("FATAL: SECRET_KEY must be set in production!")
    else:
        # Fallback for local dev only - still risky but better than silent random
        logger.warning("Using unsafe default SECRET_KEY for development.")
        SECRET_KEY = "dev-secret-change-me" 

ALGORITHM = "HS256"
```

### Fix 3: Enforce WebSocket Authentication (High)
**File:** `src/fba_bench_api/api/routes/realtime.py`
**Issue:** Logic allows bypassing auth if `effective_token` is missing.
**Fix:** Enforce auth.

```python
    # ... inside websocket_realtime function ...

    if public_key:
        if not effective_token:
            # FIX: Do not allow bypass. Close connection.
            logger.error("WS connection missing token. Closing.")
            await websocket.close(code=1008) # Policy Violation
            return
        else:
            try:
                # ... existing verification logic ...
            except Exception as e:
                logger.error(f"WS JWT verification failed: {e}")
                await websocket.close(code=1008)
                return
    else:
        # Fallback if no public key configured (Dev only)
        if os.getenv("ENVIRONMENT") == "production":
             logger.error("WS Authentication not configured in production. Closing.")
             await websocket.close(code=1011)
             return
```

## 4. Stability & Quality Notes
*   **AgentManager**: The `AgentManager` is doing too much. It handles backward compatibility, decision making, event bus arbitration, and lifecycle. Recommend extracting the "BackCompat" logic into a completely separate adapter class to clean up the core logic.
*   **EventBus Leak**: The shim implementation of `EventBus` must be updated to support `unsubscribe`. Currently, `AgentManager` tries to unsubscribe but catches expected errors. In a long-running process where agents are added/removed, this will lead to a memory leak and "zombie" listeners processing events.

**Validation Status:**
*   SQL Injection: **PASSED** (Parameterized queries used correctly).
*   XSS: **PASSED** (FastAPI/Pydantic validation handles most cases; no raw HTML rendering found in API).
*   Secrets: **FAILED** (Found in `.env`).

**Recommendation:** Do not launch until Critical issues are resolved.
