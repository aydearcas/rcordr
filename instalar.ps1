# Instala rcordr: crea el entorno virtual, instala dependencias y crea accesos directos.
#   powershell -ExecutionPolicy Bypass -File instalar.ps1            -> menú Inicio
#   powershell -ExecutionPolicy Bypass -File instalar.ps1 -Inicio    -> además, arrancar con Windows
param([switch]$Inicio)

$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$venv = Join-Path $dir ".venv"

if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "Creando entorno virtual..."
    python -m venv $venv
}
# --require-hashes: pip rechaza cualquier paquete cuyo hash no coincida con requirements.txt
& "$venv\Scripts\python.exe" -m pip install --require-hashes --only-binary=:all: -r (Join-Path $dir "requirements.txt") -q
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias." }

$shell = New-Object -ComObject WScript.Shell
function New-Shortcut($path) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = "$venv\Scripts\pythonw.exe"
    $lnk.Arguments = "`"$dir\rcordr.pyw`""
    $lnk.WorkingDirectory = $dir
    $lnk.IconLocation = "$dir\assets\rcordr.ico"
    $lnk.Description = "Capturas y grabación de pantalla"
    $lnk.Save()
    Write-Host "Acceso directo: $path"
}

New-Shortcut (Join-Path ([Environment]::GetFolderPath("Programs")) "rcordr.lnk")
if ($Inicio) {
    New-Shortcut (Join-Path ([Environment]::GetFolderPath("Startup")) "rcordr.lnk")
}
Write-Host "Listo. Busca 'rcordr' en el menú Inicio."
