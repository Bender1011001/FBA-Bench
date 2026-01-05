# Tenant Provisioning Guide

This guide describes how to generate valid configuration environments for new enterprise tenants using the automated provisioning scripts.

## Overview

The tenant environment generation scripts (`generate_tenant_env.py` and its wrappers) automate the creation of:
1.  **Backend Environment File**: `.env` file containing database credentials, API keys, and service URLs.
2.  **Terraform Variables**: `.tfvars` file for infrastructure provisioning (optional).

The scripts verify correct template usage and generate files in the standardized project structure.

## Quick Start ("One-Click" Experience)

### Windows (PowerShell)

Run the PowerShell wrapper script:

```powershell
.\infrastructure\config\generate_tenant_env.ps1 --tenant-id <TENANT_ID> --domain <DOMAIN>
```

**Example:**

```powershell
.\infrastructure\config\generate_tenant_env.ps1 --tenant-id acme_corp --domain acme.com
```

### Linux / macOS

Run the Bash wrapper script:

```bash
./infrastructure/config/generate_tenant_env.sh --tenant-id <TENANT_ID> --domain <DOMAIN>
```

Make sure the script is executable (`chmod +x infrastructure/config/generate_tenant_env.sh`).

## Usage Reference

### Arguments

| Argument | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `--tenant-id` | Yes | - | Unique identifier for the tenant (e.g., `acme`). Used in DB names, file names. |
| `--domain` | Yes | - | The domain name for the tenant (e.g., `acme.com`). |
| `--environment` | No | `dev` | Target environment (`dev`, `staging`, `prod`). |
| `--public-app-base-url` | No | `http://localhost:5173` | The public URL for the frontend application. |
| `--api-image-tag` | No | `latest` | Docker image tag for the API. |
| `--frontend-image-tag` | No | `latest` | Docker image tag for the Frontend. |
| `--output-root` | No | `deploy/tenants` | Root directory for generated `.env` files. |
| `--tfvars-out` | No | `infrastructure/terraform/env` | Directory for generated `.tfvars` files. |
| `--no-tfvars` | No | `false` | If set, skips generation of the `.tfvars` file. |
| `--force` | No | `false` | Overwrites existing files if they already exist. |

### Output Files

By default, the script generates:

1.  **Backend Config**: `deploy/tenants/<TENANT_ID>/backend/.env`
2.  **Infrastructure Config**: `infrastructure/terraform/env/<TENANT_ID>.tfvars`

## Templates

The generation uses templates located in `infrastructure/config/templates`:
-   `backend.env.tpl`
-   `tenant.tfvars.tpl`

These templates use standard `${VARIABLE}` substitution. Use `CHANGE_ME` placeholders for secrets that must be manually rotated after generation.
