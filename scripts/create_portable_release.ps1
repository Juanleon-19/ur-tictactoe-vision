param()
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
# Always rebuild cleanly: never archive a distribution with personal configuration.
& (Join-Path $PSScriptRoot "build_windows.ps1")
$bundle = Join-Path $projectRoot "dist\RobotTriqui"
$files = @(Get-ChildItem -LiteralPath $bundle -Recurse -File)
foreach ($file in $files) {
    $relative = $file.FullName.Substring($bundle.Length + 1).Replace('\', '/')
    if ($relative -ne "RobotTriqui.exe" -and -not $relative.StartsWith("_internal/")) {
        throw "Unexpected file in clean runtime distribution: $relative"
    }
    if ($relative -match '(?i)(^|/)(\.git|\.venv|reports|\.pytest_cache)(/|$)|\.local\.(yaml|yml|json)$|(^|/)config/(app|vision)\.yaml$') {
        throw "Local/non-runtime file is forbidden in release: $relative"
    }
}
$releaseDir = Join-Path $projectRoot "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$zipPath = Join-Path $releaseDir "RobotTriqui_Windows_x64.zip"
$temporaryZip = Join-Path $releaseDir (([guid]::NewGuid().ToString()) + ".zip")
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($temporaryZip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in ($files | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($bundle.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive, $file.FullName, "RobotTriqui/$relative", [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $archive, (Join-Path $projectRoot "packaging\README-portable.txt"),
        "RobotTriqui/README.txt", [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
} finally { $archive.Dispose() }
Move-Item -LiteralPath $temporaryZip -Destination $zipPath -Force
Get-Item -LiteralPath $zipPath | Select-Object FullName, Length
