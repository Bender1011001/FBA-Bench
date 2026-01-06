# Project Rules for AI Assistants

These rules apply to **all AI interactions** with this repository.

---

## Mandatory: Update Context Files

**After ANY code edit**, you MUST update the relevant context documentation:

1. **Subdirectory edits** → Update `CONTEXT.md` in that directory (create from `.agent/context_template.md` if missing)
2. **Structural changes** → Also update `.agent/context.md`
3. **New directories** → Create `CONTEXT.md` from template

Use `/update-context` workflow for detailed steps.

---

## Context File Priority

When starting a new session, read in this order:
1. `.agent/context.md` (root overview)
2. `CONTEXT.md` in any directory you're about to edit
3. Relevant `docs/` files if deeper understanding needed

---

## General Conventions

- Use **absolute imports** from `src/`
- All services go through `src/services/`
- Document public APIs with docstrings
- Run `make lint` before finalizing changes
