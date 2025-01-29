Param()

Write-Host "Installing accessclient:// protocol..."

# Resolve the script directory
$scriptDir   = Split-Path $MyInvocation.MyCommand.Definition -Parent
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
$forkblPath  = Join-Path $projectRoot "ForkBL.exe"

if (-not (Test-Path $forkblPath)) {
    Write-Error "ForkBL.exe not found at $forkblPath."
    exit 1
}

# Add registry entries
reg add "HKCR\accessclient" /f /ve /d "URL:AccessClient Protocol" | Out-Null
reg add "HKCR\accessclient" /f /v "URL Protocol" /d "" | Out-Null
reg add "HKCR\accessclient\shell" /f | Out-Null
reg add "HKCR\accessclient\shell\open" /f | Out-Null

# Create the command string
$escapedPath = $forkblPath.Replace("\","\\")
$cmdValue    = "`"$escapedPath`" `"%1`""

reg add "HKCR\accessclient\shell\open\command" /f /ve /d $cmdValue | Out-Null

Write-Host "Installation complete."
