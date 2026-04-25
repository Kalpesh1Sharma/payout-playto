param(
  [switch]$NoRebuild
)

$ErrorActionPreference = "Stop"

$buildFlag = "--build"
if ($NoRebuild) {
  $buildFlag = ""
}

Write-Host "Starting Playto stack via docker compose..."
docker compose up -d $buildFlag

Write-Host "Waiting briefly for services to stabilize..."
Start-Sleep -Seconds 12

Write-Host "Checking backend merchants endpoint..."
try {
  $resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/merchants/" -Method Get -TimeoutSec 20
  $merchantCount = @($resp).Count
  Write-Host "Smoke check passed. Merchants endpoint reachable. Count: $merchantCount"
} catch {
  Write-Host "Smoke check failed. Backend endpoint not reachable."
  Write-Host "Run: docker compose logs backend worker beat"
  throw
}

Write-Host "Checking frontend URL..."
try {
  $frontend = Invoke-WebRequest -Uri "http://localhost:5173" -Method Get -TimeoutSec 20
  if ($frontend.StatusCode -ge 200 -and $frontend.StatusCode -lt 400) {
    Write-Host "Frontend reachable at http://localhost:5173"
  } else {
    throw "Unexpected frontend status code: $($frontend.StatusCode)"
  }
} catch {
  Write-Host "Frontend check failed."
  Write-Host "Run: docker compose logs frontend"
  throw
}

Write-Host "Smoke check complete."
