[CmdletBinding()]
param(
    [string]$EnvironmentName = "mcp_tfs_env",
    [string]$PythonVersion = "3.12",
    [bool]$InstallDevDependencies = $true,
    [switch]$InstallWindowsService,
    [switch]$StartWindowsService
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

if ($InstallWindowsService) {
    $installCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "install"
    if ($installCode -ne 0) {
        throw "Windows service installation failed (exit code $installCode)."
    }
}

if ($StartWindowsService) {
    $startCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "start"
    if ($startCode -ne 0) {
        throw "Windows service start failed (exit code $startCode)."
    }
}

Write-Host "Installation finished successfully."
Write-Host "Run script mode: .\\scripts\\Manage-TfsMcp.ps1 -Command run"
Write-Host "Check service: .\\scripts\\Manage-TfsMcp.ps1 -Command service-status"
