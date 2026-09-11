param([string]$IsccPath = "")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)" }
}

function Clear-GeneratedDirectory([string]$Relative) {
    if ($Relative -notin @("build", "dist", "installer\output")) { throw "Unauthorized cleanup target" }
    $target = [IO.Path]::GetFullPath((Join-Path $projectRoot $Relative))
    if (-not $target.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Cleanup escaped the repository: $target"
    }
    # Refuse links at any ancestor or below the target before recursive deletion.
    $ancestor = $target
    while ($ancestor -ne $projectRoot) {
        if (Test-Path -LiteralPath $ancestor) {
            if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing linked artifact directory: $ancestor"
            }
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    if (Test-Path -LiteralPath $target) {
        $links = @(Get-ChildItem -LiteralPath $target -Recurse -Force | Where-Object {
            $_.Attributes -band [IO.FileAttributes]::ReparsePoint
        })
        if ($links.Count) { throw "Refusing artifact tree containing links: $target" }
        Write-Output "Cleaning generated artifacts: $target"
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

function Find-Iscc {
    if ($IsccPath) {
        if (-not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) { throw "ISCC.exe not found at supplied path" }
        return (Resolve-Path -LiteralPath $IsccPath).Path
    }
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($parent in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, (Join-Path $env:LOCALAPPDATA "Programs"))) {
        if ($parent -and (Test-Path -LiteralPath $parent)) {
            foreach ($folder in @(Get-ChildItem -LiteralPath $parent -Directory -Filter "Inno Setup*" | Sort-Object Name -Descending)) {
                $candidate = Join-Path $folder.FullName "ISCC.exe"
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
            }
        }
    }
    return $null
}

try {
    if ((Get-Location).ProviderPath -ne $projectRoot) { throw "Run scripts/build_release.ps1 from the repository root" }
    $python = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) { throw "Missing .venv/Scripts/python.exe" }
    # A fresh directory avoids stale pytest ACLs; no source or local config is cleaned.
    $testTemp = (Join-Path ([IO.Path]::GetTempPath()) ("triqui-release-tests-" + [guid]::NewGuid())).Replace('\', '/')
    $previousPytestOptions = $env:PYTEST_ADDOPTS
    try {
        $env:PYTEST_ADDOPTS = '--basetemp="' + $testTemp + '" -o cache_dir="' + $testTemp + '/cache"'
        & $python -m pytest -q
        Assert-LastExit "pytest"
    } finally { $env:PYTEST_ADDOPTS = $previousPytestOptions }
    & $python -m pip check
    Assert-LastExit "pip check"
    & git -c core.whitespace=cr-at-eol --no-pager diff --no-ext-diff --check
    Assert-LastExit "git diff --check"

    foreach ($relative in @("build", "dist", "installer\output")) { Clear-GeneratedDirectory $relative }
    $previousPyiCache = $env:PYINSTALLER_CONFIG_DIR
    try {
        # Keep PyInstaller's own --clean cache inside the authorized build tree.
        $env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot "build\pyinstaller-cache"
        & $python -m PyInstaller --noconfirm --clean robot_triqui.spec
        Assert-LastExit "PyInstaller onedir"
    } finally { $env:PYINSTALLER_CONFIG_DIR = $previousPyiCache }
    $product = Join-Path $projectRoot "dist\RobotTriqui\RobotTriqui.exe"
    if (-not (Test-Path -LiteralPath $product -PathType Leaf)) { throw "Missing RobotTriqui.exe" }

    & $python scripts/release_support.py stage
    Assert-LastExit "Configuration staging"
    $provenance = Get-Content -LiteralPath "build/stage-result.json" -Raw | ConvertFrom-Json
    if ($provenance.generic) {
        Write-Warning "GENERIC CONFIGURATION: at least one local YAML is missing. Configure the installation before real use."
    } else { Write-Output "Configuration: local app + local vision (distribution only; not staged in Git)." }
    & $python scripts/release_support.py audit
    Assert-LastExit "Distribution audit"
    Write-Output "ONEDIR: $product"

    $compiler = Find-Iscc
    if (-not $compiler) {
        throw "ONEDIR READY. Missing Inno Setup ISCC.exe; installer not generated. No software downloaded. Install Inno Setup manually and rerun, or supply -IsccPath."
    }
    Write-Output "Inno Setup compiler: $compiler"
    & $compiler installer/RobotTriqui.iss
    Assert-LastExit "Inno Setup"
    $compiled = Join-Path $projectRoot "installer\output\RobotTriqui_Setup.exe"
    if (-not (Test-Path -LiteralPath $compiled -PathType Leaf)) { throw "Installer was not generated" }
    $release = Join-Path $projectRoot "dist\release"
    New-Item -ItemType Directory -Path $release -Force | Out-Null
    $installer = Join-Path $release "RobotTriqui_Setup.exe"
    Copy-Item -LiteralPath $compiled -Destination $installer
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
    $size = (Get-Item -LiteralPath $installer).Length
    Write-Output "INSTALLER: $installer"
    Write-Output "SIZE: $size bytes ($([Math]::Round($size / 1MB, 2)) MiB)"
    Write-Output "SHA256: $hash"
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
