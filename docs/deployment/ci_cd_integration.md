# FBA-Bench CI/CD Integration Guide

This guide explains how to hook your agent's GitHub or GitLab repository into the FBA-Bench SaaS platform to run automated, long-horizon economic simulations on every Pull Request.

## Why CI/CD for Agents?

Standard unit tests verify that your agent's code compiles and its API keys work. FBA-Bench verifies that your agent's *economic reasoning* hasn't regressed. 
If an engineer tweaks a system prompt or adds a new RAG tool, you need to know if that change causes the agent to overspend on inventory or fall for phishing traps. 

## Integration Steps

### 1. Obtain Your FBA-Bench API Key
After subscribing to the SaaS Starter or Enterprise tier, you will receive an `FBA_BENCH_API_KEY` in your dashboard. Store this securely in your repository secrets (e.g., GitHub Secrets).

### 2. Configure Your Agent Runner
Ensure your agent is accessible via a standardized runner script or Docker container that accepts environment variables for the benchmark scenario. We provide adapters for CrewAI, LangChain, and custom REST APIs.

### 3. Add the GitHub Actions Workflow

Create `.github/workflows/fba-bench-eval.yml` in your repository:

```yaml
name: FBA-Bench Regression Eval

on:
  pull_request:
    branches: [ "main" ]

jobs:
  agent-eval:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Build Agent Container
        run: docker build -t my-agent-runner .

      - name: Trigger FBA-Bench Simulation
        uses: fba-bench/action-eval@v1
        with:
          api_key: ${{ secrets.FBA_BENCH_API_KEY }}
          agent_image: my-agent-runner
          scenario: "supply_chain_shock_v2"
          ticks: 30 # Run a 30-day simulation
          fail_on_bankruptcy: true

      - name: Post Results to PR
        uses: fba-bench/action-pr-comment@v1
        with:
           github_token: ${{ secrets.GITHUB_TOKEN }}
```

## Reviewing Results
Once the workflow completes, FBA-Bench will automatically comment on your PR with:
1. **Net Profit / ROI** over the simulated 30 days.
2. **Red Team Score:** Did it survive adversarial injection?
3. **Link to Godot Replay:** A cinematic playback showing exactly how your agent managed the supply chain and pricing during the test.

If `fail_on_bankruptcy` is set to `true`, the pipeline will fail if the agent's cash balance hits $0, preventing you from merging fundamentally flawed logic into production.
