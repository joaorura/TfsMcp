[CmdletBinding()]
param(
    [string]$EnvironmentName = "mcp_tfs_env"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$modulePath = Join-Path $PSScriptRoot "TfsMcp.PowerShell.psm1"
Import-Module $modulePath -Force -DisableNameChecking

$projectRoot = Get-TfsMcpProjectRoot -StartPath $PSScriptRoot

if (-not $env:TFSMCP_STATE_DIR) {
    $env:TFSMCP_STATE_DIR = Join-Path $env:LOCALAPPDATA "TfsMcp"
}

# Keep the process attached to the MCP server lifecycle in this hidden PowerShell host.
$exitCode = Invoke-TfsMcpModule -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -ModuleName "tfsmcp"
exit $exitCode
