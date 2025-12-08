# CloudSim Backend Server Startup Script
# This script starts the backend API server (REST gateway to gRPC)
# IMPORTANT: Start cloudrpc server first using: cloudrpc/start_cloudrpc.ps1
# The server will stop when you close this terminal or press Ctrl+C

Write-Host "Starting CloudSim Backend API Server (REST Gateway)..." -ForegroundColor Green
Write-Host "NOTE: Make sure cloudrpc server is running on port 50051" -ForegroundColor Yellow
Write-Host "Start it with: cloudrpc/start_cloudrpc.ps1" -ForegroundColor Yellow
Write-Host "Server will stop when you close this terminal or press Ctrl+C" -ForegroundColor Yellow
Write-Host ""

cd backend
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload

