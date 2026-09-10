$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$spec = Join-Path $projectRoot "packaging\RotoMaskAnalyzer.spec"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Virtuelle Umgebung fehlt. Zuerst: py -3.13 -m venv .venv und .\.venv\Scripts\python.exe -m pip install -e '.[dev]'"
}

Push-Location $projectRoot
$previousPath = $env:PATH
try {
    $pythonBase = (& $python -c "import sys; print(sys.base_prefix)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $pythonBase) {
        throw "Python-Basisverzeichnis konnte nicht ermittelt werden."
    }
    $windowsRoot = $env:SystemRoot
    $env:PATH = [string]::Join(
        [IO.Path]::PathSeparator,
        @($pythonBase, (Join-Path $windowsRoot "System32"), $windowsRoot)
    )
    & $python -m PyInstaller --noconfirm --clean $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller-Build fehlgeschlagen (Exitcode $LASTEXITCODE)."
    }
    $executable = Join-Path $projectRoot "dist\RotoMaskAnalyzer.exe"
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Build meldete Erfolg, aber RotoMaskAnalyzer.exe fehlt."
    }
    Write-Host "Gebaut: $executable"
}
finally {
    $env:PATH = $previousPath
    Pop-Location
}
