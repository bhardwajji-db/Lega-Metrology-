# MetrCheck AI - Quick Secure Tunnel for Mobile / Any Phone
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " Starting Secure Cloudflare HTTPS Tunnel for Mobile    " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

& "cloudflared.exe" tunnel --url https://localhost:5173 --no-tls-verify
