# Cloudflare Tunnel Setup for fbabench.com

This guide covers setting up a permanent Cloudflare Tunnel to expose FBA-Bench at `fbabench.com`.

## Prerequisites

- Cloudflare account with `fbabench.com` domain configured
- `cloudflared` installed (`winget install --id Cloudflare.cloudflared -e`)
- FBA-Bench running locally on port 80

## Quick Tunnel (Temporary)

For quick testing without account setup:

```powershell
# Start temporary tunnel (URL changes each time)
cloudflared tunnel --url http://localhost:80
```

This creates a URL like `https://random-words.trycloudflare.com`.

## Named Tunnel (Permanent - Recommended)

### Step 1: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser to authenticate and downloads a certificate to `~/.cloudflared/cert.pem`.

### Step 2: Create a Named Tunnel

```bash
cloudflared tunnel create fba-bench
```

This creates a tunnel and outputs a Tunnel ID (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

### Step 3: Configure the Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: fba-bench
credentials-file: C:\Users\<username>\.cloudflared\<tunnel-id>.json

ingress:
  # Main domain
  - hostname: fbabench.com
    service: http://localhost:80
  
  # WWW subdomain
  - hostname: www.fbabench.com
    service: http://localhost:80
  
  # API subdomain (optional)
  - hostname: api.fbabench.com
    service: http://localhost:80
  
  # Catch-all (required)
  - service: http_status:404
```

### Step 4: Configure Cloudflare DNS

In the Cloudflare dashboard for `fbabench.com`:

1. Go to **DNS** → **Records**
2. Add CNAME records:

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | @ | `<tunnel-id>.cfargotunnel.com` | Proxied |
| CNAME | www | `<tunnel-id>.cfargotunnel.com` | Proxied |

Or use the CLI:
```bash
cloudflared tunnel route dns fba-bench fbabench.com
cloudflared tunnel route dns fba-bench www.fbabench.com
```

### Step 5: Run the Tunnel

```bash
# Run in foreground
cloudflared tunnel run fba-bench

# Or install as a service (Windows)
cloudflared service install
cloudflared service start
```

## Running as Windows Service

To run the tunnel automatically on system startup:

```powershell
# Install the service
cloudflared service install

# Start the service
Start-Service cloudflared

# Check status
Get-Service cloudflared
```

## Verification

After setup, verify the tunnel is working:

```bash
# Check health endpoint
curl https://fbabench.com/api/v1/health

# Check leaderboard
curl https://fbabench.com/api/v1/leaderboard
```

## Troubleshooting

### Tunnel not connecting
- Check `cloudflared tunnel info fba-bench` for status
- Verify credentials file exists at the path in config.yml
- Check Windows Firewall isn't blocking cloudflared

### DNS not resolving
- Verify CNAME records in Cloudflare dashboard
- Wait 1-2 minutes for DNS propagation
- Use `nslookup fbabench.com` to verify

### SSL certificate errors
- Ensure Cloudflare SSL/TLS mode is set to "Flexible" or "Full"
- Cloudflare handles SSL termination automatically

## Configuration Reference

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TUNNEL_ORIGIN_CERT` | Path to origin certificate |
| `TUNNEL_LOGLEVEL` | Log level (debug, info, warn, error) |
| `TUNNEL_METRICS` | Metrics server address |

### Cloudflare Account Info

- **Account ID**: `20d723d8016cca307896f7254d8e421c`
- **Workers Subdomain**: `andrewdarcy530.workers.dev`
- **Domain**: `fbabench.com`

## Related Documentation

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps)
- [FBA-Bench Deployment Guide](../deployment.md)
- [Deployment Fixes](./deployment_fixes.md)
