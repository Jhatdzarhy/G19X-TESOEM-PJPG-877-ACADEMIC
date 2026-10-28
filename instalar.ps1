<#
.SYNOPSIS
    Instalacion en un paso del Dashboard Ejecutivo de Supply Chain (CC-28).

.DESCRIPTION
    Hace en orden lo que la seccion 5 del manual tecnico hace a mano:
      1. Requisitos: Python 3.13, psql, y JDK 21 y Tomcat 10.1 si se instala la capa web.
      2. Entorno virtual backend\.venv con requirements-dev.txt.
      3. backend\.env a partir de backend\.env.example, solo si no existe.
      4. Base de datos nueva y scripts de db\final en orden numerico (01 a 07).
      5. Datos y modelos con python -m admin.cargar_todo, con los datos de respaldo validados
         (CC-27); con -Descargar los trae de las APIs.
      6. Token interno y capa web (admin.token_interno y frontend\build.ps1), con CATALINA_HOME.
      7. Cuentas gerencia, operaciones y admin; la contrasena se escribe oculta.
      8. Verificacion: pytest, 99_verificar_extensiones.sql, validar_kpis.sql y huella de datos.

    La contrasena de PostgreSQL se pide oculta y solo vive en este proceso; si se crea
    backend\.env, se guarda ahi (el archivo no se versiona). Nunca toca supply_chain_mvp.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\instalar.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\instalar.ps1 -BaseDatos supply_chain_prueba -SinWeb
#>
[CmdletBinding()]
param(
    [string]$BaseDatos = 'supply_chain_final',
    [string]$ServidorPg = 'localhost',
    [int]$PuertoPg = 5432,
    [string]$UsuarioPg = 'postgres',
    [string]$TomcatHome = $env:CATALINA_HOME,
    [switch]$Descargar,
    [switch]$SinWeb,
    [switch]$Reinstalar
)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$backend = Join-Path $raiz 'backend'
$dbFinal = Join-Path $raiz 'db\final'
$huellaValidada = 'efe7c9c479757f45d1283033b0d126db4a73a0bb3649b55f00d5ce30de2185ad'   # CC-22
$cuentas = @(
    @{ Usuario = 'gerencia';    Nombre = 'Gerencia general'; Rol = 'EJECUTIVO' },
    @{ Usuario = 'operaciones'; Nombre = 'Operaciones';      Rol = 'OPERACIONES' },
    @{ Usuario = 'admin';       Nombre = 'Administrador';    Rol = 'ADMIN' }
)

function Paso([string]$texto) { Write-Host ''; Write-Host "== $texto" -ForegroundColor Cyan }
function Detener([string]$texto) { throw "INSTALACION DETENIDA: $texto" }

function Buscar-Psql {
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidatos = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
        Sort-Object { [int]($_.Directory.Parent.Name -replace '\D', '') } -Descending
    if ($candidatos) { return $candidatos[0].FullName }
    Detener 'No se encontro psql. Instala PostgreSQL 18 o agrega su carpeta bin al PATH.'
}

function Buscar-Python {
    $ErrorActionPreference = 'Continue'      # PowerShell 5.1 convierte el stderr de un programa en error
    foreach ($opcion in @(@('py', '-3.13'), @('python3.13'), @('python'))) {
        $exe = $opcion[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $argumentos = @($opcion | Select-Object -Skip 1)
        $version = & $exe @argumentos -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -eq '3.13') { return , $opcion }
    }
    Detener 'No se encontro Python 3.13. Instala Python 3.13 (con el lanzador py) y vuelve a ejecutar.'
}

function Invocar-Psql([string]$base, [string[]]$argumentos) {
    $ErrorActionPreference = 'Continue'      # los NOTICE de psql salen por stderr
    $salida = & $script:psql -h $ServidorPg -p $PuertoPg -U $UsuarioPg -d $base -X -v ON_ERROR_STOP=1 @argumentos 2>&1
    $codigo = $LASTEXITCODE
    return @{ Codigo = $codigo; Salida = ($salida | ForEach-Object { "$_" }) }
}

