# FBA-Bench Enterprise Marketing Workflow

This directory supports go-to-market (GTM) activities for enterprise ICPs in SaaS, FinTech, Healthcare, Manufacturing, Retail, Media, and GovTech. Focus on compliant, personalized outbound outreach using ICP targets and email templates to generate leads.

Key assets:
- [ICP Target List](targets/top20_icp.csv): 20 anonymized sample entries.
- [Email Sequence Templates](templates/email_sequence.md): 5-step multi-touch framework.
- [Case Studies](case-studies/template.md): Reusable success story template.
- [ROI Calculator](tools/roi_calculator.csv): Sample data for value quantification; see [tools/README.md](tools/README.md).

## New Reports & Campaigns 🚀
- **[Q1 2026 Benchmark Report](reports/2026_q1_benchmark.md)**: Analysis of Top Models (Grok, Claude, GPT-5).
- **["Loss Porn" Stress Test](campaigns/loss_porn_teaser.md)**: Concept for the next-gen "Chaos" benchmark.

## 1) ICP Targets

The [ICP Target List](targets/top20_icp.csv) provides 20 representative, anonymized entries across industries (SaaS, FinTech, etc.), regions (NA, EU, APAC), headcount (50-200, 200-1k, 1k-5k, 5k+), and tech stacks (e.g., Python/FastAPI, React/Stripe).

### CSV Schema

| Column          | Description                                                                 | Example Value                  | Data Type |
|-----------------|-----------------------------------------------------------------------------|-------------------------------|-----------|
| company        | Fictitious company name                                                     | Acme Analytics                | String   |
| industry       | Sector (SaaS, FinTech, Healthcare, etc.)                                    | SaaS                          | String   |
| headcount      | Employee count bucket                                                       | 150                           | Integer  |
| region         | Geographic focus (NA, EU, APAC)                                             | NA                            | String   |
| tech_stack     | Key technologies (comma-separated)                                          | Python FastAPI React Postgres | String   |
| key_pain_points| Primary challenges (e.g., evaluation inconsistencies)                       | Inconsistent AI model evaluations across teams | String   |
| champion_role  | Likely decision-maker role                                                  | CTO                           | String   |
| budget_range   | Estimated annual spend (USD)                                                | $50k-$100k                    | String   |
| priority_tier  | Prioritization (A: High fit/immediate, B: Medium, C: Long-term)             | A                             | String   |
| status         | Outreach stage (uncontacted, contacted, replied, meeting, won, lost)        | uncontacted                   | String   |
| notes          | Additional context (e.g., recent funding, events)                           | Enterprise SaaS leader seeking standardization | String   |
| contact_name   | Placeholder name (e.g., First Last or TBD)                                  | John Doe                      | String   |
| contact_title  | Job title                                                                   | CTO                           | String   |
| contact_email  | Placeholder email (e.g., firstname.lastname@example.com)                    | john.doe@acmeanalytics.example| String   |
| outreach_tier  | Sequence length (short: 2-3 emails, standard: 5, executive: customized)     | standard                      | String   |

Encoding: UTF-8, comma-separated. Use tools like Excel/Google Sheets for viewing; ensure no real PII.

### Prioritization and Status Lifecycle

- **Priority Tier Guidance:** A (top 30%: high alignment, budget >$50k, urgent pains); B (next 50%: good fit, moderate budget); C (20%: exploratory). Start outreach with A-tier; segment by industry/region for relevance.
- **Status Lifecycle:** uncontacted → contacted (Day 0 sent) → replied (response received) → meeting (demo booked) → won/lost (outcome). Update status post-interaction; archive lost after 90 days for re-engagement.

Copy to a private file for real data; research via LinkedIn/Crunchbase.

## 2) Outreach Workflow

Efficiently convert ICPs to opportunities with this structured process.

### Steps
1. **Segment:** Filter CSV by priority_tier (A first), industry/region. Limit to 20-50 accounts/week.
2. **Personalize:** Map CSV to [email templates](templates/email_sequence.md); add 1-2 custom details (e.g., "Congrats on recent Series B").
3. **Send Day 0:** Initial outreach via mail merge tool.
4. **Follow-Ups:** Automate Days 3,7,10,14 based on no-reply; adjust for outreach_tier (e.g., short skips Days 10/14).
5. **Record Outcomes:** Update status/notes in CSV/CRM on reply/bounce. Handoff replied/meeting to sales.

### Cadence and Handling
- **Daily Limits:** 50-100 emails/day from warmed domain; ramp up gradually.
- **Reply Handling:** Positive → book meeting; Negative/Questions → objection handling snippet; Opt-out → update status to "lost", remove from sequences.
- **Pause/Stop:** On reply (any), opt-out, or Day 14 completion. Re-engage lost after 3-6 months if status changes.

