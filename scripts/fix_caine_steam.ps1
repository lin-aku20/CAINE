#requires -version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DesktopPath = [Environment]::GetFolderPath('Desktop')
$LogPath = Join-Path $DesktopPath 'CAINE_repair_log.txt'

function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet('INFO', 'WARNING', 'ERROR', 'SUCCESS', 'FAILURE')][string]$Level = 'INFO'
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[{0}] [{1}] {2}" -f $timestamp, $Level, $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ensure-Administrator {
    if (Test-IsAdministrator) {
        return
    }

    Write-Host 'Elevating script with administrator privileges...'
    $arguments = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-File', ('"{0}"' -f $PSCommandPath)
    )
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments
    exit
}

function Get-SteamInstallPath {
    $candidates = @(
        'C:\Program Files (x86)\Steam',
        'C:\Program Files\Steam',
        (Join-Path $env:LOCALAPPDATA 'Steam')
    )

    foreach ($path in $candidates) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        if (Test-Path $path) {
            return (Resolve-Path $path).Path
        }
    }

    try {
        $steamRegistry = Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam' -ErrorAction Stop
        if ($steamRegistry.SteamPath -and (Test-Path $steamRegistry.SteamPath)) {
            return (Resolve-Path $steamRegistry.SteamPath).Path
        }
    } catch {
    }

    return $null
}

function Stop-SteamProcesses {
    Write-Log 'Closing Steam-related processes.'

    $steamNames = @(
        'steam',
        'steamwebhelper',
        'steamservice',
        'gameoverlayui',
        'steamerrorreporter',
        'steammonitor',
        'steamtmp'
    )

    foreach ($name in $steamNames) {
        try {
            Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        } catch {
        }
    }

    try {
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match '^(steam|steamwebhelper|steamservice|gameoverlayui|steamerrorreporter)' -or
                $_.ExecutablePath -match '\\Steam\\'
            } |
            ForEach-Object {
                try {
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                } catch {
                }
            }
    } catch {
    }

    Start-Sleep -Milliseconds 1200
}

function Remove-PathSafely {
    param([string]$TargetPath)

    if ([string]::IsNullOrWhiteSpace($TargetPath)) { return }
    if (-not (Test-Path $TargetPath)) { return }

    try {
        Remove-Item -LiteralPath $TargetPath -Recurse -Force -ErrorAction Stop
        Write-Log "Removed: $TargetPath"
    } catch {
        Write-Log ("Failed to remove '{0}': {1}" -f $TargetPath, $_.Exception.Message) 'WARNING'
    }
}

function Clear-SteamCache {
    param([Parameter(Mandatory = $true)][string]$SteamPath)

    Write-Log "Cleaning Steam cache under $SteamPath"

    $pathsToClean = @(
        (Join-Path $SteamPath 'config\htmlcache'),
        (Join-Path $SteamPath 'config\GPUCache'),
        (Join-Path $SteamPath 'config\Cache'),
        (Join-Path $SteamPath 'userdata'),
        (Join-Path $env:LOCALAPPDATA 'Steam\htmlcache'),
        (Join-Path $env:LOCALAPPDATA 'Steam\GPUCache'),
        (Join-Path $env:LOCALAPPDATA 'Steam\Cache')
    )

    Remove-PathSafely -TargetPath (Join-Path $SteamPath 'config\htmlcache')
    Remove-PathSafely -TargetPath (Join-Path $SteamPath 'config\GPUCache')
    Remove-PathSafely -TargetPath (Join-Path $SteamPath 'config\Cache')
    Remove-PathSafely -TargetPath (Join-Path $env:LOCALAPPDATA 'Steam\htmlcache')
    Remove-PathSafely -TargetPath (Join-Path $env:LOCALAPPDATA 'Steam\GPUCache')
    Remove-PathSafely -TargetPath (Join-Path $env:LOCALAPPDATA 'Steam\Cache')

    $userDataPath = Join-Path $SteamPath 'userdata'
    if (Test-Path $userDataPath) {
        Get-ChildItem -Path $userDataPath -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-PathSafely -TargetPath (Join-Path $_.FullName 'config\htmlcache')
            Remove-PathSafely -TargetPath (Join-Path $_.FullName 'config\GPUCache')
            Remove-PathSafely -TargetPath (Join-Path $_.FullName 'config\Cache')
        }
    }
}

