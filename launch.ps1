param([ValidateSet('start','setup','check')][string]$Mode = 'start')
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$appRoot = Join-Path $projectRoot 'apps\gradio'
$envPython = Join-Path $appRoot '.venv\Scripts\python.exe'
try {
    if (-not (Test-Path -LiteralPath $envPython)) {
        $pythonCandidates = @(
            (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
        )
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand -and $pythonCommand.Source -notmatch 'WindowsApps') { $pythonCandidates += $pythonCommand.Source }
        $basePython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $basePython) { throw 'Install Python 3.11 or later from python.org, then reopen this shortcut.' }
        & $basePython -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11 or later is required"'
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or later is required.' }
        & $basePython -m venv (Join-Path $appRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    $requirements = Join-Path $appRoot 'requirements.txt'
    $requirementsHash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $stampPath = Join-Path $appRoot '.venv\requirements.sha256'
    $installedHash = if (Test-Path -LiteralPath $stampPath) { (Get-Content -LiteralPath $stampPath -Raw).Trim() } else { '' }
    if ($installedHash -ne $requirementsHash) {
        & $envPython -m pip install -r $requirements
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your internet connection.' }
        Set-Content -LiteralPath $stampPath -Value $requirementsHash -Encoding ascii
    }
    $envPath = Join-Path $appRoot '.env'
    if ($Mode -eq 'setup' -and -not (Test-Path -LiteralPath $envPath)) {
        Copy-Item -LiteralPath (Join-Path $appRoot '.env.example') -Destination $envPath
        Write-Host 'A private .env was created. Add both API keys and your Dust workspace ID, save, then run SETUP again.'
        Start-Process notepad.exe -ArgumentList ('"' + $envPath + '"') -WindowStyle Normal
        exit 0
    }
    if ($Mode -eq 'setup') {
        & $envPython (Join-Path $appRoot 'setup_providers.py') --provision
    } elseif ($Mode -eq 'check') {
        & $envPython -m unittest discover -s (Join-Path $projectRoot 'tests') -q
    } else {
        Write-Host 'Open http://127.0.0.1:7865 in your browser. This window keeps Lecture running. Ctrl+C stops it.'
        & $envPython (Join-Path $appRoot 'app.py')
    }
    exit $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
