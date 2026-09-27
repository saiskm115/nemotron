# frontend/start.ps1 - Starts DiarizeStudio from frontend directory
$ErrorActionPreference = "SilentlyContinue"
$rootDir = (Get-Item $PSScriptRoot).Parent.FullName
powershell -ExecutionPolicy Bypass -File "$rootDir\start.ps1"
