param([string]$Python = "", [switch]$InstallDependencies)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Python) { $Python = Join-Path $projectRoot ".venv\Scripts\python.exe" }
Push-Location $projectRoot
try {
    if ($InstallDependencies) {
        & $Python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    }
    & $Python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.update(); root.destroy()"
    if ($LASTEXITCODE -ne 0) { throw "Tcl/Tk is not functional in the build interpreter" }
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Inconsistent dependencies" }
    & $Python -m pytest -q --junitxml=reports/pytest.xml
    if ($LASTEXITCODE -ne 0) { throw "Tests must pass before packaging" }
    # Remove only this product's generated directories after resolving containment.
    foreach ($relative in @("build\robot_triqui", "dist\RobotTriqui")) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $relative))
        if (-not $target.StartsWith($projectRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Build cleanup escaped project root"
        }
        if (Test-Path -LiteralPath $target) {
            $item = Get-Item -LiteralPath $target
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Refusing to clean a linked build directory"
            }
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
    & $Python -m PyInstaller --noconfirm --clean robot_triqui.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    $product = Join-Path $projectRoot "dist\RobotTriqui\RobotTriqui.exe"
    if (-not (Test-Path -LiteralPath $product)) { throw "Missing executable" }
    Write-Output $product
} finally {
    Pop-Location
}
