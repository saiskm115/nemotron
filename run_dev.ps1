# DiarizeStudio Dev Launcher (PowerShell)
Write-Host "Starting DiarizeStudio..." -ForegroundColor Cyan

# 1. Start Backend in background process
Write-Host "Launching FastAPI Backend on http://localhost:8000..." -ForegroundColor Green
$backendJob = Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" -PassThru

# 2. Start Frontend
Write-Host "Launching Vite Frontend on http://localhost:5173..." -ForegroundColor Green
Set-Location -Path "$PSScriptRoot\frontend"
npm run dev

# Cleanup backend when frontend terminates
if ($backendJob) {
    Stop-Process -Id $backendJob.Id -ErrorAction SilentlyContinue
}
