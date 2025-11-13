<#
.SYNOPSIS
    Repository Size Cleanup Script for FBA-Bench-Enterprise

.DESCRIPTION
    This script helps reduce repository size by removing large ignored files from git tracking
    and providing instructions for using BFG Repo-Cleaner to purge them from history.
    
    WARNING: This script performs destructive git operations. Always ensure you have a backup
    and that all important changes are committed before running.

.NOTES
    Author: FBA-Bench Team
    Version: 1.0.0
    See docs/repository-cleanup-guide.md for complete cleanup instructions.
#>

# Requires PowerShell 5.1 or higher
#Requires -Version 5.1

# Stop on errors
$ErrorActionPreference = "Stop"

# ============================================================================
# Helper Functions
# ============================================================================

function Test-GitAvailable {
    <#
    .SYNOPSIS
        Checks if git is available in the system PATH
    #>
    try {
        $null = git --version 2>&1
        return $true
    }
    catch {
        Write-Host "❌ Git is not available in your PATH." -ForegroundColor Red
        Write-Host "Please install Git and ensure it's in your system PATH." -ForegroundColor Red
        return $false
    }
}

function Get-DirectorySize {
    <#
    .SYNOPSIS
        Calculates the size of a directory in MB
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    
    if (-not (Test-Path $Path)) {
        return 0
    }
    
    try {
        $bytes = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | 
                  Measure-Object -Property Length -Sum).Sum
        
        if ($null -eq $bytes) {
            return 0
        }
        
        return [math]::Round($bytes / 1MB, 2)
    }
    catch {
        Write-Host "⚠️  Warning: Could not calculate size for $Path" -ForegroundColor Yellow
        return 0
    }
}

function Check-RepositorySize {
    <#
    .SYNOPSIS
        Displays current repository sizes
    .OUTPUTS
        Returns the .git directory size in MB
    #>
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Current Repository Size" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    # Calculate .git directory size
    $gitDirSize = Get-DirectorySize -Path ".git"
    Write-Host "📊 .git directory size: " -NoNewline
    Write-Host "$gitDirSize MB" -ForegroundColor $(if ($gitDirSize -gt 100) { "Red" } else { "Green" })
    
    # Calculate working directory size
    $workingDirSize = Get-DirectorySize -Path "."
    Write-Host "📊 Working directory size: " -NoNewline
    Write-Host "$workingDirSize MB" -ForegroundColor Cyan
    
    Write-Host ""
    
    return $gitDirSize
}

function Remove-IgnoredFiles {
    <#
    .SYNOPSIS
        Removes ignored files from git tracking
    .DESCRIPTION
        Removes database files, clearml-data, and .tmp directories from git tracking.
        Files are only unstaged, not deleted from the file system.
    #>
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Removing Ignored Files from Git Tracking" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    $filesRemoved = @()
    $errorsEncountered = @()
    
    # Remove .db files
    Write-Host "🔍 Searching for .db files..." -ForegroundColor Yellow
    try {
        $output = git ls-files "*.db" 2>&1
        if ($output -and $output.Count -gt 0) {
            git rm --cached *.db 2>&1 | Out-Null
            $filesRemoved += "*.db files"
            Write-Host "✅ Removed *.db files from tracking" -ForegroundColor Green
        }
        else {
            Write-Host "ℹ️  No .db files currently tracked" -ForegroundColor Gray
        }
    }
    catch {
        if ($_.Exception.Message -notmatch "did not match any files") {
            $errorsEncountered += "Failed to remove .db files: $($_.Exception.Message)"
        }
    }
    
    # Remove .sqlite* files
    Write-Host "🔍 Searching for .sqlite* files..." -ForegroundColor Yellow
    try {
        $output = git ls-files "*.sqlite*" 2>&1
        if ($output -and $output.Count -gt 0) {
            git rm --cached "*.sqlite*" 2>&1 | Out-Null
            $filesRemoved += "*.sqlite* files"
            Write-Host "✅ Removed *.sqlite* files from tracking" -ForegroundColor Green
        }
        else {
            Write-Host "ℹ️  No .sqlite* files currently tracked" -ForegroundColor Gray
        }
    }
    catch {
        if ($_.Exception.Message -notmatch "did not match any files") {
            $errorsEncountered += "Failed to remove .sqlite* files: $($_.Exception.Message)"
        }
    }
    
    # Remove clearml-data directory
    Write-Host "🔍 Checking for clearml-data directory..." -ForegroundColor Yellow
    try {
        $output = git ls-files "clearml-data/*" 2>&1
        if ($output -and $output.Count -gt 0) {
            git rm --cached -r clearml-data/ 2>&1 | Out-Null
            $filesRemoved += "clearml-data/ directory"
            Write-Host "✅ Removed clearml-data/ directory from tracking" -ForegroundColor Green
        }
        else {
            Write-Host "ℹ️  clearml-data/ directory not currently tracked" -ForegroundColor Gray
        }
    }
    catch {
        if ($_.Exception.Message -notmatch "did not match any files") {
            $errorsEncountered += "Failed to remove clearml-data/: $($_.Exception.Message)"
        }
    }
    
    # Remove .tmp directory
    Write-Host "🔍 Checking for .tmp directory..." -ForegroundColor Yellow
    try {
        $output = git ls-files ".tmp/*" 2>&1
        if ($output -and $output.Count -gt 0) {
            git rm --cached -r .tmp/ 2>&1 | Out-Null
            $filesRemoved += ".tmp/ directory"
            Write-Host "✅ Removed .tmp/ directory from tracking" -ForegroundColor Green
        }
        else {
            Write-Host "ℹ️  .tmp/ directory not currently tracked" -ForegroundColor Gray
        }
    }
    catch {
        if ($_.Exception.Message -notmatch "did not match any files") {
            $errorsEncountered += "Failed to remove .tmp/: $($_.Exception.Message)"
        }
    }
    
    Write-Host ""
    
    # Display summary
    if ($filesRemoved.Count -gt 0) {
        Write-Host "📋 Summary of removed items:" -ForegroundColor Cyan
        foreach ($item in $filesRemoved) {
            Write-Host "   • $item" -ForegroundColor Green
        }
        Write-Host ""
    }
    else {
        Write-Host "ℹ️  No files needed to be removed from tracking" -ForegroundColor Gray
        Write-Host ""
    }
    
    # Display errors if any
    if ($errorsEncountered.Count -gt 0) {
        Write-Host "⚠️  Warnings encountered:" -ForegroundColor Yellow
        foreach ($error in $errorsEncountered) {
            Write-Host "   • $error" -ForegroundColor Yellow
        }
        Write-Host ""
    }
    
    return $filesRemoved.Count -gt 0
}

