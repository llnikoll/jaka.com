# =====================================================================
# Lanza Jaka Bicicletería y la publica con una URL temporal de Cloudflare
#
#   .\tienda\lanzar.ps1              # servidor local + túnel + abre el navegador
#   .\tienda\lanzar.ps1 -NoAbrir     # sin abrir el navegador
#   .\tienda\lanzar.ps1 -Puerto 9000
#   .\tienda\lanzar.ps1 -Detener     # apaga servidor y túnel
#
# La URL cambia cada vez que se lanza. Para una dirección fija hace falta
# publicar en un hosting (ver tienda/README.md §3).
# =====================================================================
param(
  [int]$Puerto = 8080,
  [switch]$NoAbrir,
  [switch]$Detener
)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
$logTunel = Join-Path $PSScriptRoot 'logs\tunel.log'
$cloudflared = Join-Path $raiz 'tools\cloudflared.exe'

if ($Detener) {
  Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
  Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  Write-Host "Servidor y túnel detenidos." -ForegroundColor Green
  exit 0
}

function Buscar-Python {
  foreach ($c in @('python', 'python3', 'py')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) {
      & $c -c "import http.server" *> $null
      if ($LASTEXITCODE -eq 0) { return $c }
    }
  }
  $empaquetado = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
  if (Test-Path $empaquetado) { return $empaquetado }
  return $null
}

# 1) Servidor local (si ya está escuchando, se reutiliza)
$escuchando = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue
if (-not $escuchando) {
  $py = Buscar-Python
  if (-not $py) { Write-Host "No encontré Python. Instalalo o usá otro hosting." -ForegroundColor Red; exit 1 }
  Start-Process -FilePath $py `
    -ArgumentList @((Join-Path $PSScriptRoot 'servidor.py'), "$Puerto") `
    -WorkingDirectory $raiz -WindowStyle Hidden
  Start-Sleep -Seconds 2
  Write-Host "Servidor iniciado en el puerto $Puerto" -ForegroundColor DarkGray
} else {
  Write-Host "Servidor ya activo en el puerto $Puerto" -ForegroundColor DarkGray
}

if (-not (Test-Path $cloudflared)) {
  Write-Host "Falta tools\cloudflared.exe (túnel). Descargalo desde:" -ForegroundColor Yellow
  Write-Host "  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -ForegroundColor Yellow
  Write-Host "Mientras tanto podés usar la IP local para probar: http://127.0.0.1:$Puerto" -ForegroundColor Yellow
  exit 2
}

# 2) Reiniciar túnel
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
New-Item -ItemType Directory -Force -Path (Split-Path $logTunel) | Out-Null
Remove-Item $logTunel -Force -ErrorAction SilentlyContinue
Start-Process -FilePath $cloudflared `
  -ArgumentList @('tunnel', '--url', "http://127.0.0.1:$Puerto", '--no-autoupdate', '--logfile', $logTunel) `
  -WindowStyle Hidden

Write-Host "Conectando con Cloudflare..." -ForegroundColor DarkGray
$url = $null
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 800
  if (Test-Path $logTunel) {
    $m = Select-String -Path $logTunel -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($m) {
      $url = [regex]::Match($m.Line, 'https://[a-z0-9-]+\.trycloudflare\.com').Value
      break
    }
  }
}

if (-not $url) {
  Write-Host "No se pudo obtener la URL del túnel. Revisá $logTunel" -ForegroundColor Red
  exit 1
}

try { Set-Clipboard -Value $url } catch { }
Write-Host ""
Write-Host "  JAKA BICICLETERÍA ESTÁ EN LÍNEA" -ForegroundColor Green
Write-Host "  $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Local: http://127.0.0.1:$Puerto" -ForegroundColor DarkGray
Write-Host "  Log:   $logTunel" -ForegroundColor DarkGray
Write-Host "  (URL copiada al portapapeles)" -ForegroundColor DarkGray

if (-not $NoAbrir) { Start-Process $url }
