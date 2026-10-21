# =====================================================================
# Actualiza el catálogo de la tienda desde ciclovia.com.py
#
#   .\actualizar.ps1              # lee el sitio, regenera y publica si hay config
#   .\actualizar.ps1 -SinRed      # regenera usando la caché local (0 requests)
#   .\actualizar.ps1 -SinPublicar # solo actualiza los archivos locales
#   .\actualizar.ps1 -Python "C:\ruta\python.exe"
#
# Lo llama la tarea programada (ver programar.ps1). Deja un log por corrida en
# tienda\logs\ y el detalle de cambios en tienda\data\ultimos_cambios.json.
# =====================================================================
param(
  [switch]$SinRed,
  [switch]$SinPublicar,
  [switch]$AbrirReporte,
  [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
try { $script:OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$raiz = Split-Path $PSScriptRoot -Parent
$carpetaLogs = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $carpetaLogs | Out-Null
$log = Join-Path $carpetaLogs ("actualizar-{0}.log" -f (Get-Date -Format 'yyyy-MM-dd_HHmmss'))
$transcripcion = $false

Push-Location $raiz

function Ejecutar {
  param([string]$Exe, [string[]]$Argumentos)
  $previo = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    & $Exe @Argumentos | Out-Host
    $codigo = $LASTEXITCODE
  }
  finally { $ErrorActionPreference = $previo }
  return $codigo
}

function Tiene-Lxml {
  param([string]$Exe)
  # Se ejecuta con .NET para que un Python sin lxml no ensucie el log con errores
  try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $psi.Arguments = '-c "import lxml"'
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proceso = [System.Diagnostics.Process]::Start($psi)
    $proceso.WaitForExit(20000) | Out-Null
    $codigo = $proceso.ExitCode
    $proceso.Dispose()
    return ($codigo -eq 0)
  }
  catch { return $false }
}

function Buscar-Python {
  param([string]$Preferido)
  $candidatos = @()
  if ($Preferido) { $candidatos += $Preferido }
  $candidatos += @('python', 'python3', 'py')

  $empaquetado = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
  if (Test-Path $empaquetado) { $candidatos += $empaquetado }

  foreach ($candidate in $candidatos) {
    $exe = $candidate
    if (-not (Test-Path $candidate)) {
      $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
      if (-not $cmd) { continue }
      $exe = $cmd.Source
    }
    if (Tiene-Lxml -Exe $exe) { return $exe }
  }
  return $null
}

try {
  try { Start-Transcript -Path $log -Append | Out-Null; $transcripcion = $true } catch { }
  Write-Host "== Actualizacion de catalogo: $(Get-Date -Format 'yyyy-MM-dd HH:mm') ==" -ForegroundColor Cyan

  $py = Buscar-Python -Preferido $Python
  if (-not $py) {
    throw "No encontré un Python con 'lxml'. Instalalo con: python -m pip install lxml y volvé a intentar (o pasá la ruta con -Python)."
  }
  Write-Host "Python: $py" -ForegroundColor DarkGray

  Write-Host "`n== 1/3 Leyendo el catálogo de ciclovia.com.py ==" -ForegroundColor Cyan
  $argumentos = @('poc\scraper_ciclovia.py', '--modo', 'todo', '--incluir-raices')
  if ($SinRed) {
    $argumentos += '--sin-red'
  }
  else {
    # --force: ignora la caché y vuelve a pedir el catálogo (sin esto no habría precios nuevos)
    $argumentos += '--force'
  }
  $codigo = Ejecutar -Exe $py -Argumentos (@('-X', 'utf8') + $argumentos)
  if ($codigo -ne 0) { throw "El scraper terminó con código $codigo" }

  Write-Host "`n== 2/3 Regenerando el catálogo de la tienda ==" -ForegroundColor Cyan
  $codigo = Ejecutar -Exe $py -Argumentos @('-X', 'utf8', 'tienda\build_catalogo.py')
  if ($codigo -ne 0) { throw "build_catalogo.py terminó con código $codigo" }

  Write-Host "`n== 3/3 Publicando en el hosting ==" -ForegroundColor Cyan
  $publicar = Join-Path $PSScriptRoot 'publicar.ps1'
  if ($SinPublicar) {
    Write-Host "Publicación omitida (-SinPublicar)." -ForegroundColor Yellow
  }
  elseif (-not (Test-Path (Join-Path $PSScriptRoot 'publicar.config.ps1'))) {
    Write-Host "Sin publicar.config.ps1: los archivos quedaron listos para subir a mano." -ForegroundColor Yellow
    Write-Host "Ver tienda\README.md §4 para configurar la subida automática." -ForegroundColor Yellow
  }
  else {
    $codigo = Ejecutar -Exe 'powershell.exe' -Argumentos @(
      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $publicar
    )
    if ($codigo -ne 0) { throw "publicar.ps1 terminó con código $codigo" }
  }

  Write-Host "`nListo: $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Green
  Write-Host "Log: $log"
  Write-Host "Detalle de cambios: tienda\data\ultimos_cambios.json"

  if ($AbrirReporte) {
    $reporte = Join-Path $raiz 'tienda\data\ultimos_cambios.json'
    if (Test-Path $reporte) { Start-Process notepad.exe $reporte }
  }

  # Mantener solo los últimos 30 logs
  Get-ChildItem $carpetaLogs -Filter 'actualizar-*.log' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 |
    Remove-Item -Force -ErrorAction SilentlyContinue
}
catch {
  Write-Host "`nERROR: $_" -ForegroundColor Red
  if ($transcripcion) { try { Stop-Transcript | Out-Null } catch { } }
  Pop-Location
  exit 1
}
finally {
  if ($transcripcion) { try { Stop-Transcript | Out-Null } catch { } }
  Pop-Location
}
