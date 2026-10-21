# =====================================================================
# Publica los datos del catálogo en el hosting.
#
# Requiere un archivo de configuración (no incluido por seguridad):
#   tienda\publicar.config.ps1
#
# Hay dos modos: FTP (hosting compartido/cPanel) y git (Netlify/Vercel/GitHub Pages).
# Copiá publicar.config.ejemplo.ps1 a publicar.config.ps1 y completá tus datos.
#
# Sube: data\indice.json, data\indice.js y todos los data\v\*.json
# (el catálogo completo catalogo.json/.js queda solo como respaldo local)
# =====================================================================
param(
  [switch]$SoloVerificar
)

$ErrorActionPreference = 'Stop'
$config = Join-Path $PSScriptRoot 'publicar.config.ps1'

if (-not (Test-Path $config)) {
  Write-Host "Sin configuracion de publicacion (falta tienda\publicar.config.ps1)." -ForegroundColor Yellow
  Write-Host "Los archivos actualizados quedaron en tienda\data\: subilos a mano al hosting." -ForegroundColor Yellow
  exit 2
}

. $config
if (-not $Publicacion -or -not $Publicacion.Modo) {
  Write-Host "publicar.config.ps1 no define `$Publicacion.Modo (ftp | git)." -ForegroundColor Red
  exit 1
}

$data = Join-Path $PSScriptRoot 'data'
$archivos = @(
  @{ Local = (Join-Path $data 'indice.json'); Remoto = 'data/indice.json' },
  @{ Local = (Join-Path $data 'indice.js');   Remoto = 'data/indice.js' }
)
Get-ChildItem (Join-Path $data 'v') -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object {
  $archivos += @{ Local = $_.FullName; Remoto = "data/v/$($_.Name)" }
}

function Subir-Ftp {
  param([string]$ArchivoLocal, [string]$RutaRemota, [hashtable]$Config)
  $carpeta = if ($Config.CarpetaRemota) { $Config.CarpetaRemota.TrimEnd('/') + '/' } else { '/' }
  $uri = "ftp://$($Config.Host)$carpeta$RutaRemota"
  $req = [System.Net.FtpWebRequest]::Create($uri)
  $req.Method = [System.Net.WebRequestMethods+Ftp]::UploadFile
  $req.Credentials = New-Object System.Net.NetworkCredential($Config.Usuario, $Config.Clave)
  $req.UseBinary = $true
  $req.UsePassive = $true
  $req.Timeout = 60000
  $bytes = [System.IO.File]::ReadAllBytes($ArchivoLocal)
  $req.ContentLength = $bytes.Length
  $stream = $req.GetRequestStream()
  try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Close() }
  $resp = $req.GetResponse()
  $resp.Close()
}

function Asegurar-CarpetaFtp {
  param([string]$CarpetaRelativa, [hashtable]$Config)
  $carpeta = if ($Config.CarpetaRemota) { $Config.CarpetaRemota.TrimEnd('/') + '/' } else { '/' }
  $uri = "ftp://$($Config.Host)$carpeta$CarpetaRelativa"
  try {
    $req = [System.Net.FtpWebRequest]::Create($uri)
    $req.Method = [System.Net.WebRequestMethods+Ftp]::MakeDirectory
    $req.Credentials = New-Object System.Net.NetworkCredential($Config.Usuario, $Config.Clave)
    $req.UsePassive = $true
    $req.Timeout = 60000
    $req.GetResponse().Close()
    Write-Host "Carpeta creada: $CarpetaRelativa" -ForegroundColor DarkGray
  }
  catch { }  # ya existe: seguimos
}

try {
  switch ($Publicacion.Modo.ToLower()) {
    'ftp' {
      if (-not $SoloVerificar) { Asegurar-CarpetaFtp -CarpetaRelativa 'data/v' -Config $Publicacion }
      foreach ($a in $archivos) {
        if (-not (Test-Path $a.Local)) { throw "No existe $($a.Local)" }
        if ($SoloVerificar) {
          Write-Host "[verificacion] subiria $($a.Remoto)" -ForegroundColor DarkGray
        } else {
          Subir-Ftp -ArchivoLocal $a.Local -RutaRemota $a.Remoto -Config $Publicacion
          Write-Host "Subido: $($a.Remoto)" -ForegroundColor Green
        }
      }
    }
    'git' {
      # Sin preguntas interactivas: usa la credencial guardada de Windows y
      # falla con un error claro si venció (importante para la tarea programada).
      $env:GIT_TERMINAL_PROMPT = '0'
      $env:GCM_INTERACTIVE = 'never'
      Push-Location (Split-Path $PSScriptRoot -Parent)
      try {
        $fecha = Get-Date -Format 'yyyy-MM-dd HH:mm'
        & git add 'tienda/data' | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "git add fallo" }
        $cambios = (& git status --porcelain -- 'tienda/data') -join "`n"
        if (-not $cambios) {
          Write-Host "Sin cambios para publicar." -ForegroundColor DarkGray
        } else {
          & git commit -m "Catalogo actualizado $fecha" | Out-Host
          if ($LASTEXITCODE -ne 0) { throw "git commit fallo" }
          if (-not $SoloVerificar) {
            & git push | Out-Host
            if ($LASTEXITCODE -ne 0) {
              throw "git push fallo. Abrí una consola y corré 'git push' una vez para renovar la credencial de GitHub."
            }
            Write-Host "Publicado por git push. GitHub Pages se actualiza en 1-2 minutos." -ForegroundColor Green
          }
        }
      }
      finally { Pop-Location }
    }
    default {
      throw "Modo de publicacion desconocido: $($Publicacion.Modo). Usá 'ftp' o 'git'."
    }
  }
}
catch {
  Write-Host "ERROR al publicar: $_" -ForegroundColor Red
  exit 1
}
