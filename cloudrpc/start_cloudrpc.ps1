# CloudSim gRPC Server Startup Script
# This script starts the cloudrpc gRPC server
# The server will stop when you close this terminal or press Ctrl+C

Write-Host "Starting CloudSim gRPC Server (cloudrpc)..." -ForegroundColor Green
Write-Host "Server will stop when you close this terminal or press Ctrl+C" -ForegroundColor Yellow
Write-Host "gRPC server listening on port 50051" -ForegroundColor Cyan
Write-Host ""

cd cloudrpc
python server.py

