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

# Verify source exists BEFORE Resolve-Path (which would throw a stack trace
# under -ErrorAction Stop, bypassing the friendly error message).
$srcPath = Join-Path $PSScriptRoot "..\claude-skill\agenttest"
if (-not (Test-Path $srcPath)) {
    Write-Error "Skill source not found at $srcPath"
    exit 1
}
$src = Resolve-Path $srcPath
$dst = Join-Path $env:USERPROFILE ".claude\skills\agenttest"

if (Test-Path $dst) {
    Write-Host "Skill already installed at $dst"
    $resp = Read-Host "Overwrite? [y/N]"
    if ($resp -ne "y") {
        Write-Host "Aborted."
        exit 0
    }
    Remove-Item -Path $dst -Recurse -Force
}

# Ensure destination exists, then copy CONTENTS of $src into $dst (using
# `\*` glob). Without the glob, PowerShell's Copy-Item with a non-existent
# destination can either: (a) create $dst and copy contents in (correct),
# or (b) create $dst and copy the source folder as a child, yielding
# ~\.claude\skills\agenttest\agenttest\ (broken). The `\*` form is
# unambiguous.
New-Item -ItemType Directory -Path $dst -Force | Out-Null
Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force

Write-Host ""
Write-Host "Installed AgentTest skill to:"
Write-Host "  $dst"
Write-Host ""
Write-Host "In any Claude Code project, invoke with:"
Write-Host "  /agenttest <path-to-java-file>"
Write-Host ""
Write-Host "Note: skill is set to disable-model-invocation; only explicit"
Write-Host "/agenttest invocation triggers it (Claude won't auto-trigger)."
