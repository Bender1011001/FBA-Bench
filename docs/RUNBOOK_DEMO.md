# Sales Demo Runbook — FBA Bench Enterprise

## Audience and Purpose
This runbook is for Sales teams, Systems Engineers (SEs), and Founders conducting live demos. Typical duration: 15–25 minutes. Outcomes: Qualify prospects, showcase authentication, billing integration, and sandbox provisioning capabilities.

## Demo Architecture at a Glance
- **Backend API**: FastAPI with JWT authentication for secure endpoints.
- **Frontend**: Web application with client-side auth handling.
- **Billing**: Stripe integration for checkout sessions, customer portals, and webhook processing.
- **Infrastructure**: Terraform-based provisioning skeleton for managed sandboxes.
- **Tenant Configs**: Automated generator for multi-tenant setups.

Link references:
- Auth endpoints: [api/routers/auth.py](repos/fba-bench-enterprise/api/routers/auth.py)
- Billing endpoints: [api/routers/billing.py](repos/fba-bench-enterprise/api/routers/billing.py)
- Frontend client: [frontend/src/api/authClient.ts](repos/fba-bench-enterprise/frontend/src/api/authClient.ts)
- Billing page: [web/src/components/BillingPage.tsx](repos/fba-bench-enterprise/web/src/components/BillingPage.tsx)
- Terraform skeleton: [infrastructure/terraform/providers.tf](repos/fba-bench-enterprise/infrastructure/terraform/providers.tf)
- Tenant generator: [infrastructure/scripts/generate_tenant_configs.py](repos/fba-bench-enterprise/infrastructure/scripts/generate_tenant_configs.py)
- Demo provision wrappers: [infrastructure/scripts/provision_demo_tenant.sh](repos/fba-bench-enterprise/infrastructure/scripts/provision_demo_tenant.sh), [infrastructure/scripts/provision_demo_tenant.ps1](repos/fba-bench-enterprise/infrastructure/scripts/provision_demo_tenant.ps1)

## Prerequisites and Environment Setup
- **Tools**: Python 3.10+, Node 18+, Terraform ≥1.4, Stripe CLI (optional).
- **Env vars** (placeholders only; do not commit real keys):
  - JWT_SECRET=CHANGE_ME_DEV
  - DATABASE_URL=sqlite:///./enterprise.db
  - STRIPE_SECRET_KEY=sk_test_CHANGE_ME (optional; required for live Checkout demo)
  - STRIPE_WEBHOOK_SECRET=whsec_CHANGE_ME (optional; for webhook simulation)
  - FRONTEND_BASE_URL=http://localhost:5173
- Copy .env examples:
  - Backend: [/.env.example](repos/fba-bench-enterprise/.env.example)
  - Web: [web/.env.example](repos/fba-bench-enterprise/web/.env.example)

## One-Command Sandbox Dry-Run (No Apply)
- **Bash**: `./infrastructure/scripts/provision_demo_tenant.sh --tenant=demo`
- **PowerShell**: `./infrastructure/scripts/provision_demo_tenant.ps1 -Tenant demo`
- **Resulting files**:
  - Tenant .env, tfvars under [infrastructure/tenants/demo/](repos/fba-bench-enterprise/infrastructure/tenants/.gitkeep)
  - Terraform plan in [infrastructure/terraform/](repos/fba-bench-enterprise/infrastructure/terraform/providers.tf)

## Timeboxed Talk Track (18–20 Minutes Total)
- **0–2m: Framing** — Problem and outcomes: "FBA Bench Enterprise solves secure, scalable AI benchmarking for teams. Today, we'll demo auth, billing, and sandbox setup to show how it qualifies leads and drives revenue."
- **2–6m: Auth Flow** — Register → Login → View profile (/auth/me): "Seamless onboarding with JWT security. Watch as we register a user, log in, and fetch profile data."
  - Frontend actions: Show Login UI, Register UI, Account page.
- **6–11m: Billing (Two Paths)**:
  - With test Stripe keys: "Click 'Subscribe' to create Checkout Session (URL returned), optionally open; 'Manage Billing' shows portal if a customer exists."
  - Without keys: "Show graceful 'Billing unavailable' messages; explain env-gating and secure defaults for production."
- **11–15m: Managed Sandbox** — Walk through dry-run infra plan (local/null/random only): "Provision isolated environments via Terraform—dry-run generates configs without deployment."
- **15–18m: Q&A and Next Steps** — "Questions? Let's discuss POC, sandbox access, and security compliance."

Timing cues: Presenter signals transitions (e.g., "Next, billing..."); SE drives UI; monitor clock for 20m cap.

## Step-by-Step Demo Flow
1. **Start Backend**: Assumed running (e.g., `uvicorn api.server:app --reload`); verify at http://localhost:8000/docs.
2. **Start Web Dev Server**: From web/: `npm i && npm run dev` (loads at http://localhost:5173).
3. **Register Test User → Login → Show Account**: Use UI forms; confirm profile loads via /auth/me.
4. **(Optional) Set Stripe Test Vars → Subscribe (Checkout) → Portal (if Customer Exists)**: Trigger endpoints; show session URLs.
5. **(Optional) Webhook Simulation**: Use Stripe CLI if configured (see below).
6. **Run Sandbox Dry-Run Script**: Execute provision command; show generated tfvars and plan file.

## Optional: Webhook Simulation (Only if STRIPE_WEBHOOK_SECRET Configured)
- Install Stripe CLI: Download from Stripe docs.
- Forward events: `stripe listen --forward-to localhost:8000/billing/webhook` (use whsec placeholders; set locally only).
- Trigger test event: `stripe trigger checkout.session.completed`.
- Emphasize: No secrets in repo; configure .env locally for simulation; verify DB updates (e.g., subscription status).

## Troubleshooting (Quick Reference)
- **401 Unauthorized** → Ensure JWT_SECRET consistent; login token fresh (clear localStorage if stale).
- **503 Billing Unavailable** → Set STRIPE_SECRET_KEY or demo the disabled path (env-gated fallback).
- **Terraform Missing** → Install Terraform; confirm on PATH (`terraform version`).
- **CORS/Local URLs** → Ensure FRONTEND_BASE_URL and API URLs match env (e.g., no port mismatches).
- **Onboarding Overlay Persistence** → Clear localStorage `fbaee_onboarding_dismissed`.

Roles: Primary (Presenter) narrates; Secondary (Driver/SE) executes steps; inline cues like "Driver: Click Subscribe."

## Appendix (Commands)
- Backend: `uvicorn api.server:app --reload`; `alembic upgrade head`.
- Web: `cd web && npm run dev`; `npm test`.
- Tests: `pytest`; `cd web && npm test`.
- Sandbox: See dry-run above; full plan: `cd infrastructure/terraform && terraform plan -var-file=../tenants/demo/terraform.tfvars`.
- Links to CI: [/.github/workflows/ci.yml](repos/fba-bench-enterprise/.github/workflows/ci.yml)
