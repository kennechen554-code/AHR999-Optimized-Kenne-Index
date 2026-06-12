param(
  [string]$HostName = "127.0.0.1",
  [int]$ApiPort = 8001,
  [int]$WebPort = 5173,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$ApiUrl = "http://$HostName`:$ApiPort"
$WebUrl = "http://$HostName`:$WebPort"

function Resolve-Python {
  $candidates = @()

  $venvPython = Join-Path $BackendDir "venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    $candidates += $venvPython
  }

  $dotVenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
  if (Test-Path $dotVenvPython) {
    $candidates += $dotVenvPython
  }

  $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (Test-Path $codexPython) {
    $candidates += $codexPython
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    $candidates += $python.Source
  }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    $candidates += $py.Source
  }

  foreach ($candidate in $candidates) {
    & $candidate -c "import uvicorn, fastapi, sqlalchemy, pydantic, multipart" *> $null
    if ($LASTEXITCODE -eq 0) {
      return $candidate
    }
  }

  if ($candidates.Count -gt 0) {
    throw "Python was found, but backend dependencies are missing. Run: cd backend; python -m pip install -r requirements.txt"
  }

  throw "Python was not found. Install Python or create backend\.venv first."
}

function Test-TcpPort {
  param(
    [string]$HostName,
    [int]$Port
  )

  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $task = $client.ConnectAsync($HostName, $Port)
    if (-not $task.Wait(800)) {
      return $false
    }
    return $client.Connected
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Wait-Port {
  param(
    [string]$Name,
    [string]$HostName,
    [int]$Port,
    [int]$Seconds = 25
  )

  Write-Host "Waiting for $Name on $HostName`:$Port ..."
  for ($i = 0; $i -lt $Seconds; $i++) {
    if (Test-TcpPort -HostName $HostName -Port $Port) {
      Write-Host "$Name is ready." -ForegroundColor Green
      return $true
    }
    Start-Sleep -Seconds 1
  }

  Write-Host "$Name did not respond on $HostName`:$Port." -ForegroundColor Yellow
  return $false
}

function Assert-Path {
  param([string]$Path, [string]$Name)
  if (-not (Test-Path $Path)) {
    throw "Missing $Name at $Path"
  }
}

function Start-DevWindow {
  param(
    [string]$Title,
    [string]$WorkingDirectory,
    [string]$Command
  )

  $psCommand = @"
`$host.UI.RawUI.WindowTitle = @'
$Title
'@
Set-Location -LiteralPath @'
$WorkingDirectory
'@
try {
  Write-Host "Working directory: $WorkingDirectory" -ForegroundColor DarkGray
  Write-Host "Command: $Command" -ForegroundColor DarkGray
  $Command
  if (`$LASTEXITCODE -ne `$null -and `$LASTEXITCODE -ne 0) {
    Write-Host "Process exited with code `$LASTEXITCODE" -ForegroundColor Red
  }
} catch {
  Write-Host "Startup failed:" -ForegroundColor Red
  Write-Host `$_.Exception.Message -ForegroundColor Red
}
"@
  $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($psCommand))

  Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-EncodedCommand",
    $encodedCommand
  )
}

Assert-Path $BackendDir "backend directory"
Assert-Path $FrontendDir "frontend directory"

$PythonExe = Resolve-Python
$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $Npm) {
  throw "npm.cmd was not found. Install Node.js and make sure npm is available in PATH."
}

$BackendCommand = "& '$PythonExe' -m uvicorn app.main:app --host $HostName --port $ApiPort --reload"
$FrontendCommand = "& '$($Npm.Source)' run dev -- --host $HostName --port $WebPort"

Write-Host ""
Write-Host "Starting Kenne Index local dev environment..." -ForegroundColor Cyan
Write-Host "Backend: $ApiUrl"
Write-Host "Frontend: $WebUrl"
Write-Host ""

Start-DevWindow -Title "Kenne Index API :$ApiPort" -WorkingDirectory $BackendDir -Command $BackendCommand
Start-Sleep -Seconds 1
Start-DevWindow -Title "Kenne Index Web :$WebPort" -WorkingDirectory $FrontendDir -Command $FrontendCommand

$apiReady = Wait-Port -Name "Backend API" -HostName $HostName -Port $ApiPort -Seconds 25
$webReady = Wait-Port -Name "Frontend Web" -HostName $HostName -Port $WebPort -Seconds 25

if (-not $apiReady) {
  Write-Host "Backend is not running. Login/register and /api proxy calls will fail until API is ready." -ForegroundColor Red
  Write-Host "Check the 'Kenne Index API' window for the exact Python/FastAPI error." -ForegroundColor Yellow
}

if (-not $NoBrowser -and $webReady) {
  Start-Process $WebUrl
}

Write-Host "Two dev service windows have been opened. Close those windows to stop the services." -ForegroundColor Green
Write-Host "If ports are busy, try: powershell -ExecutionPolicy Bypass -File .\start-dev.ps1 -ApiPort 8010 -WebPort 5174" -ForegroundColor DarkGray
