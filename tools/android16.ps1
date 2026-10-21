<#
  Versión PC del parche "Compatibilidad Android 16" de Zenith APK Editor.
  Decompila con apktool, sube el targetSdk, añade android:exported, (opcional) te deja editar
  smali/recursos en Android Studio, recompila, alinea a 16 KB y firma con tu debug.keystore.

  Uso:
    .\android16.ps1 -Apk juego.apk                 # API 36
    .\android16.ps1 -Apk juego.apk -Target 24      # mínimo instalable en Android 15/16/17
    .\android16.ps1 -Apk juego.apk -Edit           # pausa para editar antes de recompilar
#>
param(
    [Parameter(Mandatory = $true)][string]$Apk,
    [int]$Target = 36,
    [switch]$Edit,
    [string]$Apktool = (Join-Path $PSScriptRoot "apktool.jar")
)
$ErrorActionPreference = "Stop"

function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function Run($exe) { & $exe @args; if ($LASTEXITCODE -ne 0) { Fail "$exe terminó con código $LASTEXITCODE" } }

if ($Target -lt 24) { Fail "Android 15/16/17 no instalan apps con targetSdk menor a 24" }
if (-not (Test-Path $Apk)) { Fail "No existe $Apk" }
if (-not (Test-Path $Apktool)) { Fail "Falta apktool.jar junto al script (descárgalo de https://apktool.org)" }

# Java: JAVA_HOME, o el que trae Android Studio, o el del PATH
$java = "java"
if ($env:JAVA_HOME) { $java = Join-Path $env:JAVA_HOME "bin/java" }
elseif (Test-Path "C:\Program Files\Android\Android Studio\jbr\bin\java.exe") { $java = "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" }

# build-tools más nuevo del SDK (ruta por defecto de Android Studio en Windows)
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA "Android\Sdk" }
$bt = Get-ChildItem (Join-Path $sdk "build-tools") -Directory -ErrorAction SilentlyContinue |
      Sort-Object { [version]($_.Name -replace '-.*', '') } | Select-Object -Last 1
if (-not $bt) { Fail "No encuentro build-tools en $sdk (instálalo desde el SDK Manager de Android Studio)" }
function Tool($name) { foreach ($ext in ".exe", ".bat", "") { $p = Join-Path $bt.FullName "$name$ext"; if (Test-Path $p) { return $p } } Fail "Falta $name en $($bt.FullName)" }

$name = [IO.Path]::GetFileNameWithoutExtension($Apk)
$dir = Split-Path (Resolve-Path $Apk)
$work = Join-Path $dir "$name-src"
$out = Join-Path $dir "${name}_api$Target.apk"

Write-Host "1/5 Decompilando en $work"
Run $java -jar $Apktool d -f -o $work $Apk

Write-Host "2/5 targetSdkVersion -> $Target"
$yml = Join-Path $work "apktool.yml"
$text = Get-Content $yml -Raw
$current = if ($text -match 'targetSdkVersion:\s*''?(\d+)') { [int]$Matches[1] } else { 0 }
if ($current -lt $Target) {
    if ($current) { $text = $text -replace 'targetSdkVersion:\s*''?\d+''?', "targetSdkVersion: $Target" }
    else { $text = $text -replace 'sdkInfo:\s*\r?\n', "sdkInfo:`n  targetSdkVersion: $Target`n" }
}
$text = $text -replace '(?m)^\s*maxSdkVersion:.*\r?\n', ''   # bloquearía la instalación en Android nuevos
Set-Content $yml $text -NoNewline

if ($Target -ge 31) {
    # Antes de API 31, tener intent-filter implicaba exported=true; se conserva igual.
    $ns = "http://schemas.android.com/apk/res/android"
    $manifestPath = Join-Path $work "AndroidManifest.xml"
    $xml = New-Object xml; $xml.PreserveWhitespace = $true; $xml.Load($manifestPath)
    $fixed = 0
    foreach ($c in $xml.manifest.application.ChildNodes) {
        if ($c.LocalName -in "activity", "activity-alias", "service", "receiver" -and
            -not $c.HasAttribute("exported", $ns) -and $c.SelectSingleNode("intent-filter")) {
            [void]$c.SetAttribute("exported", $ns, "true"); $fixed++
        }
    }
    $xml.Save($manifestPath)
    Write-Host "    android:exported añadido a $fixed componente(s)"
}

if ($Edit) {
    Write-Host "`nAbre $work en Android Studio (File > Open) y edita smali/, res/ o AndroidManifest.xml." -ForegroundColor Yellow
    Read-Host "Cuando termines, presiona Enter para recompilar"
}

Write-Host "3/5 Recompilando"
$unsigned = Join-Path $work "build-unsigned.apk"; $aligned = Join-Path $work "build-aligned.apk"
Run $java -jar $Apktool b -f -o $unsigned $work

Write-Host "4/5 Alineando (4 B y .so a 16 KB)"
Run (Tool zipalign) -f -P 16 4 $unsigned $aligned

Write-Host "5/5 Firmando con el debug.keystore de Android Studio"
$ks = Join-Path $HOME ".android/debug.keystore"
if (-not (Test-Path $ks)) {
    New-Item -ItemType Directory -Force (Split-Path $ks) | Out-Null
    $keytool = if ($java -eq "java") { "keytool" } else { Join-Path (Split-Path $java) "keytool" }
    Run $keytool -genkeypair -keystore $ks -storepass android -keypass android -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
}
Run (Tool apksigner) sign --ks $ks --ks-pass pass:android --out $out $aligned
Remove-Item $unsigned, $aligned, "$out.idsig" -ErrorAction SilentlyContinue

Write-Host "`nListo: $out" -ForegroundColor Green
Write-Host "Instalar (desinstala antes la original):  adb install `"$out`""
