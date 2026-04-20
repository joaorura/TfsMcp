[CmdletBinding()]
param(
    [string]$EnvironmentName = "mcp_tfs_env",
    [string]$PythonVersion = "3.12",
    [bool]$InstallDevDependencies = $true,
    [switch]$StartBackgroundNow,
    [switch]$DisablePatDialog,
    [switch]$ClearPat
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($ClearPat) {
    Write-Host "Clearing persistent TFSMCP_TFS_PAT environment variable..."
    [Environment]::SetEnvironmentVariable("TFSMCP_TFS_PAT", $null, "User")
    $env:TFSMCP_TFS_PAT = $null
}

if ($DisablePatDialog) {
    $env:TFSMCP_DISABLE_PAT_DIALOG = "true"
}

$modulePath = Join-Path $PSScriptRoot "TfsMcp.PowerShell.psm1"
Import-Module $modulePath -Force -DisableNameChecking

$projectRoot = Get-TfsMcpProjectRoot -StartPath $PSScriptRoot

Write-Host "Project root: $projectRoot"
Write-Host "Using Conda environment: $EnvironmentName"

Ensure-TfsMcpCondaEnvironment -EnvironmentName $EnvironmentName -PythonVersion $PythonVersion
Install-TfsMcpDependencies -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -InstallDevDependencies:$InstallDevDependencies

$enableCode = Enable-TfsMcpStartupShortcut -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -DisablePatDialog:$DisablePatDialog
if ($enableCode -ne 0) {
    throw "Failed to create Startup shortcut (exit code $enableCode)."
}

if ($StartBackgroundNow) {
    $startCode = Start-TfsMcpBackgroundProcess -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -DisablePatDialog:$DisablePatDialog
    if ($startCode -ne 0) {
        throw "Failed to start background process (exit code $startCode)."
    }
}

Get-TfsMcpStartupShortcutStatus | Out-Host
if ($StartBackgroundNow) {
    Get-TfsMcpBackgroundStatus | Out-Host
}

Write-Host "Startup setup finished successfully."
