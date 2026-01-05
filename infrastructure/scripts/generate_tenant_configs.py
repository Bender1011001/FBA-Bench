#!/usr/bin/env python3
"""
Tenant config generator: renders .env and terraform.tfvars from templates with ${VAR} placeholders
using Python's string.Template for safe substitution.

Precedence: CLI args > defaults (no env var override for simplicity in this step).

All specified tokens are substituted; unknown/extra tokens remain as ${VAR} via safe_substitute.
Generation is idempotent: skips existing files unless --force.
No external dependencies; stdlib only.
"""

from __future__ import annotations

import argparse
import re
import secrets
import string
import sys
from pathlib import Path
from typing import Dict


def main() -> int:
    here = Path(__file__).resolve()
    infra_dir = here.parent.parent
    templates_dir = infra_dir / "templates"

    parser = argparse.ArgumentParser(
        description="Generate per-tenant .env and terraform.tfvars from templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_tenant_configs.py -t demo -d demo.example.com --api-url http://localhost:8000 --web-url http://localhost:5173 --stripe-public-key pk_test_123 --price-id price_ABC --jwt-secret CHANGE_ME_DEV
        """
    )
    parser.add_argument("-t", "--tenant", required=True, help="Tenant slug (e.g., 'demo'; validates [a-z0-9-]+)")
    parser.add_argument("-d", "--domain", default="example.com", help="Domain name (default: example.com)")
    parser.add_argument("-e", "--env", default="sandbox", help="Environment (default: sandbox)")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API public base URL (default: http://localhost:8000)")
    parser.add_argument("--web-url", default="http://localhost:5173", help="Frontend base URL (default: http://localhost:5173)")
    parser.add_argument("--database-url", default="sqlite:///./enterprise.db", help="Database URL (default: sqlite:///./enterprise.db)")
    parser.add_argument("--stripe-public-key", default="pk_test_CHANGE_ME", help="Stripe public key (default: pk_test_CHANGE_ME)")
    parser.add_argument("--price-id", default="price_123CHANGE_ME", help="Default Stripe price ID (default: price_123CHANGE_ME)")
    parser.add_argument("--jwt-secret", default=None, help="JWT secret (default: generates secure random string)")
    parser.add_argument("--stripe-secret-key", default=None, help="Stripe secret key (optional; default: empty string)")
    parser.add_argument("--stripe-webhook-secret", default=None, help="Stripe webhook secret (optional; default: empty string)")
    parser.add_argument("--api-image-tag", default="latest", help="API Docker image tag (default: latest)")
    parser.add_argument("--web-image-tag", default="latest", help="Web Docker image tag (default: latest)")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: infrastructure/tenants/<tenant>)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    args = parser.parse_args()

    tenant = args.tenant.strip().lower()
    # Issue 73: Tightened regex to require at least one alphanumeric character
    if not re.match(r"^(?=.*[a-z0-9])[a-z0-9-]+$", tenant):
        print(f"ERROR: Invalid tenant slug '{args.tenant}': must match [a-z0-9-]+ and contain at least one alphanumeric character.", file=sys.stderr)
        return 1

    default_out = infra_dir / "tenants" / tenant
    out_dir = Path(args.out_dir) if args.out_dir else default_out

    # Issue 71: Secure default for JWT_SECRET
    if args.jwt_secret:
        jwt_secret = args.jwt_secret
        if jwt_secret == "CHANGE_ME_DEV" and args.env not in ("sandbox", "dev", "local"):
            print(f"ERROR: Unsafe JWT_SECRET 'CHANGE_ME_DEV' not allowed in environment '{args.env}'.", file=sys.stderr)
            return 1
    else:
        jwt_secret = secrets.token_urlsafe(32)
        print(f"INFO: Generated secure JWT_SECRET for tenant '{tenant}'")

    # Issue 72: Configurable DATABASE_URL
    database_url = args.database_url

    # Build mapping (CLI args only; no env var precedence for simplicity)
    mapping: Dict[str, str] = {
        "DATABASE_URL": database_url,
        "DOMAIN_NAME": args.domain,
        "ENVIRONMENT": args.env,
        "API_IMAGE_TAG": args.api_image_tag,
        "WEB_IMAGE_TAG": args.web_image_tag,
        "API_PUBLIC_BASE_URL": args.api_url,
        "FRONTEND_BASE_URL": args.web_url,
        "STRIPE_PUBLIC_KEY": args.stripe_public_key,
        "STRIPE_PRICE_ID_DEFAULT": args.price_id,
        "JWT_SECRET": jwt_secret,
        "STRIPE_SECRET_KEY": args.stripe_secret_key or "",
        "STRIPE_WEBHOOK_SECRET": args.stripe_webhook_secret or "",
    }

    # Load templates
    env_template_path = templates_dir / ".env.template"
    tfvars_template_path = templates_dir / "terraform.tfvars.template"

    try:
        env_template = env_template_path.read_text(encoding="utf-8")
        tfvars_template = tfvars_template_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Failed to read templates from {templates_dir}: {e}", file=sys.stderr)
        return 2

    # Render with safe_substitute (leaves unsubstituted ${VAR} for extras/unknowns)
    env_t = string.Template(env_template)
    tfvars_t = string.Template(tfvars_template)
    env_rendered = env_t.safe_substitute(mapping)
    tfvars_rendered = tfvars_t.safe_substitute(mapping)

    # Write outputs (idempotent: skip if exists unless --force)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"ERROR: Failed to create output directory {out_dir}: {e}", file=sys.stderr)
        return 3

    env_out = out_dir / ".env"
    tfvars_out = out_dir / "terraform.tfvars"

    try:
        # Track actions for summary
        actions = []

        if env_out.exists() and not args.force:
            actions.append(f"Skipped (exists): {env_out.resolve()}")
        else:
            env_out.write_text(env_rendered, encoding="utf-8", newline="\n")
            action = "Wrote" if not env_out.exists() else "Overwrote"
            actions.append(f"{action}: {env_out.resolve()}")

        if tfvars_out.exists() and not args.force:
            actions.append(f"Skipped (exists): {tfvars_out.resolve()}")
        else:
            tfvars_out.write_text(tfvars_rendered, encoding="utf-8", newline="\n")
            action = "Wrote" if not tfvars_out.exists() else "Overwrote"
            actions.append(f"{action}: {tfvars_out.resolve()}")

        # Print summary
        print("\nGeneration summary:")
        print(f"Output directory: {out_dir.resolve()}")
        for a in actions:
            print(f"  - {a}")
        print("Note: Generated files are git-ignored; do not commit real secrets.")

        return 0
    except Exception as e:
        print(f"ERROR: Failed writing outputs under {out_dir}: {e}", file=sys.stderr)
        return 4

if __name__ == "__main__":
    sys.exit(main())
