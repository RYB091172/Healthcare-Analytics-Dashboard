$ErrorActionPreference = "Stop"

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "This build script must be run on Windows."
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
$buildWorkPath = Join-Path $env:TEMP "HealthcareAnalytics-build"

$pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    & $pythonLauncher.Source -3 -m venv .build-venv
} else {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3 is required to build the executable."
    }

    & $pythonCommand.Source -m venv .build-venv
}

if ($LASTEXITCODE -ne 0) {
    throw "Could not create the build environment."
}

$buildPython = Join-Path $projectRoot ".build-venv\Scripts\python.exe"
& $buildPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not update pip in the build environment."
}

& $buildPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the application build dependencies."
}

& $buildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name HealthcareAnalytics `
    --workpath $buildWorkPath `
    --collect-all customtkinter `
    main_code.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to build the application."
}

Write-Host "Build complete: $projectRoot\dist\HealthcareAnalytics.exe"
