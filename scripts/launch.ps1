param(
    [ValidateSet('Start', 'Stop')]
    [string]$Action = 'Start'
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

try {
    Write-Host ''
    Write-Host '  GLOBAL BANK TESTER' -ForegroundColor Cyan
    Write-Host '  Your local banking adventure'
    Write-Host ''

    $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
    $dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else { $null }
    $desktopCandidates = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
    )
    $desktopExecutable = $desktopCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $dockerExecutable) {
        $cliCandidates = @(
            "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
            "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
        )
        $dockerExecutable = $cliCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $dockerExecutable) {
        Write-Host 'One-time setup needed: install Docker Desktop for Windows.' -ForegroundColor Yellow
        Write-Host ''
        Write-Host 'Download and installation instructions:'
        Write-Host 'https://docs.docker.com/desktop/setup/install/windows-install/' -ForegroundColor Cyan
        Write-Host ''
        Write-Host 'Use the WSL 2 backend / Linux containers. Restart Windows if requested.'
        Write-Host 'Open Docker Desktop once and finish its setup.'
        Write-Host 'Then double-click Start Bank.cmd again. No Python or Node installation is needed.'
        exit 1
    }

    if ($Action -eq 'Stop') {
        Write-Host 'Stopping the lab. Your saved bank data will be kept.'
        & $dockerExecutable compose down
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop the lab. Check that Docker Desktop is running.' }
        Write-Host 'Stopped. You can close Docker Desktop when you are finished.' -ForegroundColor Green
        exit 0
    }

    function Get-DockerEngine {
        # Windows PowerShell 5 can treat native stderr as a terminating error
        # under Stop, even while probing an engine that is simply not running.
        $ErrorActionPreference = 'Continue'
        $engineType = & $dockerExecutable info --format '{{.OSType}}' 2>$null
        return @{ Running = ($LASTEXITCODE -eq 0); Type = $engineType }
    }

    Write-Host 'Checking Docker Desktop...'
    $engine = Get-DockerEngine
    if (-not $engine.Running) {
        if ($desktopExecutable) {
            Write-Host 'Starting Docker Desktop. This may take a minute...'
            Start-Process -FilePath $desktopExecutable -WindowStyle Hidden
        } else {
            throw 'Open Docker Desktop, wait for its engine to start, then double-click Start Bank.cmd again.'
        }
        $deadline = (Get-Date).AddMinutes(3)
        do {
            Start-Sleep -Seconds 3
            $engine = Get-DockerEngine
            if ($engine.Running) { break }
        } while ((Get-Date) -lt $deadline)
        if (-not $engine.Running) {
            throw 'Docker Desktop has not started. Open it and finish any WSL setup prompts, then try again.'
        }
    }
    if ($engine.Type -ne 'linux') {
        throw 'Docker is using Windows containers. Switch Docker Desktop to Linux containers, then try again.'
    }
    & $dockerExecutable compose version
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is missing. Install or update Docker Desktop.' }

    Write-Host ''
    Write-Host 'Starting the app and three databases...' -ForegroundColor Cyan
    Write-Host 'The first launch downloads and builds the app. Allow several minutes and keep this window open.'
    Write-Host 'Later launches reuse the downloaded files and build cache.'
    Write-Host ''
    & $dockerExecutable compose up --build -d
    if ($LASTEXITCODE -ne 0) {
        throw 'Startup failed. Read the Docker error above. The first launch needs an internet connection.'
    }

    Write-Host ''
    Write-Host 'Waiting for the app to be ready...'
    $ready = $false
    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $observed = Invoke-RestMethod -Uri 'http://localhost:3000/api/status' -TimeoutSec 20
            if ($observed.nodes.Count -eq 3 -and
                @($observed.nodes | Where-Object { -not $_.reachable -or $null -eq $_.network.isolated }).Count -eq 0) {
                $ready = $true
                break
            }
        } catch {
            # Containers can accept requests before MongoDB initialization completes.
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    if (-not $ready) {
        & $dockerExecutable compose ps -a
        & $dockerExecutable compose logs --tail 35 init api
        throw 'The lab did not become ready. Keep the errors above and check docs/troubleshooting.md.'
    }

    Write-Host 'Ready! Opening http://localhost:3000' -ForegroundColor Green
    Start-Process 'http://localhost:3000'
    Write-Host 'The lab keeps running after this window closes. Double-click Stop Bank.cmd to stop it.'
} catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
