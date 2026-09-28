# Determine project root
$root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Starting DiarizeStudio Suite       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Terminate any previous processes on port 8000 or 5173
$p8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($p8000) { Stop-Process -Id $p8000 -Force -ErrorAction SilentlyContinue }

$p5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($p5173) { Stop-Process -Id $p5173 -Force -ErrorAction SilentlyContinue }

# 2. Launch Backend daemon
Write-Host "[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Green
$backendProc = Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $root -PassThru -WindowStyle Hidden

# Wait for backend health check (up to 10s)
$healthy = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 1
        if ($res.status -eq "healthy") {
            $healthy = $true
            break
        }
    } catch {}
}

if ($healthy) {
    Write-Host "  -> Backend is ready and healthy at http://127.0.0.1:8000" -ForegroundColor Green
} else {
    Write-Host "  -> WARNING: Backend startup taking longer than expected. Check uvicorn backend.main:app" -ForegroundColor Yellow
}

# 3. Launch Frontend in Vite dev server
Write-Host "[2/2] Starting Vite Frontend on http://127.0.0.1:5173..." -ForegroundColor Green
Set-Location -Path "$root\frontend"

Write-Host ""
Write-Host "Application is live:" -ForegroundColor Yellow
Write-Host "  -> Frontend UI:  http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "  -> Backend API:  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "  -> Swagger Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C or run .\stop.ps1 in another terminal to stop all processes." -ForegroundColor DarkGray

npm run dev -- --host 127.0.0.1 --port 5173
