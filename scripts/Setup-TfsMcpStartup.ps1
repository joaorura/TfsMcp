[CmdletBinding()]
param(
    [string]$EnvironmentName = "mcp_tfs_env",
    [string]$PythonVersion = "3.12",
    [bool]$InstallDevDependencies = $true,
    [switch]$StartBackgroundNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$modulePath = Join-Path $PSScriptRoot "TfsMcp.PowerShell.psm1"
Import-Module $modulePath -Force -DisableNameChecking

$projectRoot = Get-TfsMcpProjectRoot -StartPath $PSScriptRoot

Write-Host "Project root: $projectRoot"
Write-Host "Using Conda environment: $EnvironmentName"

Ensure-TfsMcpCondaEnvironment -EnvironmentName $EnvironmentName -PythonVersion $PythonVersion
Install-TfsMcpDependencies -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -InstallDevDependencies:$InstallDevDependencies

$enableCode = Enable-TfsMcpStartupShortcut -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot
if ($enableCode -ne 0) {
    throw "Failed to create Startup shortcut (exit code $enableCode)."
}

if ($StartBackgroundNow) {
    $startCode = Start-TfsMcpBackgroundProcess -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot
    if ($startCode -ne 0) {
        throw "Failed to start background process (exit code $startCode)."
    }
}

Get-TfsMcpStartupShortcutStatus | Out-Host
if ($StartBackgroundNow) {
    Get-TfsMcpBackgroundStatus | Out-Host
}

Write-Host "Startup setup finished successfully."
