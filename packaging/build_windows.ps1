# Construit la version Windows : exe unique, installateur Inno Setup et version portable (.zip).
# Exécuté par GitHub Actions sur windows-latest.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$Version = python -c "import jcfportable; print(jcfportable.VERSION)"
Remove-Item -Recurse -Force build, dist, out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force out, build | Out-Null

# 1) Application autonome (Python + Qt embarqués)
pyinstaller --noconfirm --clean --windowed --name jcfportable --paths . `
  --icon packaging/jcfportable.ico `
  --add-data "jcfportable/icon.png:jcfportable" --add-data "jcfportable/assets:jcfportable/assets" `
  --hidden-import PySide6.QtSerialPort `
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.Qt3DCore `
  packaging/run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a échoué" }
$App = "dist/jcfportable"

# 2) Hamlib pour Windows (rigctld.exe, rigctl.exe et DLL) depuis la dernière version officielle
$Assets = gh release view --repo Hamlib/Hamlib --json assets -q ".assets[].name"
$Zip = $Assets | Where-Object { $_ -match '^hamlib-w64-[0-9.]+\.zip$' } | Select-Object -First 1
if (-not $Zip) { throw "Archive Hamlib Windows introuvable dans : $Assets" }
Write-Host "Hamlib : $Zip"
gh release download --repo Hamlib/Hamlib --pattern $Zip --dir build
Expand-Archive -Force "build/$Zip" build/hamlib
$Rigctld = Get-ChildItem -Recurse build/hamlib -Filter rigctld.exe | Select-Object -First 1
if (-not $Rigctld) { throw "rigctld.exe absent de l'archive Hamlib" }
New-Item -ItemType Directory -Force "$App/hamlib" | Out-Null
Copy-Item "$($Rigctld.DirectoryName)/*" "$App/hamlib/" -Recurse
& "$App/hamlib/rigctl.exe" -l | Select-Object -First 3

# 3) Version portable (dossier zippé)
Compress-Archive -Force -Path $App -DestinationPath "out/JCFPortable-$Version-windows-portable.zip"

# 4) Installateur
$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) {
  choco install innosetup -y --no-progress | Out-Null
}
& $Iscc "/DAppVersion=$Version" "/DSourceDir=$((Resolve-Path $App).Path)" "/O$((Resolve-Path out).Path)" packaging/jcfportable.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup a échoué" }
# 5) Exe unique : tout (Python, Qt, Hamlib) dans un seul fichier à double-cliquer
pyinstaller --noconfirm --onefile --windowed --name "JCFPortable-$Version-windows" --paths . `
  --distpath build/onefile --workpath build/onefile-work `
  --icon packaging/jcfportable.ico `
  --add-data "jcfportable/icon.png:jcfportable" --add-data "jcfportable/assets:jcfportable/assets" `
  --add-data "$($Rigctld.DirectoryName):hamlib" `
  --hidden-import PySide6.QtSerialPort `
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.Qt3DCore `
  packaging/run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (exe unique) a échoué" }
Copy-Item "build/onefile/JCFPortable-$Version-windows.exe" out/
Get-ChildItem out
