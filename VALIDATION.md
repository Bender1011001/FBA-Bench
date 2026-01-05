# FBA-Bench Enterprise Validation Guide

## Core Functionality Validation

- [ ] API server starts without errors (`uvicorn api.server:app --reload`)
- [ ] Database migrations apply successfully (`alembic upgrade head`)
- [ ] Auth endpoints respond correctly:
  - POST /auth/register: Creates user, returns 201
  - POST /auth/login: Returns JWT token on valid creds, 401 on invalid
  - GET /auth/me: Returns user profile with auth header, 401 without
- [ ] Billing endpoints respond correctly (test mode):
  - POST /billing/checkout-session: Returns Stripe session URL
  - POST /billing/portal-session: Returns Stripe portal URL
- [ ] Web UI loads and navigates: Login/Register/Account/Billing pages render
- [ ] Frontend auth client integrates: Token storage/retrieval works
- [ ] Onboarding overlay appears on first load, dismisses and persists flag
- [ ] Help modal triggers from buttons, shows context-specific content

## Infrastructure Validation

- [ ] Provisioning scripts generate configs: `generate_tenant_configs.sh/ps1/py`
- [ ] Terraform plan (dry-run) outputs expected resources (no apply)
- [ ] Templates render correctly: .env.template, terraform.tfvars.template

## Integration Validation

- [ ] Stripe webhooks mock/test: Subscription events update DB
- [ ] CORS configured: Frontend calls to backend succeed
- [ ] Error handling: 4xx/5xx responses include helpful messages
- [ ] Performance: Local demo loads <2s, no console errors

## Golden Master Validation

- [ ] Enterprise V1.0 Baseline exists: `artifacts/enterprise_v1.0_baseline.parquet` is present
- [ ] Verification script runs: `python scripts/verify_golden_masters.py` completes without errors
- [ ] Tier 2 golden master test passes: `pytest tests/integration/test_tier2_golden_master.py -v`
- [ ] Event snapshot is reproducible: Running the same test twice produces identical Parquet files

## Sales Demo — Validation Checklist

- [ ] Backend .env prepared (no real secrets in repo)
- [ ] Web dev server runs; Login/Register/Account working
- [ ] (Optional) Stripe test keys set; Checkout returns session URL
- [ ] (Optional) Portal session returns URL when customer exists
- [ ] Sandbox dry-run script completes (init/validate/plan) with plan file created
- [ ] Troubleshooting notes rehearsed (401, 503, PATH, CORS, onboarding)
- [ ] Timing practiced to ≤20 minutes
- [ ] Demo tenant configs generated under infrastructure/tenants/<tenant>/

### Screenshots Placeholders
- ./docs/images/demo-login.png
- ./docs/images/demo-plan.png

## UX Polish — Onboarding and Help

Use this checklist to validate the onboarding overlay and contextual help modal.

### Validation Checklist

- [ ] First visit: Onboarding overlay is visible on initial load (localStorage key 'fbaee_onboarding_dismissed' not set)
- [ ] Dismissal: Clicking "Get started", "Dismiss", or close button sets localStorage 'fbaee_onboarding_dismissed=true' and closes overlay
- [ ] Persistence: After dismissal, refresh/reload does not show overlay again
- [ ] Help button: Floating help button (?) is visible and positioned bottom-right on all views (Login, Register, Account)
- [ ] Help modal opens: Clicking help button opens modal with "How to Get Started" steps and context-specific content
- [ ] Help modal closes: Modal closes via close button (×), "Close" button, or Escape key
- [ ] Accessibility: Overlay and modal have role="dialog", aria-modal="true", proper aria-labels on buttons, focus trap works (Tab/Shift+Tab cycles focus)
- [ ] Styling: Focus-visible outlines on buttons, adequate contrast for help button and modal controls

### Screenshot Placeholders

[Screenshot: ./docs/images/onboarding-1.png] — First-run onboarding overlay

[Screenshot: ./docs/images/help-modal-1.png] — Help modal open on login view

### Troubleshooting Notes

- To re-show onboarding: Clear localStorage with `localStorage.removeItem('fbaee_onboarding_dismissed')` in browser console, then refresh
- If help button not visible: Check z-index conflicts or CSS positioning; ensure App.tsx renders HelpButton globally
- Modal not trapping focus: Verify focusable elements are correctly queried; test with keyboard navigation
- Tests failing: Run `cd web && npm test` to check component isolation; ensure no real network calls in tests
- Accessibility issues: Use browser dev tools to inspect ARIA attributes; test with screen reader if available