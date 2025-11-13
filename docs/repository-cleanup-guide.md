# Repository Cleanup Guide

This guide provides step-by-step instructions for cleaning up the FBA-Bench-Enterprise repository to reduce its size and remove unnecessary files from git history.

## Overview

The FBA-Bench-Enterprise repository has grown to **144.92 MB**, significantly exceeding GitHub's recommended repository size of 100 MB. This cleanup is necessary to:

- Improve repository performance and clone times
- Comply with GitHub's size recommendations
- Remove sensitive or unnecessary data from git history
- Prevent future accumulation of large files

## Current State

### Repository Size
- **Current size:** 144.92 MB (primarily in `.git` history)
- **Target size:** < 100 MB
- **Location:** Most bloat is in git history, not working directory

### Main Contributors to Size

1. **Database files** (`*.db`, `*.sqlite`, `*.sqlite3`)
   - SQLite database files were committed throughout git history
   - These should never be version-controlled

2. **clearml-data/ directory**
   - Contains MongoDB and Elasticsearch data
   - Large binary datasets committed to git

3. **.tmp/ directories**
   - Python virtual environments (`venv`, `.venv`)
   - Temporary build artifacts
   - Downloaded dependencies

4. **Historical node_modules commits** (if present)
   - Node.js dependencies accidentally committed
   - Can be extremely large

> **📝 NOTE:** The `.gitignore` file has been updated and cleaned (reduced from 2,876 to 119 lines) to prevent these issues going forward.

## Prerequisites

### 1. Create a Backup

> **⚠️ WARNING:** Git history rewriting is destructive and cannot be undone. Always create a backup first.

```bash
# Clone a backup copy of the repository
cd ..
git clone --mirror c:/Users/admin/Desktop/GitHub-projects/FBA-Bench-Enterprise FBA-Bench-Enterprise-backup.git
```

### 2. Export Important Data

Before cleanup, ensure you have:
- Exported any important data from database files
- Documented the structure of removed directories
- Saved any configuration or state that might be lost

### 3. Required Tools

