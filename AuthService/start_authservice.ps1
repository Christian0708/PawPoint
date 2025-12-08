# AuthService Startup Script
# This script starts the Authentication gRPC server on port 51234

Write-Host "Starting AuthService gRPC Server..." -ForegroundColor Green
Write-Host "Server will stop when you close this terminal or press Ctrl+C" -ForegroundColor Yellow
Write-Host ""

cd $PSScriptRoot
python cloud.py

