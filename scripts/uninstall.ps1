Param()

Write-Host "Uninstalling accessclient:// protocol..."
reg delete "HKCR\accessclient" /f | Out-Null
Write-Host "Uninstallation complete."
