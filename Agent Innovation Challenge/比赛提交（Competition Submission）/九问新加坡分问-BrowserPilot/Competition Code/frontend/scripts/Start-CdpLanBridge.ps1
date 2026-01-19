<# 
Start-CdpLanBridge.ps1
One-click on CLIENT:
- Launch Chrome with CDP on 127.0.0.1:9222
- Enable netsh portproxy: <ListenIP>:9222 -> 127.0.0.1:9222
- Allow inbound 9222 ONLY from server IP
#>

param(
  [string]$ServerIp = "172.20.10.3",
  [string]$ListenIp = "",          # 留空=自动检测本机默认出网IPv4
  [int]$Port = 9222,
  [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe",
  [string]$UserDataDir = "",
  [string]$ProfileDir = "Default",
  [string]$FirewallRuleName = "Allow CDP 9222 only from server",
  [switch]$KillChromeFirst
)

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# --- self-elevate if not admin ---
if (-not (Test-Admin)) {
  Write-Host "Not running as Administrator. Relaunching elevated..." -ForegroundColor Yellow
  $args = @(
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$PSCommandPath`"",
    "-ServerIp", $ServerIp,
    "-ListenIp", $ListenIp,
    "-Port", $Port,
    "-ChromePath", "`"$ChromePath`"",
    "-UserDataDir", "`"$UserDataDir`"",
    "-ProfileDir", $ProfileDir,
    "-FirewallRuleName", "`"$FirewallRuleName`""
  )
  if ($KillChromeFirst) { $args += "-KillChromeFirst" }
  Start-Process PowerShell -Verb RunAs -ArgumentList $args
  exit
}

# --- resolve listen ip (if empty) ---
if ([string]::IsNullOrWhiteSpace($ListenIp)) {
  try {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
      Sort-Object RouteMetric, InterfaceMetric |
      Select-Object -First 1
    $ip = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 |
      Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
      Select-Object -First 1
    $ListenIp = $ip.IPAddress
  } catch {
    $ip = Get-NetIPAddress -AddressFamily IPv4 |
      Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
      Select-Object -First 1
    $ListenIp = $ip.IPAddress
  }
}

if ([string]::IsNullOrWhiteSpace($ListenIp)) {
  Write-Host "ERROR: Cannot determine ListenIp. Please pass -ListenIp <your_client_ip>." -ForegroundColor Red
  exit 1
}

Write-Host "== Config ==" -ForegroundColor Cyan
Write-Host "ServerIp : $ServerIp"
Write-Host "ListenIp : $ListenIp"
Write-Host "Port     : $Port"
Write-Host ""

# --- paths ---
if ([string]::IsNullOrWhiteSpace($UserDataDir)) {
  $UserDataDir = Join-Path $env:LOCALAPPDATA "ChromeCDPProfile"
}

if (!(Test-Path $ChromePath)) {
  Write-Host "ERROR: Chrome not found: $ChromePath" -ForegroundColor Red
  exit 1
}

# --- optional kill chrome ---
if ($KillChromeFirst) {
  Write-Host "Killing existing Chrome..." -ForegroundColor Yellow
  taskkill /IM chrome.exe /F | Out-Null
  Start-Sleep -Seconds 1
}

# --- ensure iphlpsvc for portproxy ---
Write-Host "Ensuring iphlpsvc (IP Helper) is running..." -ForegroundColor Cyan
sc.exe config iphlpsvc start=auto | Out-Null
sc.exe start iphlpsvc | Out-Null

# --- setup portproxy ---
Write-Host ("Setting netsh portproxy: {0}:{1} -> 127.0.0.1:{1}" -f $ListenIp, $Port) -ForegroundColor Cyan

# delete old rule (ignore errors)
netsh interface portproxy delete v4tov4 listenaddress=$ListenIp listenport=$Port | Out-Null
# add rule
netsh interface portproxy add v4tov4 listenaddress=$ListenIp listenport=$Port connectaddress=127.0.0.1 connectport=$Port | Out-Null

# --- firewall: allow inbound ONLY from server ---
Write-Host ("Configuring firewall rule (allow ONLY from {0})..." -f $ServerIp) -ForegroundColor Cyan
# remove existing rule with same name (if any)
Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule `
  -DisplayName $FirewallRuleName `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort $Port `
  -RemoteAddress $ServerIp `
  -Profile Any | Out-Null

# --- launch chrome with local CDP (keeps plugin working) ---
Write-Host ("Launching Chrome with CDP on 127.0.0.1:{0} ..." -f $Port) -ForegroundColor Cyan
Start-Process -FilePath $ChromePath -ArgumentList @(
  "--remote-debugging-address=127.0.0.1",
  "--remote-debugging-port=$Port",
  "--user-data-dir=$UserDataDir",
  "--profile-directory=$ProfileDir"
)

Start-Sleep -Seconds 1

# --- status / self-tests ---
Write-Host "`n== Status ==" -ForegroundColor Green
Write-Host "[Portproxy rules]"
netsh interface portproxy show v4tov4

Write-Host "`n[Local listen check]"
Get-NetTCPConnection -LocalPort $Port | Format-Table LocalAddress,LocalPort,State,OwningProcess

Write-Host "`n[HTTP self-test]"
try {
  $null = Invoke-WebRequest -UseBasicParsing ("http://127.0.0.1:{0}/json/version" -f $Port) -TimeoutSec 3
  Write-Host ("OK: http://127.0.0.1:{0}/json/version" -f $Port)
} catch {
  Write-Host ("FAIL: http://127.0.0.1:{0}/json/version" -f $Port) -ForegroundColor Red
}

try {
  $null = Invoke-WebRequest -UseBasicParsing ("http://{0}:{1}/json/version" -f $ListenIp, $Port) -TimeoutSec 3
  Write-Host ("OK: http://{0}:{1}/json/version (via portproxy)" -f $ListenIp, $Port)
} catch {
  Write-Host ("FAIL: http://{0}:{1}/json/version (via portproxy)" -f $ListenIp, $Port) -ForegroundColor Red
}

Write-Host "`nDone."
Write-Host "On SERVER run:"
Write-Host ("  Test-NetConnection {0} -Port {1}" -f $ListenIp, $Port)
Write-Host ("  Invoke-WebRequest -UseBasicParsing http://{0}:{1}/json/version | Select -Expand Content" -f $ListenIp, $Port)