function Show-CleanupInstructions {
    <#
    .SYNOPSIS
        Displays instructions for using BFG Repo-Cleaner
    #>
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Next Steps: BFG Repo-Cleaner" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    Write-Host "After committing the changes above, use BFG Repo-Cleaner to purge files from git history.`n" -ForegroundColor White
    
    Write-Host "1️⃣  Download BFG Repo-Cleaner:" -ForegroundColor Yellow
    Write-Host "   https://rtyley.github.io/bfg-repo-cleaner/`n" -ForegroundColor Cyan
    
    Write-Host "2️⃣  Run these commands:" -ForegroundColor Yellow
    Write-Host "   # Remove database files from history" -ForegroundColor Gray
    Write-Host "   java -jar bfg.jar --delete-files `"*.db`"`n" -ForegroundColor White
    
    Write-Host "   # Remove SQLite files from history" -ForegroundColor Gray
    Write-Host "   java -jar bfg.jar --delete-files `"*.sqlite*`"`n" -ForegroundColor White
    
    Write-Host "   # Remove clearml-data directory from history" -ForegroundColor Gray
    Write-Host "   java -jar bfg.jar --delete-folders clearml-data`n" -ForegroundColor White
    
    Write-Host "   # Remove .tmp directory from history" -ForegroundColor Gray
    Write-Host "   java -jar bfg.jar --delete-folders .tmp`n" -ForegroundColor White
    
    Write-Host "   # Clean up the repository" -ForegroundColor Gray
    Write-Host "   git reflog expire --expire=now --all" -ForegroundColor White
    Write-Host "   git gc --prune=now --aggressive`n" -ForegroundColor White
    
    Write-Host "3️⃣  Verify the cleanup:" -ForegroundColor Yellow
    Write-Host "   Run this script again to check the new repository size`n" -ForegroundColor White
    
    Write-Host "📖 For detailed instructions, see:" -ForegroundColor Cyan
    Write-Host "   docs/repository-cleanup-guide.md`n" -ForegroundColor White
}

function Get-UserConfirmation {
    <#
    .SYNOPSIS
        Prompts user for confirmation before proceeding
    .OUTPUTS
        Returns $true if user confirms, $false otherwise
    #>
    Write-Host "⚠️  WARNING: This script will modify your git repository" -ForegroundColor Yellow
    Write-Host "⚠️  Files will be removed from git tracking (but NOT deleted from disk)" -ForegroundColor Yellow
    Write-Host "⚠️  Ensure you have committed all important changes before proceeding`n" -ForegroundColor Yellow
    
    $response = Read-Host "Do you want to proceed? (Y/N)"
    
    if ($response -match '^[Yy]$') {
        return $true
    }
    
    Write-Host "`n❌ Operation cancelled by user" -ForegroundColor Red
    return $false
}

# ============================================================================
# Main Execution
# ============================================================================

function Main {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Repository Size Cleanup Script" -ForegroundColor Cyan
    Write-Host "FBA-Bench-Enterprise" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    # Check if git is available
    if (-not (Test-GitAvailable)) {
        exit 1
    }
    
    # Check if we're in a git repository
    try {
        $null = git rev-parse --git-dir 2>&1
    }
    catch {
        Write-Host "❌ This script must be run from within a git repository" -ForegroundColor Red
        exit 1
    }
    
    # Display current size
    $beforeSize = Check-RepositorySize
    
    # Get user confirmation
    if (-not (Get-UserConfirmation)) {
        exit 0
    }
    
    Write-Host ""
    
    # Remove ignored files from tracking
    $changesWereMade = Remove-IgnoredFiles
    
    # Show commit instructions if changes were made
    if ($changesWereMade) {
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Next Step: Commit the Changes" -ForegroundColor Cyan
        Write-Host "========================================`n" -ForegroundColor Cyan
        
        Write-Host "✅ Files have been removed from git tracking" -ForegroundColor Green
        Write-Host "📝 Please commit these changes:`n" -ForegroundColor Yellow
        
        Write-Host "   git commit -m `"chore: remove large files from tracking`"`n" -ForegroundColor White
        
        Write-Host "After committing, continue with BFG Repo-Cleaner (see below)`n" -ForegroundColor Yellow
    }
    
    # Show BFG instructions
    Show-CleanupInstructions
    
    # Show size check reminder
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "After Cleanup" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    Write-Host "To verify the cleanup was successful, run this script again:" -ForegroundColor White
    Write-Host "   .\scripts\cleanup-repo-size.ps1`n" -ForegroundColor Cyan
    
    Write-Host "✅ Script completed successfully" -ForegroundColor Green
    Write-Host ""
}

# Run the main function
try {
    Main
}
catch {
    Write-Host "`n❌ An error occurred:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "`nStack Trace:" -ForegroundColor Yellow
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    exit 1
}