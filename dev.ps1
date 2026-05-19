$nodePath = 'C:\Program Files\nodejs'

if (-not (Test-Path "$nodePath\npm.cmd")) {
    Write-Error "No encontre npm en $nodePath. Reinstala Node.js o revisa la ruta."
    exit 1
}

$env:PATH = "$nodePath;$env:PATH"
& "$nodePath\npm.cmd" run dev
