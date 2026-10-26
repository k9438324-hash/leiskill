$ErrorActionPreference = 'Stop'
$installer = Join-Path (Split-Path -Parent $PSScriptRoot) 'install.ps1'
$parseErrors = $null
$tree = [System.Management.Automation.Language.Parser]::ParseFile($installer, [ref]$null, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
# Load helpers only. Never run global installation from this test.
foreach ($definition in $tree.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $false)) {
    . ([scriptblock]::Create($definition.Extent.Text))
}
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('leiskill-hosts-' + [guid]::NewGuid().ToString('N'))
$testRoot = [IO.Path]::GetFullPath($testRoot)
$link = Join-Path $testRoot 'user\.workbuddy\skills\jj'
try {
    $userRoot = Join-Path $testRoot 'user'
    New-Item -ItemType Directory -Path $userRoot -Force | Out-Null
    $empty = Get-LeiInstallTargets -UserRoot $userRoot -ClaudeRoot (Join-Path $userRoot '.claude')
    if (@($empty.NativeHosts).Count -ne 0) { throw 'Uninstalled clients must not be added.' }
    New-Item -ItemType Directory -Path (Join-Path $userRoot '.claude'), (Join-Path $userRoot '.workbuddy') -Force | Out-Null
    $found = Get-LeiInstallTargets -UserRoot $userRoot -ClaudeRoot (Join-Path $userRoot '.claude')
    if (@($found.NativeHosts).Count -ne 2 -or $found.CliAgents -notcontains 'claude-code') { throw 'Existing clients were not detected.' }
    $customClaude = Join-Path $testRoot 'custom-claude'
    New-Item -ItemType Directory -Path $customClaude -Force | Out-Null
    $custom = Get-LeiInstallTargets -UserRoot $userRoot -ClaudeRoot $customClaude
    if (($custom.NativeHosts | Where-Object {$_.Name -eq 'claude-code'}).Root -ne (Join-Path $customClaude 'skills')) { throw 'Custom Claude config was ignored.' }
    $source = Join-Path $testRoot 'source\jj'
    New-Item -ItemType Directory -Path $source -Force | Out-Null
    'test skill' | Set-Content -LiteralPath (Join-Path $source 'SKILL.md')
    Connect-LeiSkill $source $link
    if (-not (Test-Path -LiteralPath (Join-Path $link 'SKILL.md'))) { throw 'Native skill link is not usable.' }
    Connect-LeiSkill $source $link
    $conflict = Join-Path $testRoot 'existing\jj'
    New-Item -ItemType Directory -Path $conflict -Force | Out-Null
    'keep this file' | Set-Content -LiteralPath (Join-Path $conflict 'SKILL.md')
    $refused = $false
    try { Connect-LeiSkill $source $conflict } catch {
        if ($_.Exception.Message -match 'preserved without replacement') { $refused = $true } else { throw }
    }
    if (-not $refused -or (Get-Content -LiteralPath (Join-Path $conflict 'SKILL.md')) -ne 'keep this file') { throw 'Conflicting skill was not preserved.' }
    Write-Output 'PASS: absent clients skipped, installed clients detected, custom Claude path, usable junction, repeat installation, conflict preserved.'
} finally {
    if (Test-Path -LiteralPath $link) { [IO.Directory]::Delete($link) }
    $allowed = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $testRoot.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $testRoot) -notmatch '^leiskill-hosts-[a-f0-9]{32}$') { throw 'Unsafe cleanup target.' }
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}
