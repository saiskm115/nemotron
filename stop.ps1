# stop.ps1 - Stops all DiarizeStudio processes completely
$ErrorActionPreference = "SilentlyContinue"

Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "     Stopping DiarizeStudio Processes     " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

# 1. Kill process on port 8000 (Backend)
$p8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($p8000) {
    foreach ($pid_val in $p8000) {
        Stop-Process -Id $pid_val -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Backend on port 8000 (PID: $pid_val)" -ForegroundColor Green
    }
} else {
    Write-Host "No process listening on port 8000." -ForegroundColor DarkGray
}

# 2. Kill process on port 5173 (Frontend)
$p5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($p5173) {
    foreach ($pid_val in $p5173) {
        Stop-Process -Id $pid_val -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Frontend on port 5173 (PID: $pid_val)" -ForegroundColor Green
    }
} else {
    Write-Host "No process listening on port 5173." -ForegroundColor DarkGray
}

# 3. Kill any lingering uvicorn or vite processes
Get-Process -Name "python", "py", "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "backend.main:app" -or $_.CommandLine -match "vite"
} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "All DiarizeStudio processes have been stopped completely." -ForegroundColor Green
