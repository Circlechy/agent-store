# -----------------------------
# Start-ChromeCDP-Tunnel.ps1
# One-click: launch Chrome CDP + SSH reverse tunnel
# Run on CLIENT machine
# -----------------------------

# ====== EDIT THESE ======
$ServerUser = "27897"
$ServerHost = "172.20.10.3"   
$RemotePort = 9222                # exposed on server side
$LocalPort  = 9222                # Chrome CDP port on client (local)
$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$UserDataDir = Join-Path $env:LOCALAPPDATA "ChromeCDPProfile"
$ProfileDir = "Default"
# =======================

# Basic checks
if (!(Test-Path $ChromePath)) {
  Write-Host "Chrome not found at: $ChromePath" -ForegroundColor Red
  exit 1
}

Write-Host "[1/2] Launching Chrome with CDP on 127.0.0.1:$LocalPort ..."
Start-Process -FilePath $ChromePath -ArgumentList @(
  "--remote-debugging-address=127.0.0.1",
  "--remote-debugging-port=$LocalPort",
  "--user-data-dir=$UserDataDir",
  "--profile-directory=$ProfileDir"
)

Start-Sleep -Seconds 1

Write-Host "[2/2] Starting SSH reverse tunnel: server:$RemotePort -> client:127.0.0.1:$LocalPort"
Write-Host "Press Ctrl+C to stop the tunnel (Chrome will remain open)."

# Build SSH args
$sshArgs = @(
  "-N",
  "-R", "$RemotePort`:127.0.0.1`:$LocalPort",
  "-o", "ExitOnForwardFailure=yes",
  "-o", "ServerAliveInterval=30",
  "-o", "ServerAliveCountMax=3",
  "$ServerUser@$ServerHost"
)

# Run SSH in foreground (keeps tunnel alive)
ssh @sshArgs
