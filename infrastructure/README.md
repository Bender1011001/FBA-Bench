# Infrastructure

This folder contains infrastructure-as-code and deployment support assets.

## Terraform

If `infrastructure/terraform/` is present, it is intended for provisioning cloud resources.

Notes:
- Terraform state and provider caches (`.terraform/`) must not be committed.
- Use `terraform plan` for review and `terraform apply` only in controlled environments.

## Tenants

If tenant provisioning is used, keep generated tenant configs out of git (see `.gitignore`).

