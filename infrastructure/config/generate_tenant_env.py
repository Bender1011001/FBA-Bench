#!/usr/bin/env python3
"""
Per-tenant configuration generator for FBA-Bench Enterprise.

Renders templates for backend .env and optional Terraform .tfvars files.
Uses string.Template for simple placeholder substitution.
Zero external dependencies beyond Python standard library.
"""

import argparse
from pathlib import Path
from string import Template
from typing import Dict


def render_template(template_path: Path, substitutions: Dict[str, str]) -> str:
    """Render a template file with given substitutions."""
    with open(template_path) as f:
        template_content = f.read()
    template = Template(template_content)
    return template.safe_substitute(substitutions)


def ensure_dir(parent_dir: Path):
    """Create directory if it doesn't exist."""
    parent_dir.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-tenant .env and optional .tfvars files from templates."
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant identifier (e.g., 'acme')"
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Domain for the tenant (e.g., 'dev.example.com')"
    )
    parser.add_argument(
        "--public-app-base-url",
        default="http://localhost:5173",
        help="Public app base URL (default: http://localhost:5173)"
    )
    parser.add_argument(
        "--environment",
        default="dev",
        help="Environment (default: dev)"
    )
    parser.add_argument(
        "--api-image-tag",
        default="latest",
        help="API Docker image tag (default: latest)"
    )
    parser.add_argument(
        "--frontend-image-tag",
        default="latest",
        help="Frontend Docker image tag (default: latest)"
    )
    parser.add_argument(
        "--output-root",
        default="repos/fba-bench-enterprise/deploy/tenants",
        help="Output root for .env files (default: repos/fba-bench-enterprise/deploy/tenants)"
    )
    parser.add_argument(
        "--tfvars-out",
        default="repos/fba-bench-enterprise/infrastructure/terraform/env",
        help="Output directory for .tfvars files (default: repos/fba-bench-enterprise/infrastructure/terraform/env)"
    )
    parser.add_argument(
        "--no-tfvars",
        action="store_true",
        help="Skip generation of .tfvars file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files"
    )

    args = parser.parse_args()

    # Paths
    templates_dir = Path("repos/fba-bench-enterprise/infrastructure/config/templates")
    backend_tpl = templates_dir / "backend.env.tpl"
    tfvars_tpl = templates_dir / "tenant.tfvars.tpl"

    output_root = Path(args.output_root)
    tfvars_out = Path(args.tfvars_out)

    tenant_dir = output_root / args.tenant_id / "backend"
    env_file = tenant_dir / ".env"
    tfvars_file = tfvars_out / f"{args.tenant_id}.tfvars"

    # Common substitutions
    subs: Dict[str, str] = {
        "tenant": args.tenant_id,
        "domain": args.domain,
        "public_app_base_url": args.public_app_base_url,
        "environment": args.environment,
        "api_image_tag": args.api_image_tag,
        "frontend_image_tag": args.frontend_image_tag,
    }

    generated = []

    # Generate .env
    if not args.force and env_file.exists():
        print(f"Skipping {env_file}: file exists (use --force to overwrite)")
    else:
        ensure_dir(tenant_dir)
        env_content = render_template(backend_tpl, subs)
        with open(env_file, 'w') as f:
            f.write(env_content)
        generated.append(str(env_file))
        print(f"Generated: {env_file}")

    # Generate .tfvars if not skipped
    if not args.no_tfvars:
        if not args.force and tfvars_file.exists():
            print(f"Skipping {tfvars_file}: file exists (use --force to overwrite)")
        else:
            ensure_dir(tfvars_out)
            tfvars_content = render_template(tfvars_tpl, subs)
            with open(tfvars_file, 'w') as f:
                f.write(tfvars_content)
            generated.append(str(tfvars_file))
            print(f"Generated: {tfvars_file}")
    else:
        print("Skipped .tfvars generation (--no-tfvars)")

    if generated:
        print("\nSummary:")
        for path in generated:
            print(f"- {path}")
    else:
        print("No files generated.")


if __name__ == "__main__":
    main()
