# =====================================================================
# Configuración de publicación (EJEMPLO)
#
# 1) Copiá este archivo como  tienda\publicar.config.ps1
# 2) Elegí UN modo y completá tus datos
# 3) Probá sin subir nada:  .\tienda\publicar.ps1 -SoloVerificar
#
# Ojo: publicar.config.ps1 tiene contraseñas. No lo compartas ni lo subas a git.
# =====================================================================

# ---------- MODO FTP (hosting compartido, cPanel, Plesk) ----------
# $Publicacion = @{
#   Modo          = 'ftp'
#   Host          = 'ftp.tudominio.com.py'    # servidor FTP
#   Usuario       = 'usuario'
#   Clave         = 'contraseña'
#   CarpetaRemota = '/public_html/'           # carpeta donde está index.html
# }

# ---------- MODO GIT (Netlify, Vercel o GitHub Pages conectados al repo) ----------
# $Publicacion = @{
#   Modo = 'git'
# }
