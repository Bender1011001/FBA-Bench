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

- `config/`:
  - [`generate_tenant_env.sh`](config/generate_tenant_env.sh): Unified generator for tenant configs and portable demo packages.
  - [`generate_tenant_env.py`](config/generate_tenant_env.py): Core Python logic for template rendering and file generation.
  - `templates/`: J2/Template files for `.env`, `.tfvars`, and Docker Compose.

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

### Using the Unified Generator

Run from repository root. The script handles environment variable generation and optional portable demo packaging.

#### Generate Standard Tenant Config (Bash/WSL)
```bash
./infrastructure/config/generate_tenant_env.sh --tenant-id demo --domain demo.local
```

#### Generate Standard Tenant Config (Windows/Direct)
```powershell
python infrastructure/config/generate_tenant_env.py --tenant-id demo --domain demo.local
```

#### Generate Portable Demo Package
```bash
./infrastructure/config/generate_tenant_env.sh --tenant-id demo --domain demo.local --demo
```
This outputs a self-contained Docker package to `deploy/tenants/demo/backend/`.

## Safety Notes

- **Non-Destructive**: Only local/random/null resources—no external API calls, cloud provisioning, or file writes.
- **No Secrets**: Placeholders only in example files/docs. Real secrets must be injected securely (e.g., Terraform variables from env, not committed).
- **Credential-Less**: Plans succeed without AWS/GCP/Azure auth—ideal for local dev/CI validation.
- **Blast Radius**: Minimal; extends safely to cloud in future phases. Review plan before any `apply`.
- **gitignore**: Excludes `.terraform/`, `*.tfstate`, `plan.out`, `*.tfvars` to prevent accidental commits.

For next phases (e.g., cloud providers, per-tenant generation), see project roadmap.

## Per-tenant Config Generation

This section covers generating tenant-specific configuration files (`.env` and `terraform.tfvars`) from templates using the unified generator. These files are output to `deploy/tenants/<tenant_slug>/` (.env) and `infrastructure/terraform/env/` (.tfvars) and are git-ignored to prevent committing sensitive data.

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

#### Unified Command
```bash
./infrastructure/config/generate_tenant_env.sh \
    --tenant-id demo \
    --domain demo.example.com \
    --environment sandbox \
    --api-image-tag latest \
    --frontend-image-tag latest
```

- `deploy/tenants/demo/backend/.env`
- `infrastructure/terraform/env/demo.tfvars`

- Do not commit generated files; `deploy/tenants/` and `infrastructure/terraform/env/*.tfvars` are git-ignored.
- Secrets must be provided via environment variables or secure vaults in production; values here are placeholders only.
- Generation is idempotent: skips existing files unless `--force` is used.
- Verify generated `.tfvars` with `terraform plan -var-file=env/demo.tfvars` in the `infrastructure/terraform/` directory.

### Provisioning Steps
1. **Generate Environment**: Use `./infrastructure/config/generate_tenant_env.sh` (see above).
2. **Review/Edit**: Customize `deploy/tenants/<tenant>/backend/.env` or `infrastructure/terraform/env/<tenant>.tfvars`.
3. **Plan Infrastructure**:
   ```bash
   cd infrastructure/terraform
   terraform plan -var-file=env/<tenant>.tfvars
   ```

### What it Does
- Generates tenant configs under `deploy/tenants/<tenant>/` and `infrastructure/terraform/env/`.
- Prepares logic for portable Docker packages (if `--demo` is used).
- Supports dry-run validation via subsequent Terraform commands.

### Safety Notes
- No real cloud providers are configured; only local/null/random resources.
- No apply in scripts; to apply manually, refer to Terraform docs (not recommended for this skeleton).

### Troubleshooting
- PATH issues for terraform/python
- Use --force/-Force to regenerate tenant files
