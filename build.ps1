$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ required' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& ./.venv/Scripts/python.exe tools/build_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
& ./.venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name DeadlockRelay --icon assets/icon.ico --add-data 'assets;assets' --add-data 'blocker/style.qss;blocker' main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Copy-Item -LiteralPath README.md, THIRD_PARTY.md -Destination dist/DeadlockRelay
if (Test-Path licenses) { Copy-Item -LiteralPath licenses -Destination dist/DeadlockRelay -Recurse -Force }
if (Test-Path docs) { Copy-Item -LiteralPath docs -Destination dist/DeadlockRelay -Recurse -Force }
$smoke = Start-Process -FilePath ./dist/DeadlockRelay/DeadlockRelay.exe -ArgumentList '--self-check' -WindowStyle Hidden -PassThru -Wait
if ($smoke.ExitCode -ne 0) { throw 'Packaged self-check failed' }
Compress-Archive -Path dist/DeadlockRelay -DestinationPath dist/DeadlockRelay-windows-x64.zip -Force
Write-Output 'Ready: dist/DeadlockRelay/DeadlockRelay.exe'
