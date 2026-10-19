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
& "$venv\Scripts\python.exe" -m pip install --upgrade pip -q
& "$venv\Scripts\python.exe" -m pip install -r (Join-Path $dir "requirements.txt") -q

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
