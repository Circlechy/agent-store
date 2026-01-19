<# 
Stop-CdpLanBridge.ps1
One-click cleanup on CLIENT:
- Remove netsh portproxy rule: <ListenIP>:9222 -> 127.0.0.1:9222
- Remove firewall rule by DisplayName
- Optional: kill Chrome
#>

param(
  [string]$ListenIp = "", 
  [int]$Port = 9222,
  [string]$FirewallRuleName = "Allow CDP 9222 only from server",
  [switch]$KillChrome
)

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-ListenIp {
  try {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
      Sort-Object RouteMetric, InterfaceMetric |
      Select-Object -First 1
    $ip = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 |
      Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
      Select-Object -First 1
    return $ip.IPAddress
  } catch {
    $ip = Get-NetIPAddress -AddressFamily IPv4 |
      Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
      Select-Object -First 1
    return $ip.IPAddress
  }
}

# --- self-elevate if not admin ---
if (-not (Test-Admin)) {
  Write-Host "Not running as Administrator. Relaunching elevated..." -ForegroundColor Yellow
  $args = @(
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$PSCommandPath`"",
    "-ListenIp", $ListenIp,
    "-Port", $Port,
    "-FirewallRuleName", "`"$FirewallRuleName`""
  )
  if ($KillChrome) { $args += "-KillChrome" }
  Start-Process PowerShell -Verb RunAs -ArgumentList $args
  exit
}

# --- resolve ListenIp if empty ---
if ([string]::IsNullOrWhiteSpace($ListenIp)) {
  $ListenIp = Resolve-ListenIp
}

if ([string]::IsNullOrWhiteSpace($ListenIp)) {
  Write-Host "ERROR: Cannot determine ListenIp automatically. Please pass -ListenIp <your_client_ip>." -ForegroundColor Red
  exit 1
}

Write-Host "== Cleanup Config ==" -ForegroundColor Cyan
Write-Host "ListenIp         : $ListenIp"
Write-Host "Port             : $Port"
Write-Host "FirewallRuleName : $FirewallRuleName"
Write-Host ""

# --- remove portproxy rule ---
Write-Host ("Removing portproxy {0}:{1} ..." -f $ListenIp, $Port) -ForegroundColor Cyan
netsh interface portproxy delete v4tov4 listenaddress=$ListenIp listenport=$Port | Out-Null

# --- remove firewall rule ---
Write-Host ("Removing firewall rule '{0}' ..." -f $FirewallRuleName) -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue

# --- optional kill chrome ---
if ($KillChrome) {
  Write-Host "Killing Chrome..." -ForegroundColor Yellow
  taskkill /IM chrome.exe /F | Out-Null
}

# --- show remaining rules for sanity ---
Write-Host "`n== Remaining Portproxy Rules ==" -ForegroundColor Green
netsh interface portproxy show v4tov4

Write-Host "`nDone."
