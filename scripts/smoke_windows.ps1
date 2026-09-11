param([string]$Product = "", [string]$EvidenceRoot = "")
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Product) { $Product = Join-Path $projectRoot "dist\RobotTriqui\RobotTriqui.exe" }
$Product = (Resolve-Path -LiteralPath $Product).Path
$bundle = Split-Path -Parent $Product
# Always simulation, including laboratory bundles with real external settings.
# Never launch the default real mode from an automated packaging smoke.
$logo = Join-Path $bundle "_internal\assets\javeriana_logo.png"
if (-not (Test-Path -LiteralPath $logo)) { throw "Bundled logo is missing" }
$sourceHash = (Get-FileHash -LiteralPath (Join-Path $projectRoot "assets\javeriana_logo.png")).Hash
if ((Get-FileHash -LiteralPath $logo).Hash -ne $sourceHash) { throw "Bundled logo differs from source" }
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $projectRoot "reports" }
$sessionDir = Join-Path $EvidenceRoot ("smoke_" + (Get-Date -Format "yyyyMMdd_HHmmss_fff"))
New-Item -ItemType Directory -Path $sessionDir | Out-Null
$workingDir = Join-Path $sessionDir "empty-cwd"
New-Item -ItemType Directory -Path $workingDir | Out-Null
$results = @()
foreach ($mode in @("SIMULATION")) {
    $stdout = Join-Path $sessionDir "$mode.stdout.log"
    $stderr = Join-Path $sessionDir "$mode.stderr.log"
    $launch = @{
        FilePath = $Product; WorkingDirectory = $workingDir; PassThru = $true
        RedirectStandardOutput = $stdout; RedirectStandardError = $stderr
        WindowStyle = "Normal"
    }
    $launch.ArgumentList = @("--simulate")
    $process = Start-Process @launch
    # Retain the process handle before exit so Windows PowerShell can read ExitCode.
    $processHandle = $process.Handle
    $result = [ordered]@{mode=$mode; pid=$process.Id; status="FAIL"; visual="NOT CONFIRMED"; logo_sha256=$sourceHash}
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(10)
        $windowSeen = $false
        while ([DateTime]::UtcNow -lt $deadline) {
            $process.Refresh()
            if ($process.HasExited) { throw "Process exited before smoke interval elapsed" }
            if ($process.MainWindowHandle -ne 0 -and $process.MainWindowTitle -eq "Robot Triqui") {
                $windowSeen = $true
            }
            Start-Sleep -Milliseconds 200
        }
        $process.Refresh()
        if (-not $windowSeen -or -not $process.Responding) { throw "Expected responsive window not found" }
        $result.window = $process.MainWindowTitle
        $result.survived_seconds = 10
        $result.close_requested = $process.CloseMainWindow()
        if (-not $result.close_requested -or -not $process.WaitForExit(10000)) {
            throw "Controlled close did not complete"
        }
        $process.Refresh()
        $result.exit_code = $process.ExitCode
        if ($process.ExitCode -ne 0) { throw "Nonzero process exit" }
        $logText = (Get-Content -LiteralPath $stdout -Raw) + (Get-Content -LiteralPath $stderr -Raw)
        if ($logText -match "Traceback|Failed to execute script") { throw "Python failure in process logs" }
        $result.status = "PASS"
    } catch {
        $result.error = $_.Exception.Message
    } finally {
        $process.Refresh()
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id
            $result.forced_cleanup = $true
        }
        $results += [pscustomobject]$result
    }
}
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $sessionDir "results.json") -Encoding UTF8
$results | Format-Table mode,status,window,exit_code,visual
Write-Output "Evidence: $sessionDir"
if ($results.Where({$_.status -ne "PASS"}).Count) { throw "Process smoke failed; inspect session report" }
