---
description: How to update context files after making changes
---

# Update Context Files

After editing files in any directory, update the relevant context documentation:

## Steps

1. **Identify affected directories**: Note which directories contain the files you modified.

2. **Update subdirectory CONTEXT.md**: If the directory has a `CONTEXT.md` file, update it:
   - Update the "Last Updated" date
   - Add/remove/modify entries in the "Key Files" table
   - Update "Dependencies" if imports changed
   - Update "Architecture Notes" if patterns changed

3. **Update root context if needed**: If you made significant structural changes, update `.agent/context.md`:
   - New directories → add to "Key Directories" table
   - New patterns → add to "Architecture Patterns"
   - New conventions → add to "Important Conventions"

4. **Create CONTEXT.md if missing**: For new directories or directories without context:
   - Copy `.agent/context_template.md` to `DIRECTORY/CONTEXT.md`
   - Fill in all sections

## Example Update

If you edited `src/services/leaderboard_service.py`:

```markdown
# In src/services/CONTEXT.md

## Key Files
| File | Description |
|------|-------------|
| `leaderboard_service.py` | Rankings, score aggregation, public API data - **UPDATED: added caching** |
```
