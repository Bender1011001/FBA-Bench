# Getting Started: SaaS Onboarding Guide

Welcome to FBA-Bench SaaS. You have just taken the first step toward guaranteeing the economic safety and resilience of your autonomous agents.

## Your Toolkit

As a SaaS customer, you have access to three primary tools:
1. **The Remote Simulation Engine:** Run 365-day tests without burning your own local compute.
2. **The CI/CD Webhooks:** Trigger automated evaluations on GitHub/GitLab Pull Requests.
3. **The Godot Replay Theater:** Download `.fba_record` files to visually watch your agent's decision-making process.

## Step 1: Set Up Your Agent Wrapper

To plug into our simulation, your agent needs to be able to accept "Ticks" (daily state updates from the market) and respond with "Action Lists" (e.g., change price, buy inventory, allocate ad spend).

Review our `Runners Catalog` in `docs/agent_runners.md`. If you are using CrewAI or LangChain, simply import our provided adapter. If you are using a custom framework, set up a simple `/tick` web server that parses our Pydantic schemas.

## Step 2: Run a Baseline Test

Before integrating completely, trigger a manual test against the `"baseline_Q4"` scenario to get a sense of your agent's current profit margin capability.

```bash
curl -X POST https://api.fbabench.com/v1/runs \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"agent_endpoint": "http://your-ip:port/tick", "scenario": "baseline_Q4"}'
```

Watch the dashboard at `fbabench.com/dashboard` to see the live telemetry.

## Step 3: Integrate with CI/CD

The real power of FBA-Bench SaaS is preventing bad agent logic from entering production. See the [CI/CD Integration Guide](../deployment/ci_cd_integration.md) to set up GitHub Actions.

## Step 4: Red Team Analysis

Once your agent can consistently turn a profit in baseline scenarios, open your Dashboard and enable the **Red Team Gauntlet**. This will inject phishing attempts, sudden supplier price hikes, and competitor listing hijacks into the simulation. 

We highly recommend reviewing the Godot Replay files for any run where your agent failed a Red Team event, as these often highlight fundamental flaws in the agent's core instruction set or tool execution constraints.
