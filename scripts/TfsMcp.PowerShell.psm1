Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-TfsMcpProjectRoot {
    [CmdletBinding()]
    param(
        [string]$StartPath = $PSScriptRoot
    )

    $resolvedStart = (Resolve-Path -Path $StartPath).Path
    $candidateRoot = [System.IO.Path]::GetFullPath((Join-Path $resolvedStart ".."))
    $marker = Join-Path $candidateRoot "pyproject.toml"

    if (-not (Test-Path -Path $marker)) {
        throw "Could not locate project root from '$StartPath'. Expected '$marker'."
    }

    return $candidateRoot
}

function Get-CondaExecutable {
    [CmdletBinding()]
    param()

    if ($env:CONDA_EXE -and (Test-Path -Path $env:CONDA_EXE)) {
        return $env:CONDA_EXE
    }

    $command = Get-Command -Name "conda" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $command) {
        return $command.Source
    }

    throw "Conda executable was not found. Activate Conda first or add it to PATH."
}

function Invoke-Conda {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $condaExe = Get-CondaExecutable
    Write-Host (">> conda " + ($Arguments -join " "))

    $shouldPop = $false
    if ($WorkingDirectory) {
        Push-Location -Path $WorkingDirectory
        $shouldPop = $true
    }

    try {
        & $condaExe @Arguments | Out-Host
        return [int]$LASTEXITCODE
    }
    finally {
        if ($shouldPop) {
            Pop-Location
        }
    }
}

function Test-CondaEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName
    )

    $condaExe = Get-CondaExecutable
    $rawJson = & $condaExe env list --json
    if ($LASTEXITCODE -ne 0) {
        throw "Could not list Conda environments (exit code $LASTEXITCODE)."
    }

    $result = $rawJson | ConvertFrom-Json
    foreach ($prefix in $result.envs) {
        if ((Split-Path -Path $prefix -Leaf) -ieq $EnvironmentName) {
            return $true
        }
    }

    return $false
}

function Ensure-TfsMcpCondaEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName,
        [string]$PythonVersion = "3.12"
    )

    if (Test-CondaEnvironment -EnvironmentName $EnvironmentName) {
        Write-Host "Conda environment '$EnvironmentName' already exists."
        return
    }

    $exitCode = Invoke-Conda -Arguments @("create", "-n", $EnvironmentName, "python=$PythonVersion", "-y")
    if ($exitCode -ne 0) {
        throw "Failed to create Conda environment '$EnvironmentName' (exit code $exitCode)."
    }
}

function Install-TfsMcpDependencies {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName,
        [Parameter(Mandatory)]
        [string]$ProjectRoot,
        [bool]$InstallDevDependencies = $true
    )

    $upgradePipCode = Invoke-Conda -Arguments @("run", "-n", $EnvironmentName, "python", "-m", "pip", "install", "--upgrade", "pip") -WorkingDirectory $ProjectRoot
    if ($upgradePipCode -ne 0) {
        throw "Failed to upgrade pip (exit code $upgradePipCode)."
    }

    $packageSpec = if ($InstallDevDependencies) { ".[dev]" } else { "." }
    $installCode = Invoke-Conda -Arguments @("run", "-n", $EnvironmentName, "python", "-m", "pip", "install", "-e", $packageSpec) -WorkingDirectory $ProjectRoot
    if ($installCode -ne 0) {
        throw "Failed to install project dependencies (exit code $installCode)."
    }
}

function Invoke-TfsMcpModule {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName,
        [Parameter(Mandatory)]
        [string]$ProjectRoot,
        [Parameter(Mandatory)]
        [string]$ModuleName,
        [string[]]$ModuleArguments = @()
    )

    $args = @("run", "-n", $EnvironmentName, "python", "-m", $ModuleName) + $ModuleArguments
    return Invoke-Conda -Arguments $args -WorkingDirectory $ProjectRoot
}

function Invoke-TfsMcpServiceCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName,
        [Parameter(Mandatory)]
        [string]$ProjectRoot,
        [Parameter(Mandatory)]
        [ValidateSet("install", "uninstall", "start", "stop", "restart", "status", "run")]
        [string]$Action
    )

    return Invoke-TfsMcpModule -EnvironmentName $EnvironmentName -ProjectRoot $ProjectRoot -ModuleName "tfsmcp.service" -ModuleArguments @($Action)
}

function Get-TfsMcpBackgroundPaths {
    [CmdletBinding()]
    param()

    $stateDir = Join-Path $env:LOCALAPPDATA "TfsMcp"
    $startupDir = [Environment]::GetFolderPath("Startup")
    return @{
        StateDir = $stateDir
        PidFile = Join-Path $stateDir "background.pid"
        StartupShortcut = Join-Path $startupDir "TfsMcp Background.lnk"
    }
}

