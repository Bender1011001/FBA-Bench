<#
.SYNOPSIS
    Repository Size Cleanup Script for FBA-Bench

.DESCRIPTION
    This script helps reduce repository size by identifying large files and providing
    instructions for using BFG Repo-Cleaner to purge them from history.
    
    WARNING: This script performs destructive git operations. Always ensure you have a backup
    and that all important changes are committed before running.

.NOTES
    Author: FBA-Bench Team
    Version: 1.1.0
    See docs/repository-cleanup-guide.md for complete cleanup instructions.
#>

# Requires PowerShell 5.1 or higher
#Requires -Version 5.1

# Stop on errors
$ErrorActionPreference = "Stop"

function Get-DirectorySize {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    try {
        $bytes = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        if ($null -eq $bytes) { return 0 }
        return [math]::Round($bytes / 1MB, 2)
    }
    catch { return 0 }
}

function Main {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Repository Size Cleanup Helper" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    # Check git
    try { $null = git --version } catch { Write-Host "❌ Git not found."; exit 1 }
    
    # Check repo size
    $gitSize = Get-DirectorySize -Path ".git"
    Write-Host "📊 Current .git directory size: $gitSize MB" -ForegroundColor $(if ($gitSize -gt 100) { "Red" } else { "Green" })
    
    Write-Host "`n🔍 Large files have been removed from future tracking."
    Write-Host "   To reduce the .git folder size, you must rewrite history."
    
    Write-Host "`n📋 Instructions:" -ForegroundColor Yellow
    Write-Host "1. Download BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/"
    Write-Host "2. Run the following commands (requires Java):"
    Write-Host "   java -jar bfg.jar --delete-folders clearml-data"
    Write-Host "   java -jar bfg.jar --delete-folders node_modules"
    Write-Host "   java -jar bfg.jar --delete-folders .tmp"
    Write-Host "   git reflog expire --expire=now --all"
    Write-Host "   git gc --prune=now --aggressive"
    
    Write-Host "`n⚠️  WARNING: This will rewrite history. You will need to 'git push --force'." -ForegroundColor Red
    Write-Host "   See docs/repository-cleanup-guide.md for details."
}

Main