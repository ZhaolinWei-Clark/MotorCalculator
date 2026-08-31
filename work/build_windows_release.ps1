param(
    [string]$Python = ".venv\Scripts\python.exe",
    [string]$InstallerCompiler = "",
    [string]$SigningScript = "",
    [string]$CleanMachineStatus = "BLOCKED_BY_ENVIRONMENT",
    [string]$IsolatedLocalStatus = "NOT_RUN",
    [int]$FullTestCount = 589,
    [int]$DeploymentTestCount = 13,
    [switch]$AllowMissingInstallerCompiler,
    [switch]$AllowDirtyWorkingTree,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $RepositoryRoot $Python
$ReleaseDir = Join-Path $RepositoryRoot "release"

function Invoke-Checked {
    param([scriptblock]$Command, [string]$Failure)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw $Failure }
}

Push-Location $RepositoryRoot
try {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "Python executable not found: $PythonPath"
    }
    $trackedChanges = git status --porcelain --untracked-files=no
    if ($trackedChanges -and -not $AllowDirtyWorkingTree) {
        throw "Tracked working tree changes are present. Commit or use -AllowDirtyWorkingTree for an explicit local candidate build."
    }

    $Version = & $PythonPath -c "from motor_calculator.version import APPLICATION_VERSION; print(APPLICATION_VERSION)"
    # Inno Setup requires a doubled opening brace to encode a literal GUID brace.
    $AppId = & $PythonPath -c "from motor_calculator.version import APPLICATION_ID; print('{' + APPLICATION_ID)"
    $Publisher = & $PythonPath -c "from motor_calculator.version import APPLICATION_PUBLISHER; print(APPLICATION_PUBLISHER)"
    $FileVersion = & $PythonPath -c "from motor_calculator.version import windows_version_tuple; print('.'.join(str(item) for item in windows_version_tuple()))"
    $Commit = git rev-parse HEAD
    Invoke-Checked { & $PythonPath -c "from motor_calculator.deployment import verify_protected_files; verify_protected_files(r'$RepositoryRoot')" } "Protected-file hash gate failed."

    if (-not $SkipTests) {
        Invoke-Checked { & $PythonPath -m pytest -q motor_calculator/tests/test_phase8f_deployment.py } "Deployment-specific tests failed."
    }
    Invoke-Checked { & $PythonPath work\generate_release_metadata.py --repository-root $RepositoryRoot --git-commit $Commit } "Release metadata generation failed."
    Invoke-Checked { & powershell -NoProfile -ExecutionPolicy Bypass -File work\build_windows_preview.ps1 -Python $Python } "PyInstaller one-folder build failed."

    $Executable = Join-Path $RepositoryRoot "dist\MotorCalculator\MotorCalculator.exe"
    foreach ($resource in @(
        "dist\MotorCalculator\_internal\_tcl_data\init.tcl",
        "dist\MotorCalculator\_internal\_tk_data\tk.tcl",
        "dist\MotorCalculator\_internal\tcl86t.dll",
        "dist\MotorCalculator\_internal\tk86t.dll"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot $resource) -PathType Leaf)) {
            throw "Required packaged Tcl/Tk resource is missing: $resource"
        }
    }

    $Signed = $false
    if ($SigningScript) {
        Invoke-Checked { & $SigningScript -FilePath $Executable -ArtifactType executable } "Executable signing failed."
        $Signed = $true
    }

    if (-not $InstallerCompiler) {
        $candidate = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if ($candidate) { $InstallerCompiler = $candidate.Source }
    }
    if (-not $InstallerCompiler) {
        foreach ($knownPath in @(
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        )) {
            if ($knownPath -and (Test-Path -LiteralPath $knownPath -PathType Leaf)) {
                $InstallerCompiler = $knownPath
                break
            }
        }
    }
    $InstallerStatus = "BLOCKED_BY_INSTALLER_COMPILER"
    $InstallerVersion = "unknown"
    if ($InstallerCompiler -and (Test-Path -LiteralPath $InstallerCompiler -PathType Leaf)) {
        $InstallerVersion = (Get-Item -LiteralPath $InstallerCompiler).VersionInfo.ProductVersion
        New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
        Invoke-Checked {
            & $InstallerCompiler "/DAppVersion=$Version" "/DAppFileVersion=$FileVersion" "/DAppId=$AppId" "/DAppPublisher=$Publisher" "installer\MotorCalculator.iss"
        } "Inno Setup compilation failed."
        $Installer = Join-Path $ReleaseDir "MotorCalculator-$Version-win64-setup.exe"
        if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
            throw "Installer compiler returned success but expected artifact is missing: $Installer"
        }
        $InstallerStatus = "BUILT_UNTESTED_ON_CLEAN_MACHINE"
        if ($SigningScript) {
            Invoke-Checked { & $SigningScript -FilePath $Installer -ArtifactType installer } "Installer signing failed."
        }
    }

    $TkVersion = & $PythonPath -c "import tkinter as tk; r=tk.Tcl(); print(r.call('info','patchlevel'))"
    $finalize = @(
        "work\finalize_windows_release.py", "--repository-root", $RepositoryRoot,
        "--git-commit", $Commit, "--tkinter-version", $TkVersion,
        "--installer-status", $InstallerStatus, "--clean-machine-status", $CleanMachineStatus,
        "--isolated-local-status", $IsolatedLocalStatus,
        "--installer-technology", "Inno Setup", "--installer-version", $InstallerVersion,
        "--full-test-count", "$FullTestCount", "--deployment-test-count", "$DeploymentTestCount"
    )
    if ($Signed) { $finalize += "--signed" }
    Invoke-Checked { & $PythonPath @finalize } "Release artifact finalization failed."

    Write-Host "Portable release created under: $ReleaseDir"
    Write-Host "Installer status: $InstallerStatus"
    if ($InstallerStatus -eq "BLOCKED_BY_INSTALLER_COMPILER" -and -not $AllowMissingInstallerCompiler) {
        throw "Inno Setup compiler is unavailable. Portable output is valid; installer compilation remains blocked."
    }
}
finally {
    Pop-Location
}