function Consulta([string]$base, [string]$sql) {
    $r = Invocar-Psql $base @('-Atc', $sql)
    if ($r.Codigo -ne 0) { Detener ("psql fallo: " + ($r.Salida -join ' ')) }
    return ($r.Salida | Where-Object { $_ -notmatch '^(NOTICE|AVISO)' }) -join "`n"
}

function Python-Venv([string[]]$argumentos) {
    # La salida va a la consola (el usuario la ve y puede escribir contrasenas ocultas);
    # quien llama revisa $LASTEXITCODE.
    Push-Location $backend
    try { & $script:pyVenv @argumentos } finally { Pop-Location }
}

$variablesProceso = @('PGPASSWORD', 'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'CATALINA_HOME')
$previas = @{}
foreach ($v in $variablesProceso) { $previas[$v] = [Environment]::GetEnvironmentVariable($v, 'Process') }

try {
    if ($BaseDatos -notmatch '^[a-z_][a-z0-9_]{0,62}$') { Detener "Nombre de base invalido: $BaseDatos (minusculas, numeros y guion bajo)." }
    if ($BaseDatos -in @('supply_chain_mvp', 'postgres', 'template0', 'template1')) {
        Detener "La base $BaseDatos no se toca: supply_chain_mvp es el MVP congelado y las otras son del sistema."
    }

    # -------------------------------------------------------------- 1. requisitos
    Paso '1/8 Requisitos'
    $script:psql = Buscar-Psql
    Write-Host "psql: $script:psql"
    $python = Buscar-Python
    Write-Host ("Python 3.13: " + ($python -join ' '))
    if (-not $SinWeb) {
        if (-not $TomcatHome -or -not (Test-Path (Join-Path $TomcatHome 'bin\startup.bat'))) {
            Detener 'No se encontro Tomcat. Define CATALINA_HOME o usa -TomcatHome <carpeta>, o -SinWeb para instalar solo el motor y la base.'
        }
        if (-not $env:JAVA_HOME -or -not (Test-Path (Join-Path $env:JAVA_HOME 'bin\javac.exe'))) {
            Detener 'JAVA_HOME no apunta a un JDK 21. Configuralo o usa -SinWeb.'
        }
        $env:CATALINA_HOME = (Resolve-Path $TomcatHome).Path
        Write-Host "Tomcat: $env:CATALINA_HOME"
    }

    # -------------------------------------------------------------- 2. entorno de Python
    Paso '2/8 Entorno virtual backend\.venv'
    $venv = Join-Path $backend '.venv'
    if (-not (Test-Path $venv)) {
        $argumentos = @($python | Select-Object -Skip 1) + @('-m', 'venv', $venv)
        & $python[0] @argumentos
        if ($LASTEXITCODE -ne 0) { Detener 'No se pudo crear el entorno virtual.' }
    }
    $script:pyVenv = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path $script:pyVenv)) { $script:pyVenv = Join-Path $venv 'bin/python' }
    Python-Venv @('-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-r', 'requirements-dev.txt')
    if ($LASTEXITCODE -ne 0) { Detener 'pip no pudo instalar requirements-dev.txt.' }
    Write-Host 'Dependencias instaladas (requirements-dev.txt).'

    # -------------------------------------------------------------- 3. backend\.env
    Paso '3/8 Configuracion y contrasena de PostgreSQL'
    $segura = Read-Host "Contrasena del usuario $UsuarioPg de PostgreSQL" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($segura)
    try { $contrasena = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if (-not $contrasena) { Detener 'La contrasena de PostgreSQL no puede quedar vacia.' }
    $env:PGPASSWORD = $contrasena
    # La base destino y las credenciales van en el entorno de este proceso: tienen prioridad
    # sobre backend\.env, asi que instalar en una base de prueba no modifica la configuracion real.
    $env:DB_HOST = $ServidorPg; $env:DB_PORT = "$PuertoPg"; $env:DB_NAME = $BaseDatos
    $env:DB_USER = $UsuarioPg; $env:DB_PASSWORD = $contrasena

    $rutaEnv = Join-Path $backend '.env'
    if (Test-Path $rutaEnv) {
        Write-Host 'backend\.env ya existe; no se modifica (las llaves y el token se conservan).'
    } else {
        if ($contrasena -match "['\s#]" -or $contrasena -match '[^\x21-\x7E]') {
            Detener 'Para escribirla en backend\.env, la contrasena debe ser ASCII sin espacios, # ni comillas simples.'
        }
        $texto = [IO.File]::ReadAllText((Join-Path $backend '.env.example'))
        $valores = @{ DB_HOST = $ServidorPg; DB_PORT = "$PuertoPg"; DB_NAME = $BaseDatos; DB_USER = $UsuarioPg; DB_PASSWORD = "'$contrasena'" }
        foreach ($clave in $valores.Keys) {
            $texto = [regex]::Replace($texto, "(?m)^$clave=.*$", { param($m) "$clave=" + $valores[$clave] }.GetNewClosure())
        }
        [IO.File]::WriteAllText($rutaEnv, $texto, (New-Object Text.UTF8Encoding($false)))
        Write-Host 'backend\.env creado desde .env.example. BANXICO_TOKEN y ZAI_API_KEY quedan vacios (opcionales, CC-27).'
    }

    # -------------------------------------------------------------- 4. base de datos
    Paso "4/8 Base de datos $BaseDatos"
    if ((Consulta 'postgres' 'SELECT 1') -ne '1') { Detener 'No hay conexion con PostgreSQL.' }
    $existe = (Consulta 'postgres' "SELECT COUNT(*) FROM pg_database WHERE datname = '$BaseDatos'") -eq '1'
    if ($existe) {
        if (-not $Reinstalar) {
            Detener "La base $BaseDatos ya existe. Para borrarla y volver a instalar usa -Reinstalar; para instalar en otra base usa -BaseDatos <nombre>."
        }
        Write-Host "Se borrara la base $BaseDatos con todos sus datos, usuarios e historial de decisiones." -ForegroundColor Yellow
        if ((Read-Host "Escribe $BaseDatos para confirmar") -cne $BaseDatos) { Detener 'Confirmacion incorrecta; no se borro nada.' }
        Consulta 'postgres' "DROP DATABASE `"$BaseDatos`" WITH (FORCE)" | Out-Null
        Write-Host "Base $BaseDatos borrada."
    }
    Consulta 'postgres' "CREATE DATABASE `"$BaseDatos`" ENCODING 'UTF8'" | Out-Null
    Write-Host "Base $BaseDatos creada."
    $scripts = Get-ChildItem $dbFinal -Filter '0*.sql' | Sort-Object Name
    $prefijos = $scripts | ForEach-Object { $_.Name.Substring(0, 2) }
    if (($prefijos | Select-Object -Unique).Count -ne $prefijos.Count) { Detener 'Hay scripts de db\final con el mismo prefijo numerico.' }
    foreach ($s in $scripts) {
        $r = Invocar-Psql $BaseDatos @('-q', '-v', "base=$BaseDatos", '-f', $s.FullName)
        if ($r.Codigo -ne 0) { Detener ("$($s.Name) fallo: " + (($r.Salida | Select-Object -Last 3) -join ' ')) }
        Write-Host "  $($s.Name)"
    }

    # -------------------------------------------------------------- 5. datos y modelos
    Paso '5/8 Datos y modelos (admin.cargar_todo)'
    # Por omision se usan los datos de respaldo: son los validados y dan la huella efe7c9c4 (CC-27).
    $argumentos = @('-m', 'admin.cargar_todo')
    if (-not $Descargar) { $argumentos += '--respaldo' }
    Python-Venv $argumentos
    if ($LASTEXITCODE -ne 0) { Detener 'La carga de datos fallo; revisa el mensaje anterior.' }

    # -------------------------------------------------------------- 6. token interno y capa web
    Paso '6/8 Token interno y capa web'
    if ($SinWeb) {
        Write-Host 'Omitido (-SinWeb). Despues: python -m admin.token_interno y .\frontend\build.ps1, con CATALINA_HOME definido.'
    } else {
        Python-Venv @('-m', 'admin.token_interno')
        if ($LASTEXITCODE -ne 0) { Detener 'No se pudo configurar el token interno.' }
        & (Join-Path $raiz 'frontend\build.ps1')
    }

    # -------------------------------------------------------------- 7. cuentas
    Paso '7/8 Cuentas de usuario'
    foreach ($c in $cuentas) {
        if ((Consulta $BaseDatos "SELECT COUNT(*) FROM usuarios WHERE usuario = '$($c.Usuario)'") -eq '1') {
            Write-Host "  $($c.Usuario) ya existe; se conserva."
            continue
        }
        Write-Host "  Cuenta $($c.Usuario) ($($c.Rol)): escribe su contrasena, de 15 a 128 caracteres."
        Python-Venv @('-m', 'admin.crear_usuario', '--usuario', $c.Usuario, '--nombre', $c.Nombre, '--rol', $c.Rol)
        if ($LASTEXITCODE -ne 0) { Detener "No se pudo crear la cuenta $($c.Usuario)." }
    }

    # -------------------------------------------------------------- 8. verificacion
    Paso '8/8 Verificacion'
    $resultados = [ordered]@{}
    Python-Venv @('-m', 'pytest', '-q')
    $resultados['Pruebas automaticas (55)'] = if ($LASTEXITCODE -eq 0) { 'OK' } else { 'FALLA' }

    $r = Invocar-Psql $BaseDatos @('-q', '-v', "base=$BaseDatos", '-f', (Join-Path $dbFinal '99_verificar_extensiones.sql'))
    $m = [regex]::Matches(($r.Salida -join "`n"), '(?m)^\s*(\d+)\s*\|\s*(\d+)\s*$')
    $resultados['Extensiones del modelo (36)'] = if ($r.Codigo -eq 0 -and $m.Count -and $m[$m.Count - 1].Groups[1].Value -eq $m[$m.Count - 1].Groups[2].Value) { 'OK ' + $m[$m.Count - 1].Groups[1].Value } else { 'FALLA' }

    $vol = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $backend 'etl\datos\volumen_por_sku.json')))
    $r = Invocar-Psql 'postgres' @('-q', '-v', "base=$BaseDatos", '-v', "vol_b64=$vol", '-f', (Join-Path $dbFinal 'validar_kpis.sql'))
    $m = [regex]::Matches(($r.Salida -join "`n"), '(?m)^\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*$')
    $resultados['Integridad y KPIs (23)'] = if ($r.Codigo -eq 0 -and $m.Count -and $m[$m.Count - 1].Groups[1].Value -eq $m[$m.Count - 1].Groups[4].Value) { 'OK ' + $m[$m.Count - 1].Groups[1].Value } else { 'FALLA' }

    Push-Location $backend
    $ErrorActionPreference = 'Continue'
    try { $salida = & $script:pyVenv -m etl.generar_operacion --huella 2>&1 | ForEach-Object { "$_" } }
    finally { Pop-Location; $ErrorActionPreference = 'Stop' }
    $huella = ([regex]::Match(($salida -join "`n"), 'Huella SHA-256: ([0-9a-f]{64})')).Groups[1].Value
    $resultados['Huella de datos (efe7c9c4)'] = if ($huella -eq $huellaValidada) { 'OK' } elseif ($huella) { "DISTINTA ($($huella.Substring(0, 8))): datos distintos a los validados" } else { 'FALLA' }

    Write-Host ''
    $resultados.GetEnumerator() | ForEach-Object { Write-Host ('  {0,-30} {1}' -f $_.Key, $_.Value) }
    if ($resultados.Values | Where-Object { $_ -notlike 'OK*' }) { Detener 'La verificacion no paso completa; revisa los resultados.' }

    Write-Host ''
    Write-Host "Instalacion completa en la base $BaseDatos." -ForegroundColor Green
    Write-Host 'Para usar el dashboard: FastAPI (carpeta backend, entorno activo) con fastapi dev app/main.py,'
    Write-Host 'Tomcat con "$env:CATALINA_HOME\bin\startup.bat" y el navegador en http://localhost:8080/supplychain/'
    if ($BaseDatos -ne 'supply_chain_final') { Write-Host "Nota: esta instalacion quedo en $BaseDatos; si backend\.env ya existia, sigue apuntando a su base." }
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
finally {
    foreach ($v in $variablesProceso) { [Environment]::SetEnvironmentVariable($v, $previas[$v], 'Process') }
    Remove-Variable contrasena -ErrorAction SilentlyContinue
}