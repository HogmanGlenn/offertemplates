$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseDir = Join-Path $projectRoot "release"
$buildDir = Join-Path $projectRoot "build\pyinstaller"
$specDir = Join-Path $projectRoot "build"
$exePath = Join-Path $releaseDir "OfferTemplates.exe"
$sourceConfig = Join-Path $projectRoot "packages.json"
$originalPath = $env:PATH
$originalPythonHome = $env:PYTHONHOME
$originalPythonPath = $env:PYTHONPATH
$originalDataDir = $env:OFFERTEMPLATES_DATA_DIR
$originalSmokeTest = $env:OFFERTEMPLATES_SMOKE_TEST
$smokeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("OfferTemplates-smoke-" + [guid]::NewGuid())
$windowsDir = if ($env:SystemRoot) { $env:SystemRoot } else { "C:\Windows" }

try {
    Set-Location $projectRoot
    python -B -m unittest -v
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed."
    }

    $env:PATH = (($env:PATH -split ";") | Where-Object {
        $_ -and $_ -notlike "*\.cache\codex-runtimes\*"
    }) -join ";"

    python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "OfferTemplates" `
        --add-data "${sourceConfig};." `
        --distpath $releaseDir `
        --workpath $buildDir `
        --specpath $specDir `
        (Join-Path $projectRoot "app.py")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exePath)) {
        throw "PyInstaller did not create OfferTemplates.exe."
    }

    New-Item -ItemType Directory -Path $smokeDir | Out-Null
    $env:PATH = "$windowsDir\System32;$windowsDir"
    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $env:OFFERTEMPLATES_DATA_DIR = $smokeDir
    $env:OFFERTEMPLATES_SMOKE_TEST = "1"
    $process = Start-Process -FilePath $exePath -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        throw "The packaged app exited with code $($process.ExitCode)."
    }

    $smokeConfig = Join-Path $smokeDir "packages.json"
    if (-not (Test-Path -LiteralPath $smokeConfig)) {
        throw "The packaged app did not create its first-run configuration."
    }
    if ((Get-FileHash -LiteralPath $smokeConfig).Hash -ne (Get-FileHash -LiteralPath $sourceConfig).Hash) {
        throw "The packaged app did not start from the clean bundled configuration."
    }

    Add-Content -LiteralPath $smokeConfig -Value " " -NoNewline
    $customConfigHash = (Get-FileHash -LiteralPath $smokeConfig).Hash
    $process = Start-Process -FilePath $exePath -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        throw "The packaged app failed when reopening an existing configuration."
    }
    if ((Get-FileHash -LiteralPath $smokeConfig).Hash -ne $customConfigHash) {
        throw "The packaged app overwrote an existing user configuration."
    }

    Write-Host "Built and smoke-tested: $exePath"
}
finally {
    $env:PATH = $originalPath
    $env:PYTHONHOME = $originalPythonHome
    $env:PYTHONPATH = $originalPythonPath
    $env:OFFERTEMPLATES_DATA_DIR = $originalDataDir
    $env:OFFERTEMPLATES_SMOKE_TEST = $originalSmokeTest
    if (Test-Path -LiteralPath $smokeDir) {
        Remove-Item -LiteralPath $smokeDir -Recurse -Force
    }
}