function Get-TfsMcpBackgroundProcess {
    [CmdletBinding()]
    param()

    $paths = Get-TfsMcpBackgroundPaths
    if (-not (Test-Path -Path $paths.PidFile)) {
        return $null
    }

    $pidValue = (Get-Content -Path $paths.PidFile -Raw).Trim()
    if (-not $pidValue) {
        return $null
    }

    $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -Path $paths.PidFile -ErrorAction SilentlyContinue
        return $null
    }

    return $process
}

function Start-TfsMcpBackgroundProcess {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName,
        [Parameter(Mandatory)]
        [string]$ProjectRoot
    )

    $existing = Get-TfsMcpBackgroundProcess
    if ($null -ne $existing) {
        Write-Host "Background process already running (PID $($existing.Id))."
        return 0
    }

    $paths = Get-TfsMcpBackgroundPaths
    if (-not (Test-Path -Path $paths.StateDir)) {
        New-Item -ItemType Directory -Path $paths.StateDir -Force | Out-Null
    }

    $pwshPath = (Get-Command -Name "pwsh").Source
    $backgroundScript = Join-Path $ProjectRoot "scripts\Run-TfsMcpBackground.ps1"
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-File",
        $backgroundScript,
        "-EnvironmentName",
        $EnvironmentName
    )

    $proc = Start-Process -FilePath $pwshPath -ArgumentList $arguments -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden
    Set-Content -Path $paths.PidFile -Value $proc.Id -Encoding ascii
    Write-Host "Background process started (PID $($proc.Id))."
    return 0
}

function Stop-TfsMcpBackgroundProcess {
    [CmdletBinding()]
    param()

    $paths = Get-TfsMcpBackgroundPaths
    $process = Get-TfsMcpBackgroundProcess
    if ($null -eq $process) {
        Write-Host "Background process is not running."
        return 0
    }

    Stop-Process -Id $process.Id -Force
    Remove-Item -Path $paths.PidFile -ErrorAction SilentlyContinue
    Write-Host "Background process stopped (PID $($process.Id))."
    return 0
}

function Get-TfsMcpBackgroundStatus {
    [CmdletBinding()]
    param()

    $process = Get-TfsMcpBackgroundProcess
    if ($null -eq $process) {
        Write-Host "Background process status: stopped"
        return 0
    }

    Write-Host "Background process status: running (PID $($process.Id))"
    return 0
}

function Enable-TfsMcpStartupShortcut {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$EnvironmentName,
        [Parameter(Mandatory)]
        [string]$ProjectRoot
    )

    $paths = Get-TfsMcpBackgroundPaths
    $pwshPath = (Get-Command -Name "pwsh").Source
    $backgroundScript = Join-Path $ProjectRoot "scripts\Run-TfsMcpBackground.ps1"

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($paths.StartupShortcut)
    $shortcut.TargetPath = $pwshPath
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$backgroundScript`" -EnvironmentName `"$EnvironmentName`""
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Start TfsMcp in background"
    $shortcut.Save()

    Write-Host "Startup shortcut created at '$($paths.StartupShortcut)'."
    return 0
}

function Disable-TfsMcpStartupShortcut {
    [CmdletBinding()]
    param()

    $paths = Get-TfsMcpBackgroundPaths
    if (Test-Path -Path $paths.StartupShortcut) {
        Remove-Item -Path $paths.StartupShortcut -Force
        Write-Host "Startup shortcut removed from '$($paths.StartupShortcut)'."
        return 0
    }

    Write-Host "Startup shortcut is not present."
    return 0
}

function Get-TfsMcpStartupShortcutStatus {
    [CmdletBinding()]
    param()

    $paths = Get-TfsMcpBackgroundPaths
    if (Test-Path -Path $paths.StartupShortcut) {
        Write-Host "Startup shortcut status: enabled"
        Write-Host $paths.StartupShortcut
        return 0
    }

    Write-Host "Startup shortcut status: disabled"
    return 0
}

Export-ModuleMember -Function @(
    "Get-TfsMcpProjectRoot",
    "Get-CondaExecutable",
    "Invoke-Conda",
    "Test-CondaEnvironment",
    "Ensure-TfsMcpCondaEnvironment",
    "Install-TfsMcpDependencies",
    "Invoke-TfsMcpModule",
    "Invoke-TfsMcpServiceCommand",
    "Start-TfsMcpBackgroundProcess",
    "Stop-TfsMcpBackgroundProcess",
    "Get-TfsMcpBackgroundStatus",
    "Enable-TfsMcpStartupShortcut",
    "Disable-TfsMcpStartupShortcut",
    "Get-TfsMcpStartupShortcutStatus"
)
