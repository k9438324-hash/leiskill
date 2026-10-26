[CmdletBinding()]
param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Update-JjPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}

function Find-JjPython {
    $candidates = @($env:LEISKILL_PYTHON, (Join-Path $env:LOCALAPPDATA 'leiskill\venv\Scripts\python.exe'), (Join-Path $env:LOCALAPPDATA 'jj-skill\venv\Scripts\python.exe'), (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'), (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.12-64\python.exe'))
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $valid = & $candidate -c 'import sys;print(sys.version_info >= (3,10))' 2>$null
            if ($LASTEXITCODE -eq 0 -and $valid -eq 'True') { return $candidate }
        }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $found = & $launcher.Source -3.12 -c 'import sys;print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $found -and (Test-Path -LiteralPath ([string]$found))) { return [string]$found }
    }
    $plain = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($plain -and $plain.Source -notmatch 'WindowsApps') {
        $valid = & $plain.Source -c 'import sys;print(sys.version_info >= (3,10))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $valid -eq 'True') { return $plain.Source }
    }
    return $null
}

function Get-LeiRuntime {
    foreach ($candidate in @($env:LEISKILL_PYTHON, (Join-Path $env:LOCALAPPDATA 'leiskill\venv\Scripts\python.exe'), (Join-Path $env:LOCALAPPDATA 'jj-skill\venv\Scripts\python.exe'))) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $valid = & $candidate -c 'import sys;print(sys.prefix != sys.base_prefix and sys.version_info >= (3,10))' 2>$null
            if ($LASTEXITCODE -eq 0 -and $valid -eq 'True') { return $candidate }
        }
    }
    return (Join-Path $env:LOCALAPPDATA 'leiskill\venv\Scripts\python.exe')
}

function Install-JjTool([string]$Id) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "winget is required to install $Id. Install Microsoft App Installer, then run this command again."
    }
    & winget.exe install --id $Id --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installation failed: $Id (exit $LASTEXITCODE)" }
    Update-JjPath
}

function Get-LeiInstallTargets([string]$UserRoot = $env:USERPROFILE, [string]$ClaudeRoot = $env:CLAUDE_CONFIG_DIR) {
    $cliAgents = @('codex') # Skills CLI uses this for the shared .agents/skills directory.
    $nativeHosts = @()
    if (-not $ClaudeRoot) { $ClaudeRoot = Join-Path $UserRoot '.claude' }
    if (Test-Path -LiteralPath $ClaudeRoot -PathType Container) {
        $cliAgents += 'claude-code'
        $nativeHosts += [pscustomobject]@{ Name = 'claude-code'; Root = (Join-Path $ClaudeRoot 'skills') }
    }
    $workBuddyRoot = Join-Path $UserRoot '.workbuddy'
    if (Test-Path -LiteralPath $workBuddyRoot -PathType Container) {
        $nativeHosts += [pscustomobject]@{ Name = 'workbuddy'; Root = (Join-Path $workBuddyRoot 'skills') }
    }
    return [pscustomobject]@{
        SharedRoot = (Join-Path $UserRoot '.agents\skills')
        CliAgents = $cliAgents
        NativeHosts = $nativeHosts
    }
}

function Connect-LeiSkill([string]$Source, [string]$Target) {
    if (-not (Test-Path -LiteralPath (Join-Path $Source 'SKILL.md'))) { throw ('Missing source skill: ' + $Source) }
    $existing = Get-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.LinkType -and $existing.Target) {
            $current = [IO.Path]::GetFullPath([string](@($existing.Target)[0]))
            if ($current -eq [IO.Path]::GetFullPath($Source)) { return }
        }
        throw ('Existing client skill differs; preserved without replacement: ' + $Target)
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
    New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
}

Update-JjPath
$python = Find-JjPython
$leiTargets = Get-LeiInstallTargets
if ($CheckOnly) {
    [pscustomobject]@{
        Python312 = $python
        Npx = [bool](Get-Command npx.cmd -ErrorAction SilentlyContinue)
        Git = [bool](Get-Command git.exe -ErrorAction SilentlyContinue)
        Winget = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)
        Runtime = Get-LeiRuntime
        Skills = @('lei', 'jj', 'lei-doctor', 'lei-update')
        Repository = 'k9438324-hash/leiskill'
        SharedSkills = $leiTargets.SharedRoot
        NativeClients = @($leiTargets.NativeHosts | ForEach-Object { $_.Name })
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

Write-Host '[1/4] Backing up and installing leiskill...'
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'leiskill'
$backupRoot = Join-Path $runtimeRoot ('backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$skillsRoot = $leiTargets.SharedRoot
$backupHosts = @([pscustomobject]@{Name='shared';Root=$skillsRoot}) + @($leiTargets.NativeHosts)
foreach ($hostEntry in $backupHosts) {
    foreach ($skillName in @('lei', 'jj', 'lei-doctor', 'lei-update')) {
        $installed = Join-Path $hostEntry.Root $skillName
        if (Test-Path -LiteralPath $installed) {
            $hostBackup = Join-Path $backupRoot $hostEntry.Name
            New-Item -ItemType Directory -Path $hostBackup -Force | Out-Null
            Copy-Item -LiteralPath $installed -Destination (Join-Path $hostBackup $skillName) -Recurse -ErrorAction Stop
        }
    }
}
if (Test-Path -LiteralPath $backupRoot) { Write-Host ('Skill backup: ' + $backupRoot) }
$installArgs = @('-y','skills','add','k9438324-hash/leiskill','--skill','lei','jj','lei-doctor','lei-update','--agent') + @($leiTargets.CliAgents) + @('-g','-y')
& npx.cmd @installArgs
if ($LASTEXITCODE -ne 0) { throw ('leiskill installation failed. Existing backups: ' + $backupRoot) }
foreach ($hostEntry in $leiTargets.NativeHosts) {
    foreach ($skillName in @('lei', 'jj', 'lei-doctor', 'lei-update')) {
        $clientTarget = Join-Path $hostEntry.Root $skillName
        if ($hostEntry.Name -eq 'claude-code' -and (Test-Path -LiteralPath $clientTarget)) { continue }
        Connect-LeiSkill (Join-Path $skillsRoot $skillName) $clientTarget
    }
}

Write-Host '[2/4] Preparing an isolated Python environment...'
$runtimePython = Get-LeiRuntime
if (-not (Test-Path -LiteralPath $runtimePython)) {
    $venv = Join-Path $runtimeRoot 'venv'
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
$env:LEISKILL_PYTHON = $runtimePython
[Environment]::SetEnvironmentVariable('LEISKILL_PYTHON', $runtimePython, 'User')
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
@{ python = $runtimePython; repository = 'k9438324-hash/leiskill' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeRoot 'runtime.json') -Encoding UTF8

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
Write-Host 'SUCCESS: leiskill is installed and environment checks passed. Reload skills or restart your AI client, then use /lei or /jj (or ask for the video editing assistant). Draft playback/export still need verification.' -ForegroundColor Green
