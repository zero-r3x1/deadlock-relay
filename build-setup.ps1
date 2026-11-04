param(
    [string]$DistDir = 'dist/verified',
    [string]$CompilerPath = '',
    [string]$Version = '1.0.0'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $CompilerPath) {
    $candidates = @(
        "${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe",
        "$env:ProgramFiles/Inno Setup 6/ISCC.exe",
        "$env:LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe"
    )
    $CompilerPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $CompilerPath) { throw 'Install Inno Setup 6 or pass -CompilerPath to ISCC.exe' }
$source = (Resolve-Path -LiteralPath (Join-Path $DistDir 'DeadlockRelay')).Path
& ./.venv/Scripts/python.exe package.py --dist-dir $DistDir
if ($LASTEXITCODE -ne 0) { throw 'Portable package verification failed' }
& $CompilerPath "/DSourceDir=$source" "/DAppVersion=$Version" 'installer/setup.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
Write-Output "Ready: dist/DeadlockRelay-$Version-Setup.exe"
