#!/bin/bash

set -euo pipefail

# Resolve repo root: walk up from script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to repo root
cd "$REPO_ROOT"

# Default values
TENANT="${TENANT:-demo}"
DOMAIN="${DOMAIN:-demo.example.com}"
API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:5173}"
STRIPE_PUBLIC_KEY="${STRIPE_PUBLIC_KEY:-pk_test_CHANGE_ME}"
PRICE_ID="${PRICE_ID:-price_123CHANGE_ME}"
JWT_SECRET="${JWT_SECRET:-CHANGE_ME_DEV}"
API_IMAGE_TAG="${API_IMAGE_TAG:-latest}"
WEB_IMAGE_TAG="${WEB_IMAGE_TAG:-latest}"
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --tenant=*) TENANT="${1#*=}" ;;
    --domain=*) DOMAIN="${1#*=}" ;;
    --api-url=*) API_URL="${1#*=}" ;;
    --web-url=*) WEB_URL="${1#*=}" ;;
    --stripe-public-key=*) STRIPE_PUBLIC_KEY="${1#*=}" ;;
    --price-id=*) PRICE_ID="${1#*=}" ;;
    --jwt-secret=*) JWT_SECRET="${1#*=}" ;;
    --api-image-tag=*) API_IMAGE_TAG="${1#*=}" ;;
    --web-image-tag=*) WEB_IMAGE_TAG="${1#*=}" ;;
    --force) FORCE=true ;;
    *) echo "Unknown option $1"; exit 1 ;;
  esac
  shift
done

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Error: Python is required but not found in PATH."
    exit 1
fi

# Check Terraform
TERRAFORM_CMD="terraform"
if ! command -v terraform &> /dev/null; then
    # Check parent directory for terraform.exe (Windows/Git Bash common setup)
    if [ -f "$REPO_ROOT/../terraform.exe" ]; then
        TERRAFORM_CMD="$REPO_ROOT/../terraform.exe"
        echo "Found terraform at $TERRAFORM_CMD"
    else
        echo "Error: Terraform is required but not found in PATH."
        exit 1
    fi
fi

# Generate tenant configs
FORCE_ARG=""
if [ "$FORCE" = true ]; then
    FORCE_ARG="--force"
fi

echo "Generating tenant configs for '$TENANT'..."
python3 "infrastructure/scripts/generate_tenant_configs.py" \
    --tenant "$TENANT" \
    --domain "$DOMAIN" \
    --api-url "$API_URL" \
    --web-url "$WEB_URL" \
    --stripe-public-key "$STRIPE_PUBLIC_KEY" \
    --price-id "$PRICE_ID" \
    --jwt-secret "$JWT_SECRET" \
    --api-image-tag "$API_IMAGE_TAG" \
    --web-image-tag "$WEB_IMAGE_TAG" \
    $FORCE_ARG

# Run Terraform dry-run
TF_DIR="infrastructure/terraform"
cd "$TF_DIR"

echo "Initializing Terraform..."
"$TERRAFORM_CMD" init -upgrade

echo "Validating Terraform configuration..."
"$TERRAFORM_CMD" validate

echo "Running Terraform plan..."
"$TERRAFORM_CMD" plan \
    -var-file="../tenants/$TENANT/terraform.tfvars" \
    -out "plan-$TENANT.out" \
    -compact-warnings

cd "$REPO_ROOT"

# Print summary
echo ""
echo "=== Demo Provisioning Summary ==="
echo "Tenant: $TENANT"
echo "Generated config files:"
echo "  - infrastructure/tenants/$TENANT/.env"
echo "  - infrastructure/tenants/$TENANT/terraform.tfvars"
echo "Terraform plan file:"
echo "  - infrastructure/terraform/plan-$TENANT.out"
echo ""
echo "Dry-run complete. No resources were provisioned (no 'terraform apply' executed)."
echo "To review the plan: terraform show infrastructure/terraform/plan-$TENANT.out"

exit 0