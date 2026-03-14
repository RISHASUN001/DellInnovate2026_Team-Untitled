# Full Backend Stack Launcher for SCS Dashboard
# Launches all required services in separate PowerShell windows with color-coded terminals
# Press Ctrl+C in THIS window to stop all services

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\janha\Desktop\DellInnovate2026_Team-Untitled"
$VenvPython = "$ProjectRoot\.venv\Scripts\python.exe"

$services = @(
    @{Name="auth-service";    Port=8001; Module="main:app";              Dir="$ProjectRoot\auth-service";    Bg="DarkGreen"}
    @{Name="case-service";    Port=8003; Module="app.main:app";          Dir="$ProjectRoot\case-service";    Bg="DarkBlue"}
    @{Name="chatbot-service"; Port=8000; Module="app.main:app";          Dir="$ProjectRoot\chatbot-service"; Bg="DarkMagenta"}
    @{Name="mcp-service";     Port=8007; Module="app.main:app";          Dir="$ProjectRoot\mcp-service";     Bg="DarkCyan"}
    @{Name="scraper-service"; Port=8005; Module="app:app";               Dir="$ProjectRoot\scraper-service"; Bg="DarkYellow"}
    @{Name="backend-api";     Port=8004; Module="app:app";               Dir="$ProjectRoot\backend";         Bg="DarkRed"}
    @{Name="image-service";   Port=8006; Module="api.main:app";          Dir="$ProjectRoot\backend\image-service"; Bg="DarkGray"}
    @{Name="api-gateway";     Port=8010; Module="main:app";              Dir="$ProjectRoot\api-gateway";     Bg="Black"}
)

Write-Host "`n✅ Starting SCS Backend Services..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C in THIS window to stop all services`n" -ForegroundColor Yellow

foreach ($svc in $services) {
    $title = "$($svc.Name) [:$($svc.Port)]"
    if ($svc.Name -eq "auth-service") {
        $cmd = "Set-Location '$($svc.Dir)' ; `$env:PYTHONUNBUFFERED='1' ; `$env:OAUTH_AUTHORIZE_URL='https://accounts.google.com/o/oauth2/v2/auth' ; `$env:OAUTH_TOKEN_URL='https://oauth2.googleapis.com/token' ; `$env:OAUTH_REDIRECT_URI='http://localhost:8010/callback' ; `$env:OAUTH_CLIENT_ID='5160573405-efm2lesqgp1r6vfis1igu75575khp2fr.apps.googleusercontent.com' ; `$env:OAUTH_CLIENT_SECRET='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' ; `$env:FRONTEND_REDIRECT_URL='http://localhost:5173' ; & '$VenvPython' -m uvicorn $($svc.Module) --host 0.0.0.0 --port $($svc.Port) --reload"
    } elseif ($svc.Name -eq "api-gateway") {
        $cmd = "Set-Location '$($svc.Dir)' ; `$env:PYTHONUNBUFFERED='1' ; `$env:AUTH_SERVICE_URL='http://localhost:8001' ; `$env:SCRAPER_SERVICE_URL='http://localhost:8005' ; `$env:ANALYSIS_SERVICE_URL='http://localhost:8004/api/unified-pipeline/analyze-user' ; `$env:CHATBOT_SERVICE_URL='http://localhost:8000' ; `$env:IMAGE_SERVICE_URL='http://localhost:8006' ; `$env:MCP_SERVICE_URL='http://localhost:8007' ; `$env:CASE_SERVICE_URL='http://localhost:8003' ; & '$VenvPython' -m uvicorn $($svc.Module) --host 0.0.0.0 --port $($svc.Port) --reload"
    } else {
        $cmd = "Set-Location '$($svc.Dir)' ; `$env:PYTHONUNBUFFERED='1' ; & '$VenvPython' -m uvicorn $($svc.Module) --host 0.0.0.0 --port $($svc.Port) --reload"
    }
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
    Write-Host "  ► Started: $($svc.Name) on port $($svc.Port)" -ForegroundColor Cyan
    Start-Sleep -Milliseconds 800
}

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "All services launched!" -ForegroundColor Green
Write-Host "` Service Health Checks:`n" -ForegroundColor Yellow

Start-Sleep -Seconds 8

foreach ($svc in $services) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:$($svc.Port)/health" -Method GET -TimeoutSec 3 -ErrorAction Stop
        Write-Host "   $($svc.Name) → http://localhost:$($svc.Port)" -ForegroundColor Green
    } catch {
        Write-Host "   $($svc.Name) → http://localhost:$($svc.Port) (starting...)" -ForegroundColor Yellow
    }
}

Write-Host "`Frontend Development Server:" -ForegroundColor Yellow
Write-Host "  Run: npm run dev" -ForegroundColor Cyan
Write-Host "  URL: http://localhost:5173" -ForegroundColor Cyan

Write-Host "`nOAuth Login Flow:" -ForegroundColor Yellow
Write-Host "  1. Open http://localhost:5173" -ForegroundColor White
Write-Host "  2. Click 'Sign in with Google OAuth'" -ForegroundColor White
Write-Host "  3. Complete OAuth → auto-redirect with token" -ForegroundColor White

Write-Host "`nAPI Documentation:" -ForegroundColor Yellow
Write-Host "  Gateway:  http://localhost:8010/docs" -ForegroundColor Cyan
Write-Host "  Case:     http://localhost:8003/docs" -ForegroundColor Cyan
Write-Host "  Chatbot:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8004/docs" -ForegroundColor Cyan

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C here to stop all services" -ForegroundColor Red
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor DarkGray

try {
    while ($true) {
        Start-Sleep -Seconds 60
    }
} finally {
    Write-Host "`n Stopping all services..." -ForegroundColor Red
    Get-Process -Name powershell -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -match "auth-service|case-service|chatbot-service|mcp-service|scraper-service|backend-api|image-service|api-gateway"} | Stop-Process -Force
    Write-Host "All services stopped.`n" -ForegroundColor Green
}
