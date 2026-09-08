param(
    [ValidateSet(1,2,3,4,5,6,7)][int]$Group,
    [string]$Python = "",
    [string]$Config = "",
    [string]$TestReport = "",
    [switch]$AllowMotion,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Python) { $Python = Join-Path $projectRoot ".venv\Scripts\python.exe" }
$groups = @{
    1 = @("C0")
    2 = @("C1", "C2", "C3", "C4", "C5")
    3 = @("C6")
    4 = @("C7")
    5 = @("C8")
    6 = @("C9")
    7 = @(0..9 | ForEach-Object { "C$_" })
}
if (-not $Group) {
    Write-Host "1 Software | 2 Vision completa | 3 Red UR | 4 Mode0 handshake"
    Write-Host "5 Cell5 SAFE | 6 Grid SAFE | 7 Full available commissioning"
    $selection = Read-Host "Grupo (1-7); otra respuesta cancela"
    if ($selection -notmatch '^[1-7]$') { return }
    $Group = [int]$selection
}
if (-not $Config -and (Test-Path -LiteralPath (Join-Path $projectRoot "config\app.local.yaml"))) {
    $Config = Join-Path $projectRoot "config\app.local.yaml"
}
if (-not $TestReport -and (Test-Path -LiteralPath (Join-Path $projectRoot "reports\pytest.xml"))) {
    $TestReport = Join-Path $projectRoot "reports\pytest.xml"
}
$runnerArgs = @("-m", "ur_tictactoe.commissioning", "--steps") + $groups[$Group] + @("--text-report")
if ($Config) { $runnerArgs += @("--config", $Config) }
if ($TestReport) { $runnerArgs += @("--pytest-report", $TestReport) }
if ($AllowMotion) { $runnerArgs += "--allow-motion" }
if ($DryRun) {
    [pscustomobject]@{python=$Python; arguments=$runnerArgs; working_directory=$projectRoot} | ConvertTo-Json -Depth 3
    return
}
if ($Group -ge 4 -and -not $AllowMotion) {
    Write-Host "Sin -AllowMotion, C7-C9 permanecen BLOCKED. El runner exige sus confirmaciones internas."
}
$previousPythonPath = $env:PYTHONPATH
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot "src"
    & $Python @runnerArgs
    $runnerExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
exit $runnerExitCode
