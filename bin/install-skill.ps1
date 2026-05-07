# install-skill.ps1
# Install AgentTest as a user-level Claude Code skill.
# Copies claude-skill/agenttest/ -> $env:USERPROFILE\.claude\skills\agenttest\
# Idempotent: prompts before overwriting an existing install.
#
# Usage (from repo root):
#   .\bin\install-skill.ps1
#
# After install, in any Claude Code project:
#   /agenttest <relative-path-to-java-file>

$ErrorActionPreference = "Stop"

$src = Resolve-Path (Join-Path $PSScriptRoot "..\claude-skill\agenttest")
$dst = Join-Path $env:USERPROFILE ".claude\skills\agenttest"

if (-not (Test-Path $src)) {
    Write-Error "Skill source not found at $src"
    exit 1
}

if (Test-Path $dst) {
    Write-Host "Skill already installed at $dst"
    $resp = Read-Host "Overwrite? [y/N]"
    if ($resp -ne "y") {
        Write-Host "Aborted."
        exit 0
    }
    Remove-Item -Path $dst -Recurse -Force
}

$parent = Split-Path $dst -Parent
if (-not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

Copy-Item -Path $src -Destination $dst -Recurse -Force

Write-Host ""
Write-Host "Installed AgentTest skill to:"
Write-Host "  $dst"
Write-Host ""
Write-Host "In any Claude Code project, invoke with:"
Write-Host "  /agenttest <path-to-java-file>"
Write-Host ""
Write-Host "Note: skill is set to disable-model-invocation; only explicit"
Write-Host "/agenttest invocation triggers it (Claude won't auto-trigger)."
