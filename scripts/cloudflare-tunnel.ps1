# Cloudflare Tunnel Script for FBA-Bench
# This script creates a quick tunnel to expose the local API server
# Usage: .\scripts\cloudflare-tunnel.ps1 [port]
#
# For a persistent tunnel with custom domain (fbabench.com):
#   1. Run: cloudflared tunnel login
#   2. Run: cloudflared tunnel create fba-bench
#   3. Configure DNS in Cloudflare dashboard
#   4. Run: cloudflared tunnel run fba-bench

param(
    [int]$Port = 80,
    [string]$Protocol = "http"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FBA-Bench Cloudflare Tunnel" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if cloudflared is installed
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Host "ERROR: cloudflared is not installed." -ForegroundColor Red
    Write-Host "Install with: winget install --id Cloudflare.cloudflared -e" -ForegroundColor Yellow
    exit 1
}

# Check if the local server is running
try {
    $response = Invoke-WebRequest -Uri "${Protocol}://localhost:${Port}/api/v1/health" -UseBasicParsing -TimeoutSec 5
    $health = $response.Content | ConvertFrom-Json
    Write-Host "Local server is healthy: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Local server may not be running on port $Port" -ForegroundColor Yellow
    Write-Host "Start it with: docker compose -f docker-compose.prod.yml up -d" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "Starting Cloudflare Quick Tunnel..." -ForegroundColor Green
Write-Host "This will create a temporary public URL for your local server." -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the tunnel." -ForegroundColor Yellow
Write-Host ""

# Start the tunnel
cloudflared tunnel --url "${Protocol}://localhost:${Port}"
