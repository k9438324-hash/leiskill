[CmdletBinding()]
param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Update-JjPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}

function Find-JjPython {
    foreach ($candidate in @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'), (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.12-64\python.exe'))) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $found = & $launcher.Source -3.12 -c 'import sys;print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $found -and (Test-Path -LiteralPath ([string]$found))) { return [string]$found }
    }
    return $null
}

function Install-JjTool([string]$Id) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "winget is required to install $Id. Install Microsoft App Installer, then run this command again."
    }
    & winget.exe install --id $Id --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installation failed: $Id (exit $LASTEXITCODE)" }
    Update-JjPath
}

Update-JjPath
$python = Find-JjPython
if ($CheckOnly) {
    [pscustomobject]@{
        Python312 = $python
        Npx = [bool](Get-Command npx.cmd -ErrorAction SilentlyContinue)
        Git = [bool](Get-Command git.exe -ErrorAction SilentlyContinue)
        Winget = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)
        Runtime = (Join-Path $env:LOCALAPPDATA 'jj-skill\venv\Scripts\python.exe')
    } | ConvertTo-Json
    return
}

if (-not $python) { Install-JjTool 'Python.Python.3.12'; $python = Find-JjPython }
if (-not $python) { throw 'Python 3.12 was not found. Restart PowerShell and retry.' }
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { Install-JjTool 'Git.Git' }
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { Install-JjTool 'OpenJS.NodeJS.LTS' }
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue) -or -not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) {
    throw 'Git or Node.js is not yet available. Restart PowerShell and retry.'
}

Write-Host '[1/4] Installing jj and its script-review skill...'
& npx.cmd -y skills add k9438324-hash/jj-skill --skill jj --agent codex -g -y
if ($LASTEXITCODE -ne 0) { throw 'jj skill installation failed.' }
& npx.cmd -y skills add dontbesilent2025/dbskill --skill dbs-script-flow --agent codex -g -y
if ($LASTEXITCODE -ne 0) { throw 'dbs-script-flow installation failed.' }

Write-Host '[2/4] Preparing an isolated Python environment...'
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'jj-skill'
$venv = Join-Path $runtimeRoot 'venv'
$runtimePython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) {
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}

Write-Host '[3/4] Installing FFmpeg and Jianying draft dependencies...'
& $runtimePython -m pip install --disable-pip-version-check imageio-ffmpeg 'git+https://github.com/aoguai/pyJianYingDraft.git'
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed. Check network access and retry.' }

Write-Host '[4/4] Checking the environment...'
$skillRoot = Join-Path $env:USERPROFILE '.agents\skills\jj'
$doctor = Join-Path $skillRoot 'scripts\doctor.py'
if (-not (Test-Path -LiteralPath $doctor)) { throw 'Installed jj doctor.py was not found.' }
& $runtimePython -X utf8 $doctor
if ($LASTEXITCODE -ne 0) {
    throw 'Skills are installed, but environment checks failed above. Install and open Jianying Pro once. For custom locations, set JY_INSTALL_DIR and JY_USER_DATA, then retry. Existing drafts were not changed.'
}
Write-Host 'SUCCESS: jj is installed and environment checks passed. Restart Codex, open a new chat, and use /jj with your timed SRT and media folder. Draft playback/export still need verification.' -ForegroundColor Green
