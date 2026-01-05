# Infrastructure for FBA-Bench Enterprise - Managed Sandbox IaC Skeleton (Phase 2 Step 12)

This directory contains a minimal Terraform skeleton for planning managed sandboxes in the FBA-Bench Enterprise edition. The configuration uses only local, null, and random providers to ensure `terraform validate` and `plan` succeed without any cloud credentials or external dependencies. No resources are provisioned—this is a safe, credential-less setup for validating configuration and structure before future cloud integrations.

## Overview

The skeleton enables dry-run planning for sandbox environments, generating computed identifiers (e.g., tenant suffixes) and echoing key configurations. It includes placeholders for domain, image tags, and API keys. Scripts perform `init`, `validate`, and `plan` only—no `apply` is executed.

**Safety**: This configuration is non-destructive and does not provision external resources. Extend in future steps for cloud targets (e.g., AWS, GCP).

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) installed (version >= 1.4).
- No cloud credentials or accounts required—plans run entirely locally.
- Bash (macOS/Linux) or PowerShell (Windows) for scripts.
- Git for version control (`.gitignore` excludes state files and sensitive vars).

## Files Overview

- `terraform/`:
  - [`providers.tf`](terraform/providers.tf): Configures local/random/null providers (no cloud providers).
  - [`variables.tf`](terraform/variables.tf): Input variables with defaults and placeholders.
  - [`main.tf`](terraform/main.tf): Minimal resources (`random_id` for tenant suffix, `null_resource` for plan-time summary).
  - [`outputs.tf`](terraform/outputs.tf): Non-sensitive summary output (excludes secrets like `jwt_secret`).
  - [`terraform.tfvars.example`](terraform/terraform.tfvars.example): Template for variable values—copy to `tenant.tfvars` and customize.
- `scripts/`:
  - [`deploy_sandbox.sh`](scripts/deploy_sandbox.sh): Bash script for init/validate/plan (run from repo root).
  - [`deploy_sandbox.ps1`](scripts/deploy_sandbox.ps1): PowerShell equivalent.

## Variables Reference

All variables are defined in [`variables.tf`](terraform/variables.tf). Use `terraform.tfvars.example` as a starting point.

| Variable | Type | Default | Sensitive | Description |
|----------|------|---------|-----------|-------------|
| `domain_name` | string | "example.com" | No | Domain for the sandbox (e.g., "acme-corp.com"). |
| `environment` | string | "sandbox" | No | Deployment environment (e.g., "sandbox", "dev"). |
| `api_image_tag` | string | "latest" | No | Docker tag for API service (e.g., "v1.2.3"). |
| `web_image_tag` | string | "latest" | No | Docker tag for web frontend (e.g., "v1.0.0"). |
| `api_public_base_url` | string | "http://localhost:8000" | No | Base URL for API (update for production). |
| `frontend_base_url` | string | "http://localhost:5173" | No | Base URL for frontend (update for production). |
| `stripe_public_key` | string | "pk_test_CHANGE_ME" | No | Stripe public key (pk_test_... from dashboard; placeholder only). |
| `stripe_price_id_default` | string | "price_123CHANGE_ME" | No | Default Stripe price ID (price_...; placeholder only). |
| `jwt_secret` | string | "CHANGE_ME_DEV" | Yes | JWT signing secret (generate secure random string; never commit real values). |

- **Placeholders**: Replace `CHANGE_ME` values with real data. Sensitive vars like `jwt_secret` are marked `sensitive=true` and excluded from outputs/plans.
- **Customization**: Copy [`terraform.tfvars.example`](terraform/terraform.tfvars.example) to `tenant.tfvars` in the `terraform/` directory and edit. Do not commit real secrets—use env vars or vaults for production.

## How to Use

### Manual Commands

Run from the repository root (`c:/Users/admin/Downloads/fba` or equivalent).

1. Navigate to Terraform directory:
   ```bash
   cd repos/fba-bench-enterprise/infrastructure/terraform
   ```

2. Copy and customize vars:
   ```bash
   cp terraform.tfvars.example tenant.tfvars
   # Edit tenant.tfvars (e.g., set domain_name = "your-domain.com")
   ```

3. Initialize, validate, and plan:
   ```bash
   terraform init
   terraform validate
   terraform plan -var-file=tenant.tfvars
   ```

Expected: A plan showing 2 resources to add (`random_id.tenant_suffix`, `null_resource.sandbox_summary`) with no changes/destroys. Outputs preview the sandbox summary.

### Using Scripts (Recommended)

Run from repository root. Scripts handle directory changes, var file setup, and output instructions.

#### macOS/Linux (Bash)
```bash
bash repos/fba-bench-enterprise/infrastructure/scripts/deploy_sandbox.sh [tenant.tfvars]
# Example: bash .../deploy_sandbox.sh tenant.tfvars
# Defaults to tenant.tfvars if omitted; creates from example if missing.
```

#### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File repos/fba-bench-enterprise/infrastructure/scripts/deploy_sandbox.ps1 -VarFile tenant.tfvars
# Defaults to tenant.tfvars if omitted; creates from example if missing.
```

Scripts output:
- Init: Downloads providers (random, null, local).
- Validate: Confirms syntax.
- Plan: Generates `plan.out` with compact warnings.
- Instructions: How to show/apply (apply not executed).

## Safety Notes

- **Non-Destructive**: Only local/random/null resources—no external API calls, cloud provisioning, or file writes.
- **No Secrets**: Placeholders only in example files/docs. Real secrets must be injected securely (e.g., Terraform variables from env, not committed).
- **Credential-Less**: Plans succeed without AWS/GCP/Azure auth—ideal for local dev/CI validation.
- **Blast Radius**: Minimal; extends safely to cloud in future phases. Review plan before any `apply`.
- **gitignore**: Excludes `.terraform/`, `*.tfstate`, `plan.out`, `*.tfvars` to prevent accidental commits.

For next phases (e.g., cloud providers, per-tenant generation), see project roadmap.

## Per-tenant Config Generation

This section covers generating tenant-specific configuration files (.env and terraform.tfvars) from templates using the provided scripts. These files are output to `infrastructure/tenants/<tenant_slug>/` and are git-ignored to prevent committing sensitive data.

### Variables Explanation and Defaults

The generation script substitutes the following variables with defaults (overridable via CLI flags):

- **DOMAIN_NAME**: Domain for the tenant (default: `example.com`)
- **ENVIRONMENT**: Deployment environment (default: `sandbox`)
- **API_IMAGE_TAG**: Docker tag for API (default: `latest`)
- **WEB_IMAGE_TAG**: Docker tag for web (default: `latest`)
- **API_PUBLIC_BASE_URL**: Public API URL (default: `http://localhost:8000`)
- **FRONTEND_BASE_URL**: Frontend base URL (default: `http://localhost:5173`)
- **STRIPE_PUBLIC_KEY**: Stripe public key (default: `pk_test_CHANGE_ME`)
- **STRIPE_PRICE_ID_DEFAULT**: Default Stripe price ID (default: `price_123CHANGE_ME`)
- **JWT_SECRET**: JWT signing secret (default: `CHANGE_ME_DEV`; generate a secure random string for production)
- **STRIPE_SECRET_KEY**: Stripe secret key (optional; default: empty string)
- **STRIPE_WEBHOOK_SECRET**: Stripe webhook secret (optional; default: empty string)
- **DATABASE_URL**: Database connection (fixed: `sqlite:///./enterprise.db` for local dev)

Templates use `${VAR}` placeholders. Unknown placeholders remain unsubstituted to signal configuration gaps. Secrets use placeholders—replace with real values securely; never commit them.

### Example Usage

Run from the repository root.

#### Bash
```bash
./infrastructure/scripts/generate_tenant_configs.sh demo --domain=demo.example.com --api-url=http://localhost:8000 --web-url=http://localhost:5173 --stripe-public-key=pk_test_CHANGE_ME --price-id=price_123CHANGE_ME --jwt-secret=CHANGE_ME_DEV
```

#### PowerShell
```powershell
./infrastructure/scripts/generate_tenant_configs.ps1 -Tenant demo -Domain demo.example.com -ApiUrl http://localhost:8000 -WebUrl http://localhost:5173 -StripePublicKey pk_test_CHANGE_ME -PriceId price_123CHANGE_ME -JwtSecret CHANGE_ME_DEV
```

#### Python Direct
```bash
python infrastructure/scripts/generate_tenant_configs.py --tenant demo --domain demo.example.com --api-url http://localhost:8000 --web-url http://localhost:5173 --stripe-public-key pk_test_CHANGE_ME --price-id price_123CHANGE_ME --jwt-secret CHANGE_ME_DEV
```

### Outputs
- `infrastructure/tenants/demo/.env`
- `infrastructure/tenants/demo/terraform.tfvars`

### Safety Notes
- Do not commit generated files; `tenants/` is git-ignored (with `.gitkeep` to preserve the directory).
- Secrets must be provided via environment variables or secure vaults in production; values here are placeholders only.
- Generation is idempotent: skips existing files unless `--force` is used.
- Verify generated `terraform.tfvars` with `terraform plan -var-file=../tenants/demo/terraform.tfvars` in the `infrastructure/terraform/` directory.

## Demo Provisioning Playbook (Dry-run)

### Overview
One-command demo dry-run that generates tenant config and runs a no-op Terraform plan using the local/null/random providers.

### Prerequisites
- Terraform >= 1.4, on PATH.
- Python 3.9+, on PATH.

### Bash Usage Examples
```bash
./scripts/provision_demo_tenant.sh
```
```bash
./scripts/provision_demo_tenant.sh --tenant=demo-na --domain=demo.na.example.com --api-url=http://localhost:8000 --web-url=http://localhost:5173 --stripe-public-key=pk_test_CHANGE_ME --price-id=price_123CHANGE_ME --jwt-secret=CHANGE_ME_DEV --force
```

### PowerShell Usage Examples
```powershell
./scripts/provision_demo_tenant.ps1
```
```powershell
./scripts/provision_demo_tenant.ps1 -Tenant demo-eu -Domain demo.eu.example.com -ApiUrl http://localhost:8000 -WebUrl http://localhost:5173 -StripePublicKey pk_test_CHANGE_ME -PriceId price_123CHANGE_ME -JwtSecret CHANGE_ME_DEV -Force
```

### What it Does
- Generates tenant configs under [`infrastructure/tenants/<tenant>/`](repos/fba-bench-enterprise/infrastructure/tenants/.gitkeep)
- Executes Terraform init/validate/plan using [`infrastructure/terraform/`](repos/fba-bench-enterprise/infrastructure/terraform/providers.tf)
- Produces plan-<tenant>.out (not applied)

### Safety Notes
- No real cloud providers are configured; only local/null/random resources.
- No apply in scripts; to apply manually, refer to Terraform docs (not recommended for this skeleton).

### Troubleshooting
- PATH issues for terraform/python
- Use --force/-Force to regenerate tenant files
