param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    Write-Host "Manual benchmark: http://127.0.0.1:$Port/"
    Write-Host "Press Ctrl+C when the three manual cases are complete."
    python -m http.server $Port --bind 127.0.0.1
}
finally {
    Pop-Location
}
