# ROI Calculator Tools

This directory contains the ROI (Return on Investment) calculator for FBA-Bench Enterprise, designed for use in go-to-market (GTM) activities, sales demos, and customer case studies. The primary tool is an Excel workbook (`roi_calculator.xlsx`) with embedded formulas for automatic computation. A CSV fallback (`roi_calculator.csv`) provides static example values without formulas, suitable for quick sharing or import into other tools.

## Overview
The calculator quantifies the financial benefits of adopting FBA-Bench Enterprise by comparing baseline (pre-adoption) costs and risks to post-adoption improvements. It focuses on key areas:
- Labor savings from reduced evaluation hours.
- Tool cost reductions.
- Error cost avoidance (revenue protection).
- Direct revenue uplift from faster/better agent performance.

All calculations are on a **monthly basis** unless noted. Assumptions are placeholders; customize with customer-specific data (keep confidential; do not commit real values to the repo).

## XLSX Workbook Structure
The `roi_calculator.xlsx` file includes three sheets:

### 1. Inputs (Editable)
Operator-editable fields in column B. Update these with customer estimates:
- **Current_eval_hours_per_month**: Baseline monthly hours spent on agent evaluations (e.g., 500).
- **Hourly_cost**: Fully loaded labor cost per hour (e.g., $100 USD).
- **Current_tool_cost_per_month**: Existing tool/subscription costs (e.g., $20,000 USD).
- **Error_rate**: Current error rate in evaluations (e.g., 15% or 0.15).
- **Revenue_at_risk_per_error**: Potential revenue loss per error (e.g., $50,000 USD).
- **Expected_hours_reduction_pct**: Projected % reduction in hours (e.g., 60% or 0.6).
- **Expected_tool_cost_reduction_pct**: Projected % tool cost savings (e.g., 50% or 0.5).
- **Expected_error_reduction_pct**: Projected % error reduction (e.g., 80% or 0.8).
- **Revenue_uplift_per_month**: Additional monthly revenue from improved agents (e.g., $100,000 USD).
- **Investment_cost**: FBA-Bench setup/subscription cost (e.g., $50,000 USD annually or one-time).

**Formatting**: Currency for costs/revenue, percentages for rates (2 decimals).

### 2. Results (Computed)
Auto-calculated based on Inputs. Formulas (in Excel syntax):
- **Hours_saved** = `Current_eval_hours_per_month * Expected_hours_reduction_pct` (e.g., 500 * 0.6 = 300 hours/month).
- **Labor_savings** = `Hours_saved * Hourly_cost` (e.g., 300 * 100 = $30,000/month).
- **Tool_savings** = `Current_tool_cost_per_month * Expected_tool_cost_reduction_pct` (e.g., 20,000 * 0.5 = $10,000/month).
- **Error_cost_avoidance** = `(Current_eval_hours_per_month * Error_rate) * Revenue_at_risk_per_error * Expected_error_reduction_pct` (e.g., (500 * 0.15) * 50,000 * 0.8 = 75 * 50,000 * 0.8 = $3,000,000 annual risk avoided, or ~$250,000/month).
- **Revenue_uplift_per_month**: Direct from Inputs.
- **Total_savings** = `SUM(Labor_savings + Tool_savings + Error_cost_avoidance + Revenue_uplift_per_month)` (monthly total).
- **Investment_cost**: Direct from Inputs.
- **Net_benefit** = `Total_savings - Investment_cost` (monthly net).
- **ROI_pct** = `IF(Investment_cost=0, "", Net_benefit / Investment_cost)` (e.g., 660% if net $330k on $50k investment).
- **Payback_months** = `IF(Net_benefit<=0, "", Investment_cost / (Total_savings/12))` (e.g., 1.58 months).

**Formatting**: Currency for savings/costs (2 decimals), percentages for ROI (2 decimals), numbers for months/hours.

### 3. Sample (Prefilled Examples)
Prefilled Inputs with placeholder values (e.g., 500 hours, 60% reduction) to demonstrate usage. Results auto-update. No real customer data—use for internal demos only.

## CSV Fallback
`roi_calculator.csv` mirrors the Inputs sheet plus example computed Results (static values, no formulas). Columns:
- Inputs: As above.
- Computed: Hours_saved, Labor_savings, etc., with example numbers based on sample inputs.

Use for:
- Quick email attachments.
- Import into Google Sheets/Excel (recreate formulas manually using the XLSX as reference).
- Non-Excel environments.

**Example Row (Computed)**: Hours_saved=300 (formula recreation: see above).

## How to Recreate/Use in Spreadsheets
1. **Open XLSX**: Edit Inputs in Excel/Google Sheets. Results update live. No macros needed—pure formulas.
2. **From CSV**:
   - Import to new sheet.
   - Recreate formulas in adjacent columns (copy from XLSX or this README).
   - Example: In cell next to Hours_saved, enter `=B2*C6` (assuming row/column layout).
3. **Customization**:
   - Scale to annual: Multiply monthly Total_savings by 12.
   - Sensitivity: Add charts (e.g., vary Expected_hours_reduction_pct from 40-80%).
   - Export: Save as PDF for proposals; protect sheets if sharing.
4. **Best Practices**:
   - Use placeholders only in repo; duplicate for real customer calcs.
   - Validate inputs: Ensure percentages are decimals (0.6, not 60).
   - No external links/macros: Self-contained for security.
   - For case studies: Embed key metrics (e.g., ROI_pct, Payback_months) in template.md.

## Assumptions & Limitations
- Monthly basis; assumes steady-state post-implementation.
- Investment_cost treated as monthly equivalent (adjust if one-time).
- No discounting (NPV) or taxes included—extend Results sheet if needed.
- Placeholders: Based on typical enterprise AI eval workflows; tailor per industry.

For questions, reference the case study template or contact marketing lead.
