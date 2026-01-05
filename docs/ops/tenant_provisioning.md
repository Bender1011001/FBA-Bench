# Tenant Provisioning Guide

This guide describes how to generate valid configuration environments for new enterprise tenants using the automated provisioning scripts.

## Overview

The tenant environment generation scripts (`generate_tenant_env.py` and its wrappers) automate the creation of:
1.  **Backend Environment File**: `.env` file containing database credentials, API keys, and service URLs.
2.  **Terraform Variables**: `.tfvars` file for infrastructure provisioning (optional).

The scripts verify correct template usage and generate files in the standardized project structure.

## Generating a Demo Package

For sales demos or POCs, you can generate a **self-contained "Demo Package"**. This includes not just the configuration, but also a `docker-compose.yml` and startup scripts to allow a client to run the entire backend locally with a single click (requiring only Docker).

### Command

Add the `--demo` flag to the generation command.

**Windows:**
```powershell
.\infrastructure\config\generate_tenant_env.ps1 --tenant-id acme --domain acme.com --demo
```

**Linux/Mac:**
```bash
./infrastructure/config/generate_tenant_env.sh --tenant-id acme --domain acme.com --demo
```

### Customizing Demo Ports
If the client is running other services, you can customize the ports exposed on their localhost:

```bash
./infrastructure/config/generate_tenant_env.sh --tenant-id acme --domain acme.com --demo --api-port 9000 --postgres-port 5433
```

### Demo Output
The demo package is generated in `deploy/tenants/<TENANT_ID>/backend/` and includes:
- `docker-compose.yml`: Self-contained service definition (Postgres + Redis + API).
- `start_demo.sh` / `start_demo.bat`: One-click startup scripts.
- `README.txt`: Instructions for the client.
- `.env`: Pre-configured environment variables.

You can simply zip this folder and send it to the client.


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
| `--demo` | No | `false` | Generates a self-contained demo package (docker-compose + scripts). |
| `--api-port` | No | `8000` | (Demo Only) Host port for the API server. |
| `--postgres-port` | No | `5432` | (Demo Only) Host port for Postgres. |
| `--redis-port` | No | `6379` | (Demo Only) Host port for Redis. |
### Output Files

By default, the script generates:

1.  **Backend Config**: `deploy/tenants/<TENANT_ID>/backend/.env`
2.  **Infrastructure Config**: `infrastructure/terraform/env/<TENANT_ID>.tfvars`

## Templates

The generation uses templates located in `infrastructure/config/templates`:
-   `backend.env.tpl`
-   `tenant.tfvars.tpl`
-   `demo.docker-compose.yml.tpl`

These templates use standard `${VARIABLE}` substitution. Use `CHANGE_ME` placeholders for secrets that must be manually rotated after generation.
