[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet(
        "run",
        "background-start",
        "background-stop",
        "background-status",
        "startup-enable",
        "startup-disable",
        "startup-status",
        "service-install",
        "service-uninstall",
        "service-start",
        "service-stop",
        "service-restart",
        "service-status",
        "service-run"
    )]
    [string]$Command,
    [string]$EnvironmentName = "mcp_tfs_env",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$modulePath = Join-Path $PSScriptRoot "TfsMcp.PowerShell.psm1"
Import-Module $modulePath -Force -DisableNameChecking

$projectRoot = Get-TfsMcpProjectRoot -StartPath $PSScriptRoot

switch ($Command) {
    "run" {
        $exitCode = Invoke-TfsMcpModule -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -ModuleName "tfsmcp" -ModuleArguments $RemainingArguments
    }
    "background-start" {
        $exitCode = Start-TfsMcpBackgroundProcess -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot
    }
    "background-stop" {
        $exitCode = Stop-TfsMcpBackgroundProcess
    }
    "background-status" {
        $exitCode = Get-TfsMcpBackgroundStatus
    }
    "startup-enable" {
        $exitCode = Enable-TfsMcpStartupShortcut -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot
    }
    "startup-disable" {
        $exitCode = Disable-TfsMcpStartupShortcut
    }
    "startup-status" {
        $exitCode = Get-TfsMcpStartupShortcutStatus
    }
    "service-install" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "install"
    }
    "service-uninstall" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "uninstall"
    }
    "service-start" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "start"
    }
    "service-stop" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "stop"
    }
    "service-restart" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "restart"
    }
    "service-status" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "status"
    }
    "service-run" {
        $exitCode = Invoke-TfsMcpServiceCommand -EnvironmentName $EnvironmentName -ProjectRoot $projectRoot -Action "run"
    }
    default {
        throw "Unsupported command: $Command"
    }
}

exit $exitCode