function Clear-UserTempFiles {
    Write-Log 'Cleaning user and Windows temporary directories.'

    $tempRoots = @(
        $env:TEMP,
        $env:TMP,
        (Join-Path $env:LOCALAPPDATA 'Temp'),
        'C:\Windows\Temp'
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

    foreach ($root in $tempRoots) {
        if (-not (Test-Path $root)) { continue }
        Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
            } catch {
            }
        }
        Write-Log "Processed temp directory: $root"
    }
}

function Restart-ExplorerSafely {
    Write-Log 'Restarting Explorer safely.'

    try {
        Get-Process -Name explorer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 1200
        Start-Process -FilePath 'explorer.exe'
    } catch {
        Write-Log ("Explorer restart issue: {0}" -f $_.Exception.Message) 'WARNING'
    }
}

function Start-SteamClean {
    param([Parameter(Mandatory = $true)][string]$SteamPath)

    $steamExe = Join-Path $SteamPath 'steam.exe'
    if (-not (Test-Path $steamExe)) {
        throw "steam.exe was not found in $SteamPath"
    }

    Write-Log "Launching Steam clean from $steamExe"
    Start-Process -FilePath $steamExe -ArgumentList '-no-cef-sandbox' -ErrorAction Stop
}

function Wait-ForSteamWebHelper {
    param([int]$TimeoutSeconds = 20)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $proc = Get-Process -Name steamwebhelper -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($proc) {
            return $true
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Write-CmdFallback {
    $cmdFallback = @'
CMD fallback commands:
taskkill /F /IM steam.exe /T
taskkill /F /IM steamwebhelper.exe /T
taskkill /F /IM gameoverlayui.exe /T
rd /s /q "%ProgramFiles(x86)%\Steam\config\htmlcache"
rd /s /q "%ProgramFiles(x86)%\Steam\config\GPUCache"
rd /s /q "%LOCALAPPDATA%\Steam\htmlcache"
rd /s /q "%LOCALAPPDATA%\Steam\GPUCache"
del /f /q "%TEMP%\*"
start "" explorer.exe
'@
    Add-Content -Path $LogPath -Value $cmdFallback -Encoding UTF8
}

try {
    "" | Set-Content -Path $LogPath -Encoding UTF8
    Ensure-Administrator
    Write-Log 'Starting CAINE Steam repair routine.'

    Write-Log 'Probable cause: corrupted Steam Chromium cache, stale steamwebhelper state, or broken helper startup loop.'

    $steamPath = Get-SteamInstallPath
    if (-not $steamPath) {
        throw 'Steam installation path was not found.'
    }

    Write-Log "Steam path detected: $steamPath"
    Stop-SteamProcesses
    Clear-SteamCache -SteamPath $steamPath
    Clear-UserTempFiles
    Restart-ExplorerSafely
    Start-SteamClean -SteamPath $steamPath

    if (Wait-ForSteamWebHelper -TimeoutSeconds 20) {
        Write-Log 'steamwebhelper.exe is running correctly.' 'SUCCESS'
        Write-CmdFallback
        Write-Host 'SUCCESS'
        exit 0
    }

    Write-Log 'steamwebhelper.exe did not recover within the timeout window.' 'FAILURE'
    Write-CmdFallback
    Write-Host 'FAILURE'
    exit 1
}
catch {
    Write-Log ("Repair failed: {0}" -f $_.Exception.Message) 'ERROR'
    Write-CmdFallback
    Write-Host 'FAILURE'
    exit 1
}
