# Ejecutar como administrador en la computadora que aloja el dashboard.
$nombreRegla = 'Dashboard Facturacion - TCP 8009 red local'
$identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identidad)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error 'Abra PowerShell como administrador para configurar el firewall.'
    exit 1
}
$existentes = @(Get-NetFirewallRule -DisplayName $nombreRegla -ErrorAction SilentlyContinue)
if ($existentes.Count -gt 0) {
    Write-Output 'Ya existe una regla con ese nombre. Verifique su configuración antes de crear otra.'
    $existentes | Get-NetFirewallPortFilter | Format-List
    exit 0
}
New-NetFirewallRule -DisplayName $nombreRegla -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort 8009 -Profile Domain,Private -RemoteAddress LocalSubnet -ErrorAction Stop | Out-Null
Write-Output 'Regla creada para TCP 8009 desde la subred local en redes de dominio y privadas.'
Write-Output 'Si una política de la empresa bloquea reglas locales, debe habilitarla el administrador de la red.'
