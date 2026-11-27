param([string]$Branch = '', [switch]$Disable)
$ErrorActionPreference = 'Stop'
$rootDashboard = Split-Path -Parent $PSScriptRoot
$taskDashboard = 'Dashboard-Docker-AutoUpdate'
if ($Disable) {
    Disable-ScheduledTask -TaskName $taskDashboard | Out-Null
    Write-Output 'Actualización automática deshabilitada.'
    exit
}
if (-not $Branch) { $Branch = (& git -C $rootDashboard branch --show-current).Trim() }
if (-not $Branch) { throw 'Seleccione una rama con -Branch.' }
$remoteDashboard = (& git -C $rootDashboard remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0) { throw 'No se encontró el remoto origin.' }
& git -C $rootDashboard ls-remote --exit-code --heads origin $Branch | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'La rama todavía no está publicada en origin.' }
$pythonDashboard = Join-Path $rootDashboard '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonDashboard)) {
    throw 'Prepare el entorno Python .venv antes de registrar la tarea.'
}
$stateDashboard = Join-Path $rootDashboard '.cache\docker-auto'
New-Item -ItemType Directory -Path $stateDashboard -Force | Out-Null
$configDashboard = @{remote=$remoteDashboard; branch=$Branch} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $stateDashboard 'config.json'), $configDashboard, [Text.UTF8Encoding]::new($false))
$userDashboard = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$actionSettingsDashboard = @{
    Execute = $pythonDashboard
    Argument = '"' + (Join-Path $PSScriptRoot 'actualizar_docker.py') + '"'
    WorkingDirectory = $rootDashboard
}
$actionDashboard = New-ScheduledTaskAction @actionSettingsDashboard
$timerSettingsDashboard = @{
    Once = $true
    At = (Get-Date).AddMinutes(1)
    RepetitionInterval = (New-TimeSpan -Minutes 1)
}
$triggersDashboard = @(
    (New-ScheduledTaskTrigger @timerSettingsDashboard),
    (New-ScheduledTaskTrigger -AtLogOn -User $userDashboard)
)
$principalDashboard = New-ScheduledTaskPrincipal -UserId $userDashboard -LogonType Interactive -RunLevel Limited
$settingsParametersDashboard = @{
    MultipleInstances = 'IgnoreNew'
    StartWhenAvailable = $true
    AllowStartIfOnBatteries = $true
    DontStopIfGoingOnBatteries = $true
    ExecutionTimeLimit = (New-TimeSpan -Minutes 30)
}
$settingsDashboard = New-ScheduledTaskSettingsSet @settingsParametersDashboard
$taskParametersDashboard = @{
    TaskName = $taskDashboard
    Action = $actionDashboard
    Trigger = $triggersDashboard
    Principal = $principalDashboard
    Settings = $settingsDashboard
    Description = 'Actualiza Docker desde origin/' + $Branch
    Force = $true
}
Register-ScheduledTask @taskParametersDashboard | Out-Null
Write-Output "Actualización automática registrada para origin/$Branch."
