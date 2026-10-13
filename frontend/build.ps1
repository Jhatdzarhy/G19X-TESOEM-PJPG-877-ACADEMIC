# =============================================================================
# build.ps1 - Compila y despliega la aplicacion web en Tomcat.
# Dashboard Ejecutivo de Supply Chain (PDR seccion 4; CC-20 y CC-21).
#
# Sin Maven ni bibliotecas externas: compila con el javac del JDK 21 (JAVA_HOME,
# no el del PATH) contra servlet-api.jar de Tomcat, y copia el resultado a
# %CATALINA_HOME%\webapps\supplychain. Tomcat recarga la aplicacion solo.
#
# Uso, desde la raiz del proyecto:
#   .\frontend\build.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'

$frontend = $PSScriptRoot
$fuentes  = Join-Path $frontend 'src'
$webapp   = Join-Path $frontend 'webapp'
$salida   = Join-Path $frontend 'build\supplychain'

# --- Herramientas -------------------------------------------------------------
if (-not $env:JAVA_HOME)     { throw 'JAVA_HOME no esta definido.' }
if (-not $env:CATALINA_HOME) { throw 'CATALINA_HOME no esta definido.' }

$javac      = Join-Path $env:JAVA_HOME 'bin\javac.exe'
$servletApi = Join-Path $env:CATALINA_HOME 'lib\servlet-api.jar'
$webapps    = Join-Path $env:CATALINA_HOME 'webapps'
$destino    = Join-Path $webapps 'supplychain'

foreach ($ruta in @($javac, $servletApi, $webapps)) {
    if (-not (Test-Path $ruta)) { throw "No existe: $ruta" }
}

# --- Copia limpia de webapp ---------------------------------------------------
if (Test-Path $salida) { Remove-Item $salida -Recurse -Force }
New-Item -ItemType Directory -Path $salida | Out-Null
Copy-Item -Path (Join-Path $webapp '*') -Destination $salida -Recurse

# --- Compilacion --------------------------------------------------------------
$clases = Join-Path $salida 'WEB-INF\classes'
New-Item -ItemType Directory -Path $clases -Force | Out-Null
$archivosJava = Get-ChildItem -Path $fuentes -Recurse -Filter '*.java' | ForEach-Object { $_.FullName }
if (-not $archivosJava) { throw "No hay archivos .java en $fuentes" }

Write-Host "Compilando $($archivosJava.Count) clases con $javac"
& $javac --release 21 -encoding UTF-8 -Xlint:all -Xlint:-serial -cp $servletApi -d $clases $archivosJava
if ($LASTEXITCODE -ne 0) { throw 'La compilacion fallo; no se desplego nada.' }

# --- Despliegue ---------------------------------------------------------------
# robocopy /MIR deja el destino identico a build\supplychain (borra lo que sobre).
# El destino se valida para que nunca apunte fuera de webapps\supplychain.
if ((Split-Path $destino -Leaf) -ne 'supplychain' -or (Split-Path $destino -Parent) -ne $webapps) {
    throw "Destino inesperado: $destino"
}
robocopy $salida $destino /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy fallo con codigo $LASTEXITCODE" }

Write-Host "Desplegado en $destino"
Write-Host 'Abre http://localhost:8080/supplychain/ (Tomcat recarga la aplicacion en unos segundos).'
exit 0