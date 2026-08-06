param(
    [string]$Python = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $RepositoryRoot $Python

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python executable not found: $PythonPath"
}

Push-Location $RepositoryRoot
try {
    & $PythonPath "work\check_tk_runtime.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Tcl/Tk preflight failed. No package was generated."
    }

    & $PythonPath -c "import PyInstaller; print(PyInstaller.__version__)"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is unavailable. Install requirements-packaging.txt in a complete build environment."
    }

    & $PythonPath -m PyInstaller --clean --noconfirm "packaging\MotorCalculator.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    $Executable = Join-Path $RepositoryRoot "dist\MotorCalculator\MotorCalculator.exe"
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Expected one-folder executable is missing: $Executable"
    }
    Write-Host "Engineering-preview package created: $Executable"
}
finally {
    Pop-Location
}
