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
    
    # Determine project root and default paths relative to this script
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    
    default_output_root = project_root / "deploy" / "tenants"
    default_tfvars_out = project_root / "infrastructure" / "terraform" / "env"
    
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
        default=str(default_output_root),
        help=f"Output root for .env files (default: {default_output_root})"
    )
    parser.add_argument(
        "--tfvars-out",
        default=str(default_tfvars_out),
        help=f"Output directory for .tfvars files (default: {default_tfvars_out})"
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
    
    # Demo Package Arguments
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate a self-contained demo package (docker-compose + scripts)"
    )
    parser.add_argument(
        "--postgres-port",
        default="5432",
        help="Host port for Postgres (demo mode only)"
    )
    parser.add_argument(
        "--redis-port",
        default="6379",
        help="Host port for Redis (demo mode only)"
    )
    parser.add_argument(
        "--api-port",
        default="8000",
        help="Host port for API (demo mode only)"
    )

    args = parser.parse_args()

    # Paths
    templates_dir = script_dir / "templates"
    backend_tpl = templates_dir / "backend.env.tpl"
    tfvars_tpl = templates_dir / "tenant.tfvars.tpl"
    demo_compose_tpl = templates_dir / "demo.docker-compose.yml.tpl"

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
        # Demo subs
        "postgres_port": args.postgres_port,
        "redis_port": args.redis_port,
        "api_port": args.api_port,
        "redis_password": f"{args.tenant_id}_redis_secret", # distinct per tenant in demo
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

    # Generate Demo Package if requested
    if args.demo:
        compose_file = tenant_dir / "docker-compose.yml"
        start_script = tenant_dir / "start_demo.sh"
        start_bat = tenant_dir / "start_demo.bat"
        
        # docker-compose.yml
        if not args.force and compose_file.exists():
             print(f"Skipping {compose_file}: file exists")
        else:
            compose_content = render_template(demo_compose_tpl, subs)
            with open(compose_file, 'w') as f:
                f.write(compose_content)
            generated.append(str(compose_file))
            print(f"Generated: {compose_file}")

        # start_demo.sh
        if not args.force and start_script.exists():
            print(f"Skipping {start_script}: file exists")
        else:
            with open(start_script, 'w') as f:
                f.write("#!/bin/bash\n")
                f.write("echo 'Starting FBA-Bench Enterprise Demo...'\n")
                f.write("docker compose up -d\n")
                f.write("echo 'Services started.'\n")
                f.write(f"echo 'API: http://localhost:{args.api_port}'\n")
            
            # Make executable (Windows ignores this but harmless)
            try:
                start_script.chmod(0o755)
            except OSError:
                pass
            
            generated.append(str(start_script))
            print(f"Generated: {start_script}")

        # start_demo.bat
        if not args.force and start_bat.exists():
            print(f"Skipping {start_bat}: file exists")
        else:
            with open(start_bat, 'w') as f:
                f.write("@echo off\n")
                f.write("echo Starting FBA-Bench Enterprise Demo...\n")
                f.write("docker compose up -d\n")
                f.write("echo Services started.\n")
                f.write(f"echo API: http://localhost:{args.api_port}\n")
                f.write("pause\n")
            generated.append(str(start_bat))
            print(f"Generated: {start_bat}")

        # README.txt
        readme_file = tenant_dir / "README.txt"
        if not args.force and readme_file.exists():
            print(f"Skipping {readme_file}: file exists")
        else:
            with open(readme_file, 'w') as f:
                f.write(f"FBA-Bench Enterprise - Demo Package ({args.tenant_id})\n")
                f.write("===================================================\n\n")
                f.write("Instructions:\n")
                f.write("1. START BACKEND SERVICES\n")
                f.write("   Run 'start_demo.bat' (Windows) or './start_demo.sh' (Linux/Mac).\n")
                f.write("   This will start Postgres, Redis, and the FBA-Bench API Server in Docker.\n\n")
                f.write("2. VERIFY API\n")
                f.write(f"   Open your browser to: http://localhost:{args.api_port}/api/v1/health\n")
                f.write("   You should see 'status': 'ok'.\n\n")
                f.write("3. LAUNCH GODOT GUI\n")
                f.write("   Run the provided FBA_Bench_Client executable.\n")
                f.write(f"   It is configured to connect to http://localhost:{args.api_port} by default.\n\n")
                f.write("4. SHUT DOWN\n")
                f.write("   Run 'docker compose down' in this directory.\n")
            generated.append(str(readme_file))
            print(f"Generated: {readme_file}")

    if generated:
        print("\nSummary:")
        for path in generated:
            print(f"- {path}")
    else:
        print("No files generated.")


if __name__ == "__main__":
    main()
