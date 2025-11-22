# Repository Cleanup Guide

This repository has been cleaned up to remove large files from future tracking. However, these files still exist in the git history. To fully reduce the repository size (e.g., for cloning), you should purge them from the history.

## What has been done
1.  Updated `.gitignore` to exclude:
    *   `clearml-data/`
    *   `node_modules/`
    *   `.tmp/`
    *   `learning_data/*.corrupt`
2.  Removed these files from the current git index.

## How to purge history (Optional but Recommended)

To remove these files from the entire git history, use [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/).

### Prerequisites
*   Java Runtime Environment (JRE) installed.
*   `bfg.jar` downloaded from the link above.

### Steps

1.  **Backup your repository!**
    ```bash
    cp -r FBA-Bench-Enterprise FBA-Bench-Enterprise-BACKUP
    ```

2.  **Run BFG to remove large folders:**
    ```bash
    java -jar bfg.jar --delete-folders clearml-data
    java -jar bfg.jar --delete-folders node_modules
    java -jar bfg.jar --delete-folders .tmp
    ```

3.  **Run BFG to remove specific large files:**
    ```bash
    java -jar bfg.jar --delete-files "*.corrupt"
    java -jar bfg.jar --delete-files "*.db"
    java -jar bfg.jar --delete-files "*.sqlite*"
    ```

4.  **Clean the repository:**
    ```bash
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive
    ```

5.  **Force push changes (WARNING: This rewrites history for everyone):**
    ```bash
    git push --force
    ```

## Verification
After running these commands, your `.git` directory size should be significantly reduced.