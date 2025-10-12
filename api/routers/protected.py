"""Protected routes requiring JWT authentication."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.security.jwt import get_current_user
from api.models import User

from fba_bench_core.benchmarking.engine import (
    EngineConfig,
    EngineReport,
    run_benchmark,
)

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("/test")
def protected_test(current_user: User = Depends(get_current_user)):
    """Return the current user's identifiers (for tests)."""
    return {"user_id": current_user.id, "email": current_user.email}


@router.post("/run-benchmark", response_model=EngineReport, status_code=status.HTTP_200_OK)
async def run_enterprise_benchmark(
    config: EngineConfig,
    current_user: User = Depends(get_current_user),
):
    """Run an enterprise benchmark asynchronously via the core engine."""
    try:
        report = await run_benchmark(config)
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected engine failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Benchmark execution failed",
        ) from exc

    return report
