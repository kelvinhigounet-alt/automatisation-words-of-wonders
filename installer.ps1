# Installation de l'automatisation Words of Wonders (lance par 1_INSTALLER.bat)
# N'utilise que des caracteres ASCII : Windows PowerShell 5.1 lit mal les accents.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

function Etape($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

# ---------- 1. Python
Etape "1/4 Python"
$py = $null
foreach ($c in @("py", "python")) {
    try { $v = & $c --version 2>&1; if ($v -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 9) { $py = $c; break } } catch {}
}
if (-not $py) {
    Write-Host "Python absent -> installation via winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    Write-Host "`nPython vient d'etre installe. FERME cette fenetre et relance 1_INSTALLER.bat." -ForegroundColor Yellow
    exit 1
}
Write-Host "OK : $(& $py --version)"

# ---------- 2. Bibliotheques Python
Etape "2/4 Bibliotheques Python (opencv, numpy)"
& $py -m pip install --upgrade --quiet pip
& $py -m pip install --quiet -r requirements.txt
Write-Host "OK"

# ---------- 3. ADB (platform-tools Google)
Etape "3/4 ADB"
if (Test-Path "$dir\platform-tools\adb.exe") {
    Write-Host "Deja present"
} else {
    $zip = "$env:TEMP\platform-tools.zip"
    Invoke-WebRequest "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $dir -Force
    Remove-Item $zip
    Write-Host "OK : $dir\platform-tools\adb.exe"
}

# ---------- 4. Tesseract OCR
Etape "4/4 Tesseract OCR"
$tess = @("C:\Program Files\Tesseract-OCR\tesseract.exe",
          "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
          "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($tess) {
    Write-Host "Deja present : $tess"
} else {
    Write-Host "Installation via winget (accepte la fenetre d'administrateur si elle apparait)..."
    winget install -e --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
}

Write-Host "`nInstallation terminee." -ForegroundColor Green
Write-Host "Branche le telephone puis lance 2_VERIFIER_CONNEXION.bat"
