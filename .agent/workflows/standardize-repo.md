---
description: standardizes a project repo with AGENTS.md, README.md, and CONTEXT.md
---
// turbo-all
1. Verify AGENTS.md exists and follows the standard template (Project Context, What this is, Current goal, Repo map, How to run, Environment, Conventions, Known landmines, Decision log).
2. Create or update root CONTEXT.md with status, tech stack, key files, architecture quirks, trap diary, and anti-patterns.
3. Align README.md to brief overview and link to AGENTS.md for development instructions.
4. Update CONTRIBUTING.md to point to AGENTS.md for coding standards.
5. Create .env.example if missing.
6. Run `make ci-local` or equivalent to verify documentation doesn't break build/test expectations.
