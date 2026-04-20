[CmdletBinding()]
param(
    [string]$EnvironmentName = "mcp_tfs_env",
    [switch]$DisablePatDialog
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($DisablePatDialog) {
    $env:TFSMCP_DISABLE_PAT_DIALOG = "true"
}

$modulePath = Join-Path $PSScriptRoot "TfsMcp.PowerShell.psm1"
Import-Module $modulePath -Force -DisableNameChecking

$projectRoot = Get-TfsMcpProjectRoot -StartPath $PSScriptRoot

if (-not $env:TFSMCP_STATE_DIR) {
    $env:TFSMCP_STATE_DIR = Join-Path $env:LOCALAPPDATA "TfsMcp"
}

# Prefer launching module directly with the target environment Python.
$condaExe = Get-CondaExecutable
$condaRoot = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetDirectoryName($condaExe))
$envPython = Join-Path (Join-Path $condaRoot "envs\$EnvironmentName") "python.exe"

if (Test-Path -Path $envPython) {
    Push-Location -Path $projectRoot
    try {
        & $envPython -m tfsmcp
        exit [int]$LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

# Fallback to conda-run module invocation if direct python is unavailable.
$exitCode = Invoke-TfsMcpModule -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -ModuleName "tfsmcp"
exit $exitCode
