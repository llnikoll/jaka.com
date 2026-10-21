# =====================================================================
# Programa la actualización automática del catálogo (Windows)
#
#   .\programar.ps1                               # semanal, lunes 06:00
#   .\programar.ps1 -Diario -Hora 05:30           # todos los días 05:30
#   .\programar.ps1 -CadaHoras 6                  # cada 6 horas
#   .\programar.ps1 -EjecutarAhora                # dispara una corrida ya
#   .\programar.ps1 -Quitar                       # borra la tarea
#   .\programar.ps1 -Estado                       # muestra la próxima corrida
#
# La tarea corre actualizar.ps1 (lee Ciclovía, regenera el catálogo y publica
# si tienda\publicar.config.ps1 está configurado).
# =====================================================================
param(
  [switch]$Diario,
  [int]$CadaHoras = 0,
  [ValidateSet('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')]
  [string]$Dia = 'Monday',
  [string]$Hora = '06:00',
  [switch]$Quitar,
  [switch]$Estado,
  [switch]$EjecutarAhora,
  [string]$NombreTarea = 'BiciTienda - actualizar catalogo'
)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
$script = Join-Path $PSScriptRoot 'actualizar.ps1'

function Mostrar-Estado {
  try {
    $info = Get-ScheduledTaskInfo -TaskName $NombreTarea -ErrorAction Stop
    $tarea = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction Stop
    $trigger = $tarea.Triggers | Select-Object -First 1
    Write-Host "Tarea: $NombreTarea" -ForegroundColor Cyan
    Write-Host "  Estado:        $($tarea.State)"
    Write-Host "  Próxima:       $($info.NextRunTime)"
    Write-Host "  Última:        $($info.LastRunTime)  (resultado: $($info.LastTaskResult))"
    Write-Host "  Repetición:    $($trigger.CimClass.CimClassName) $($trigger.StartBoundary)"
  }
  catch {
    Write-Host "La tarea '$NombreTarea' no existe todavía." -ForegroundColor Yellow
    Write-Host "Crearla con: .\tienda\programar.ps1"
  }
}

if ($Estado) { Mostrar-Estado; exit 0 }

if ($Quitar) {
  try {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false -ErrorAction Stop
    Write-Host "Tarea eliminada: $NombreTarea" -ForegroundColor Green
  }
  catch {
    & schtasks.exe /Delete /TN $NombreTarea /F 2>$null | Out-Null
    Write-Host "Tarea eliminada (o no existía): $NombreTarea" -ForegroundColor Green
  }
  exit 0
}

# ---------------------------------------------------------------------
# Trigger según la frecuencia pedida
# ---------------------------------------------------------------------
$horaDate = [datetime]::Today.Add([timespan]::Parse($Hora))

if ($CadaHoras -gt 0) {
  $inicio = (Get-Date).AddMinutes(2)
  $trigger = New-ScheduledTaskTrigger -Once -At $inicio `
    -RepetitionInterval (New-TimeSpan -Hours $CadaHoras) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
  $descripcionFrecuencia = "cada $CadaHoras horas"
}
elseif ($Diario) {
  $trigger = New-ScheduledTaskTrigger -Daily -At $horaDate
  $descripcionFrecuencia = "todos los días a las $Hora"
}
else {
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $horaDate
  $descripcionFrecuencia = "todos los $Dia a las $Hora"
}

$accion = New-ScheduledTaskAction `
  -Execute 'powershell.exe' `
  -Argument "-NoProfile -NoLogo -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
  -WorkingDirectory $raiz

$ajustes = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$registrada = $false
try {
  Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $trigger `
    -Settings $ajustes -Description 'Actualiza el catálogo de la tienda desde ciclovia.com.py' `
    -Force | Out-Null
  $registrada = $true
}
catch {
  Write-Host "Register-ScheduledTask falló ($($_.Exception.Message.Trim())). Probando con schtasks..." -ForegroundColor Yellow
  $tr = "powershell.exe -NoProfile -NoLogo -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
  if ($CadaHoras -gt 0) {
    & schtasks.exe /Create /TN $NombreTarea /SC HOURLY /MO $CadaHoras /TR $tr /F | Out-Null
  }
  elseif ($Diario) {
    & schtasks.exe /Create /TN $NombreTarea /SC DAILY /ST $Hora /TR $tr /F | Out-Null
  }
  else {
    $dias = @{ Monday = 'MON'; Tuesday = 'TUE'; Wednesday = 'WED'; Thursday = 'THU'; Friday = 'FRI'; Saturday = 'SAT'; Sunday = 'SUN' }
    & schtasks.exe /Create /TN $NombreTarea /SC WEEKLY /D $dias[$Dia] /ST $Hora /TR $tr /F | Out-Null
  }
  if ($LASTEXITCODE -eq 0) { $registrada = $true }
}

if (-not $registrada) {
  Write-Host "No se pudo crear la tarea. Probá abrir PowerShell como administrador y volver a correr." -ForegroundColor Red
  exit 1
}

Write-Host "Tarea programada: $NombreTarea" -ForegroundColor Green
Write-Host "  Frecuencia: $descripcionFrecuencia"
Write-Host "  Ejecuta:    $script"
Write-Host "  Logs:       $(Join-Path $PSScriptRoot 'logs')"
if (-not (Test-Path (Join-Path $PSScriptRoot 'publicar.config.ps1'))) {
  Write-Host "  Aviso:      sin publicar.config.ps1 la tarea actualiza los archivos pero no los sube al hosting." -ForegroundColor Yellow
}
Mostrar-Estado

if ($EjecutarAhora) {
  Write-Host "`nEjecutando una corrida de prueba..." -ForegroundColor Cyan
  try { Start-ScheduledTask -TaskName $NombreTarea -ErrorAction Stop }
  catch { & schtasks.exe /Run /TN $NombreTarea | Out-Null }
  Write-Host "Lanzada. Tarda 3-5 minutos; revisá los logs en tienda\logs\." -ForegroundColor Green
}