- **Git:** Already installed (verify with `git --version`)
- **BFG Repo-Cleaner:** Download from [https://rtyley.github.io/bfg-repo-cleaner/](https://rtyley.github.io/bfg-repo-cleaner/)
  - Requires Java Runtime Environment (JRE)
  - Download `bfg.jar` to your working directory

### 4. Team Coordination

> **⚠️ WARNING:** This cleanup requires a force push that will rewrite git history. Coordinate with your team:

- Notify all team members of the scheduled cleanup
- Ensure all pending work is committed and pushed
- Schedule the cleanup during low-activity periods
- Prepare instructions for team members to sync after cleanup

## Step-by-Step Cleanup Instructions

### Step 1: Verify Current .gitignore

First, confirm that the updated `.gitignore` file includes all necessary patterns:

```bash
# Navigate to repository root
cd c:/Users/admin/Desktop/GitHub-projects/FBA-Bench-Enterprise

# Check .gitignore contents
type .gitignore
```

Ensure it includes:
```
*.db
*.sqlite
*.sqlite3
clearml-data/
.tmp/
.venv/
venv/
```

Verify specific files are ignored:
```bash
# Check if a file is properly ignored
git check-ignore -v *.db
git check-ignore -v clearml-data/
```

### Step 2: Remove Files from Working Directory

Remove files from the git index (keep them locally if needed):

```bash
# Remove database files from tracking
git rm --cached *.db 2>$null
git rm --cached *.sqlite 2>$null
git rm --cached *.sqlite3 2>$null

# Remove directories from tracking
git rm --cached -r clearml-data/ 2>$null
git rm --cached -r .tmp/ 2>$null
git rm --cached -r .venv/ 2>$null
git rm --cached -r venv/ 2>$null

# Commit the changes
git commit -m "chore: remove large files from tracking"
```

> **📝 NOTE:** The `2>$null` suppresses errors if files don't exist in the index.

### Step 3: Clean Git History with BFG Repo-Cleaner

#### Option A: Using BFG (Recommended - Faster)

BFG Repo-Cleaner is significantly faster than `git filter-branch` for large repositories.

**Download BFG:**
```powershell
# Download BFG manually from https://rtyley.github.io/bfg-repo-cleaner/
# Or use PowerShell to download
Invoke-WebRequest -Uri "https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar" -OutFile "bfg.jar"
```

**Run BFG commands:**

```bash
# Remove files by pattern
java -jar bfg.jar --delete-files "*.db" .
java -jar bfg.jar --delete-files "*.sqlite" .
java -jar bfg.jar --delete-files "*.sqlite3" .

# Remove folders (note: protect HEAD to keep current state)
java -jar bfg.jar --delete-folders clearml-data --no-blob-protection .
java -jar bfg.jar --delete-folders .tmp --no-blob-protection .
java -jar bfg.jar --delete-folders .venv --no-blob-protection .
java -jar bfg.jar --delete-folders venv --no-blob-protection .
java -jar bfg.jar --delete-folders node_modules --no-blob-protection .

# Clean up git references and repack
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

> **📝 NOTE:** `--no-blob-protection` removes files from all commits, including HEAD. Omit this flag to protect current HEAD.

**Understanding BFG options:**
- `--delete-files`: Remove files matching pattern
- `--delete-folders`: Remove entire directories
- `--no-blob-protection`: Also clean HEAD (current) commit
- `.`: Run on current repository

### Step 4: Verify Size Reduction

Check the new repository size:

**PowerShell (Windows):**
```powershell
# Calculate .git directory size
$size = (Get-ChildItem -Path .git -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($size / 1MB, 2)
Write-Output "Repository size: $sizeMB MB"
```

**Git Bash / Linux / Mac:**
```bash
# Show .git directory size
du -sh .git
```

**Compare before and after:**
```bash
# Before: 144.92 MB
# After: Should be < 100 MB
```

### Step 5: Force Push

> **⚠️ WARNING:** Force pushing will rewrite repository history. Ensure team is coordinated.

**Push to remote:**
```bash
# Force push all branches
git push origin --force --all

# Force push all tags
git push origin --force --tags
```

> **⚠️ CRITICAL:** After force pushing, ALL team members must re-sync their local repositories (see Team Collaboration section).

## Alternative: Using git filter-branch

If you prefer using git's built-in tools instead of BFG:

```bash
# Remove database files from all history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch *.db *.sqlite *.sqlite3' \
  --prune-empty --tag-name-filter cat -- --all

# Remove directories from all history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch -r clearml-data .tmp .venv venv node_modules' \
  --prune-empty --tag-name-filter cat -- --all

# Clean up references
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

> **📝 NOTE:** `filter-branch` is slower than BFG but doesn't require additional tools.

**Option explanation:**
- `--force`: Overwrite existing backup refs
- `--index-filter`: Run command on each commit's index
- `--ignore-unmatch`: Don't fail if files don't exist
- `--prune-empty`: Remove commits that become empty
- `--tag-name-filter cat`: Rewrite tags to point to new commits

## Post-Cleanup Verification

### 1. Verify Files Are Gone from History

Search for removed files in git history:

```bash
# Search for .db files in history
git log --all --full-history -- "*.db"

# Search for specific directories
git log --all --full-history -- "clearml-data/"
git log --all --full-history -- ".tmp/"
```

> **✅ SUCCESS:** If these commands return no results, files are successfully removed.

### 2. Check Repository Size

```powershell
# PowerShell - Check final size
$size = (Get-ChildItem -Path .git -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($size / 1MB, 2)
Write-Output "Final repository size: $sizeMB MB"
```

### 3. Verify .gitignore Is Working

```bash
# Check that ignored files don't show up
git status

# Explicitly check ignored files
git check-ignore -v *.db
git check-ignore -v clearml-data/
```

> **✅ SUCCESS:** `git status` should show "working tree clean" and not list ignored files.

### 4. Test Clone Performance

```bash
# Clone in a new directory to test
cd ..
git clone c:/Users/admin/Desktop/GitHub-projects/FBA-Bench-Enterprise FBA-Bench-Enterprise-test
cd FBA-Bench-Enterprise-test

# Check size of fresh clone
du -sh .git  # Linux/Mac
# or
(Get-ChildItem -Path .git -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB  # PowerShell
```

## Team Collaboration

### For Team Members: How to Sync After Force Push

> **⚠️ WARNING:** Do NOT attempt to merge or pull after a force push. You must reset your local repository.

**Save any local work first:**
```bash
# Check for uncommitted changes
git status

# If you have uncommitted changes, stash them
git stash

# Or commit them to a temporary branch
git checkout -b temp-backup
git add .
git commit -m "Backup local changes"
git checkout main
```

**Reset to match remote:**
```bash
# Fetch the rewritten history
git fetch origin

# Reset your local branch to match remote (DESTRUCTIVE)
git reset --hard origin/main  # or your branch name

# Clean up any leftover files
git clean -fd
```

**Restore local work (if stashed):**
```bash
# Restore stashed changes
git stash pop

# Or merge from backup branch
git merge temp-backup
```

### Best Practices After Cleanup

1. **Immediate actions:**
   - Verify `git status` shows clean tree
   - Run `make ci-local` to ensure project still works
   - Test critical workflows

2. **Communication:**
   - Post in team chat when force push is complete
   - Share this guide with all team members
   - Provide support during re-sync process

3. **Monitoring:**
   - Check repository size weekly for first month
   - Monitor CI/CD pipelines for issues
   - Watch for re-introduction of large files

## Troubleshooting

### Issue: Size Doesn't Reduce Significantly

**Possible causes and solutions:**

1. **Remote still has old refs:**
   ```bash
   # Clean up remote refs
   git push origin --force --all
   git push origin --force --tags
   
   # Cleanup may need to run on remote (GitHub Actions or manual)
   ```

2. **Local refs remain:**
   ```bash
   # Clear all local refs
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

3. **Objects still in pack files:**
   ```bash
   # Aggressive garbage collection
   git repack -a -d --depth=250 --window=250
   git gc --aggressive --prune=now
   ```

### Issue: Merge Conflicts After Force Push

**For ongoing work:**

1. **Create a patch of your changes:**
   ```bash
   # Before resetting
   git diff > my-changes.patch
   ```

2. **Reset to match remote:**
   ```bash
   git fetch origin
   git reset --hard origin/main
   ```

3. **Apply your changes:**
   ```bash
   git apply my-changes.patch
   # Resolve any conflicts manually
   ```

### Issue: BFG or filter-branch Fails

**Common errors:**

1. **"dirty working directory":**
   ```bash
   # Commit or stash changes
   git stash
   # or
   git commit -am "WIP: temporary commit"
   ```

2. **Java errors with BFG:**
   ```bash
   # Verify Java installation
   java -version
   
   # Update Java if needed
   # Minimum: Java 8+
   ```

3. **Out of memory errors:**
   ```bash
   # Increase Java heap size
   java -Xmx2G -jar bfg.jar --delete-files "*.db" .
   ```

### Issue: Files Reappear After Cleanup

**Cause:** Someone pushed old commits or merged from old branches.

**Solution:**
```bash
# Identify the source
git log --all --oneline -- "path/to/file.db"

# Force push again to remove
git push origin --force --all
```

**Prevention:**
- Delete old branches after cleanup
- Update branch protection rules
- Add pre-commit hooks (see Maintenance section)

## Maintenance

### Prevent Future Issues

#### 1. Regular .gitignore Audits

**Monthly review:**
```bash
# List all tracked files
git ls-files

# Find large files
git ls-files | xargs ls -lh | sort -k5 -rh | head -20
```

**Add to .gitignore if found:**
- Build artifacts
- IDE configurations
- OS-specific files
- Temporary files
- Large data files

#### 2. Pre-commit Hooks to Catch Large Files

Create `.git/hooks/pre-commit`:

```bash
#!/bin/sh

# Maximum file size (100KB = 102400 bytes)
MAX_SIZE=102400

# Check for large files
large_files=$(git diff --cached --name-only | while read file; do
  if [ -f "$file" ]; then
    size=$(wc -c <"$file")
    if [ $size -gt $MAX_SIZE ]; then
      echo "$file ($(numfmt --to=iec-i --suffix=B $size))"
    fi
  fi
done)

if [ -n "$large_files" ]; then
  echo "ERROR: Attempting to commit large files:"
  echo "$large_files"
  echo ""
  echo "Please add these files to .gitignore or use Git LFS"
  exit 1
fi
```

**Install hook:**
```bash
# Make executable (Linux/Mac)
chmod +x .git/hooks/pre-commit

# Or use pre-commit framework
pip install pre-commit
pre-commit install
```

#### 3. Use Git LFS for Large Files

For legitimate large files (datasets, models):

```bash
# Install Git LFS
git lfs install

# Track specific file types
git lfs track "*.psd"
git lfs track "*.bin"
git lfs track "data/**"

# Commit .gitattributes
git add .gitattributes
git commit -m "chore: configure Git LFS"
```

#### 4. CI/CD Pipeline Checks

Add to GitHub Actions or CI pipeline:

```yaml
# .github/workflows/size-check.yml
name: Repository Size Check

on: [push, pull_request]

jobs:
  check-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check large files
        run: |
          # Find files larger than 1MB
          find . -type f -size +1M -not -path "./.git/*"
          # Fail if any found
          [ -z "$(find . -type f -size +1M -not -path "./.git/*")" ]
```

#### 5. Documentation and Training

**Create a checklist for new contributors:**

- [ ] Review `.gitignore` before committing
- [ ] Never commit database files
- [ ] Never commit `node_modules` or virtual environments
- [ ] Use `.env` for local configuration (not tracked)
- [ ] Check file size before committing large files
- [ ] Use Git LFS for necessary large files

**Regular reminders:**
- Include in onboarding documentation
- Add to PR template
- Mention in commit message guidelines

### Monitoring Repository Health

**Weekly checks:**
```bash
# Check repository size
du -sh .git

# List largest files in repo
git ls-tree -r -l HEAD | sort -k 4 -rn | head -10

# Find largest objects in pack files
git verify-pack -v .git/objects/pack/*.idx | sort -k 3 -rn | head -10
```

**Set up alerts:**
- GitHub repository insights → Traffic
- Monitor clone/fetch times
- Watch for size increases in automation

### Backup Strategy

**Regular backups:**
```bash
# Weekly mirror backup
git clone --mirror <repo-url> backup-$(date +%Y%m%d).git
```

**Cloud storage:**
- Store backups in S3, Google Cloud Storage, or Azure Blob
- Keep at least 4 weekly backups
- Document restoration procedures

---

## Summary

This guide covered:

1. **Assessment:** Identified 144.92 MB repository with database files, data directories, and virtual environments in history
2. **Cleanup:** Used BFG Repo-Cleaner or git filter-branch to remove files from all commits
3. **Verification:** Confirmed size reduction and proper .gitignore configuration
4. **Team sync:** Provided instructions for team members to re-sync after force push
5. **Prevention:** Established pre-commit hooks, monitoring, and best practices

**Next steps:**
- [ ] Complete cleanup following Step 1-5
- [ ] Coordinate team re-sync
- [ ] Implement pre-commit hooks
- [ ] Set up CI/CD size checks
- [ ] Schedule regular repository audits

**Need help?** Review the Troubleshooting section or consult with the team lead before proceeding with destructive operations.

---

*Last updated: 2025-11-13*
*Maintained by: FBA-Bench-Enterprise Team*