### A/B Testing Notes
- Test 2-3 subject line variants per batch (e.g., pain-focused vs. ROI); track open rates (>20% goal).
- CTA variants: "Book demo" vs. "See case study"; measure click-through (>5%).
- Segment tests by priority_tier/outreach_tier; iterate quarterly based on reply rates (target 10-15%).

## 3) Templates

Use the [5-step email sequence](templates/email_sequence.md) for consistent, value-first outreach.

### Mail Merge Guidance
- Tools: HubSpot, Outreach.io, or Google Workspace add-ons (e.g., Yet Another Mail Merge).
- Import CSV; map columns to merge tags (see legend in template).
- Preview 5-10 emails; test send to self/team.
- Append UTM params to {{MEETING_LINK}} (e.g., ?utm_source=email&utm_campaign=enterprise).

Reference the template's merge tags legend for full mapping (e.g., {{PAIN_POINT}} from "key_pain_points").

## 4) Compliance & Privacy

- **Placeholders Only:** Repo files use fictitious data; never commit real PII (names, emails). Store sensitive info off-repo (e.g., encrypted CRM).
- **Unsubscribe/Opt-Out:** Honor "stop" replies within 10 days; remove from all lists. Include opt-out in every email.
- **Consent Storage:** Track opt-ins off-repo (e.g., CRM fields); audit quarterly.
- **Jurisdictions:** CAN-SPAM (US: opt-out, address, honest subjects); GDPR (EU: consent/legitimate interest, data notices); CASL (Canada: implied/explicit consent). High-level only—consult legal counsel for production; no purchased lists, focus on public/ethical sourcing.

Monitor complaints (<0.1%); pause on issues.

## 5) Ops Tips

- **CRM Mapping:** HubSpot/Salesforce: company → Company Name; key_pain_points → Custom Pain Field; priority_tier → Lead Score; status → Lifecycle Stage; contact_email → Email.
- **Export/Import:** Use CSV for lightweight ops; date formats YYYY-MM-DD (e.g., for last_contact). Time zones: UTC for logs, local for scheduling (e.g., America/Los_Angeles).
- **Best Practices:** Backup CSV weekly; validate emails (tools like Hunter.io); batch updates via scripts if scaling. For >100 accounts, integrate with Zapier for auto-sync.

For ROI/case studies, see respective sections. Questions? Reference templates or marketing lead.
## CRM/Pipeline

The [CRM Pipeline Template](targets/pipeline.csv) provides a lightweight CSV for tracking enterprise opportunities from outreach to close using a standardized schema.

### Field Definitions

- **company**: Fictitious company name (e.g., TechNova).
- **industry**: Sector focus (e.g., SaaS, FinTech, Healthcare).
- **region**: Geographic area (e.g., NA, EU, APAC).
- **contact_name**: Placeholder full name (e.g., Alex Rivera).
- **contact_title**: Job role (e.g., CTO, VP Finance).
- **contact_email**: Placeholder email (e.g., alex.rivera@example.com).
- **source**: Lead origin (e.g., outbound, inbound, referral, event).
- **deal_stage**: Funnel position (prospecting, qualified, proposal, negotiation, closed_won, closed_lost).
- **status**: Overall state (open, won, lost) for quick views/filters.
- **deal_value_usd**: Estimated deal size in USD (numeric, e.g., 50000).
- **probability_pct**: Close likelihood (0–100, stage-aligned, e.g., 15 for prospecting).
- **expected_close_date**: Projected close date (YYYY-MM-DD, realistic based on stage).
- **last_contacted**: Most recent interaction date (YYYY-MM-DD).
- **next_step**: Immediate action item (short imperative, e.g., "Send proposal v2").
- **owner**: Assigned team member (placeholder name or "TBD").
- **outreach_tier**: Sequence intensity (short/standard/executive).
- **priority_tier**: Urgency ranking (A/B/C, A highest).
- **notes**: Free-text observations (concise, factual).
- **created_at**: Record creation date (YYYY-MM-DD).
- **updated_at**: Last modification date (YYYY-MM-DD).

### Stage Definitions

- **prospecting** → initial research/contact.
- **qualified** → ICP fit confirmed; problem/pain aligned.
- **proposal** → solution/pricing shared; mutual evaluation.
- **negotiation** → terms/objections; legal/procurement if any.
- **closed_won** → signed/secured.
- **closed_lost** → not moving forward (include notes).

### Workflow Guidance

- Update `last_contacted` and `next_step` after each touch.
- Keep `expected_close_date` realistic; adjust `probability_pct` by stage (e.g., 10-20% prospecting, 80-90% negotiation).
- Use `owner` field for accountability; keep `notes` concise and factual.
- Sort weekly actions by `priority_tier` (A highest).

### Compliance & Privacy Notice

- Placeholders only in-repo; store any real PII in your CRM, not in Git.
- Respect opt-outs and legal requirements (CAN-SPAM/GDPR/CASL).

### Example Filters

- Open opportunities in “proposal” or “negotiation” with `probability_pct` ≥ 50%.
- This month’s expected closes with `status`=open.