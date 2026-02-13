from __future__ import annotations

import os
from typing import List

from fba_bench_core.config import get_settings


def _load_public_keys_from_env() -> List[str]:
    keys: List[str] = []
    # 1) Single key (back-compat)
    single = os.getenv("AUTH_JWT_PUBLIC_KEY") or os.getenv("FBA_AUTH_JWT_PUBLIC_KEY")
    if single and single.strip():
        keys.append(single.strip())

    # 2) Multiple keys in one env var (separated by '||' or ';' or PEM terminator)
    multi = os.getenv("AUTH_JWT_PUBLIC_KEYS") or os.getenv("FBA_AUTH_JWT_PUBLIC_KEYS")
    if multi:
        parts: List[str] = []
        # Prefer PEM block splitting if present
        pem_sep = "\n-----END PUBLIC KEY-----\n"
        if pem_sep in multi:
            chunks = multi.split(pem_sep)
            parts = [c + "-----END PUBLIC KEY-----" for c in chunks if c.strip()]
        elif "||" in multi:
            parts = [p for p in multi.split("||") if p.strip()]
        elif ";" in multi:
            parts = [p for p in multi.split(";") if p.strip()]
        else:
            parts = [multi]
        for p in parts:
            p = p.strip()
            if p:
                keys.append(p)

    # 3) Load from file if provided
    key_file = os.getenv("AUTH_JWT_PUBLIC_KEY_FILE") or os.getenv(
        "FBA_AUTH_JWT_PUBLIC_KEY_FILE"
    )
    if key_file:
        try:
            with open(key_file, encoding="utf-8") as fh:
                content = fh.read().strip()
                if content:
                    keys.append(content)
        except Exception:
            # Fail open to allow single-key configurations still to work
            pass

    # De-duplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


_settings = get_settings()

AUTH_JWT_ALG = _settings.auth_jwt_alg
AUTH_JWT_ISSUER = _settings.auth_jwt_issuer
AUTH_JWT_AUDIENCE = _settings.auth_jwt_audience
AUTH_JWT_CLOCK_SKEW = _settings.auth_jwt_clock_skew
AUTH_JWT_PUBLIC_KEY = _settings.auth_jwt_public_key
AUTH_JWT_PUBLIC_KEYS = _load_public_keys_from_env()

AUTH_ENABLED = _settings.auth_enabled
AUTH_TEST_BYPASS = _settings.auth_test_bypass
AUTH_PROTECT_DOCS = _settings.auth_protect_docs
