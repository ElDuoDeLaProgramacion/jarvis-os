# Hace que el HUD y la voz de JARVIS arranquen solos al iniciar sesión en Windows.
# Crea dos tareas en el Programador de tareas, carpeta \JARVIS\Inicio\.
# Uso (PowerShell):  powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\instalar-inicio.ps1
param(
    [string]$Distro = "Ubuntu",
    [switch]$SinVoz,
    [switch]$SinWhatsApp,
    [switch]$PantallaCompleta
)

$repo = Split-Path $PSScriptRoot -Parent
$carpeta = "\JARVIS\Inicio\"
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$ajustes = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

function Registrar($nombre, $programa, $argumentos, $retraso) {
    $accion = New-ScheduledTaskAction -Execute $programa -Argument $argumentos -WorkingDirectory $repo
    $disparador = New-ScheduledTaskTrigger -AtLogOn -User $usuario
    $disparador.Delay = $retraso
    Register-ScheduledTask -TaskPath $carpeta -TaskName $nombre -Action $accion `
        -Trigger $disparador -Settings $ajustes -Force | Out-Null
    Write-Host "OK  al iniciar sesión  ->  $nombre"
}

# El HUD es su propio programa (sin navegador ni consola). Espera 20 s a que Windows termine de arrancar.
if (-not (Test-Path "$repo\hud\.venv\Scripts\pythonw.exe")) {
    Write-Host "Aviso: el HUD aún no está instalado. Ejecuta $repo\hud\instalar.bat antes de reiniciar."
}
$argsHud = "`"$repo\hud\jarvis_hud.py`" --distro $Distro"
if ($PantallaCompleta) { $argsHud += " --pantalla-completa" }
Registrar "HUD" "$repo\hud\.venv\Scripts\pythonw.exe" $argsHud "PT20S"

if (-not $SinVoz) {
    if (-not (Test-Path "$repo\voz\.venv")) {
        Write-Host "Aviso: la voz aún no está instalada. Ejecuta $repo\voz\instalar.bat antes de reiniciar."
    }
    # La voz queda en una ventana minimizada escuchando "Jarvis" y los gestos.
    Registrar "Voz" "cmd.exe" "/c start `"JARVIS voz`" /min `"$repo\voz\jarvis.bat`" --distro $Distro" "PT30S"
}

# WhatsApp de JARVIS (whatsapp/README.md): solo si ya pusiste la clave de Kapso en .env.
$env_ = Get-Content "$repo\.env" -ErrorAction SilentlyContinue
if (-not $SinWhatsApp -and ($env_ -match '^KAPSO_API_KEY=.+')) {
    Registrar "WhatsApp" "cmd.exe" "/c start `"JARVIS WhatsApp`" /min wsl.exe -d $Distro --cd /mnt/p/jarvis-os --exec ./whatsapp/iniciar.sh" "PT40S"
} elseif (-not $SinWhatsApp) {
    Write-Host "WhatsApp: aún sin configurar (falta KAPSO_API_KEY en .env). Ver whatsapp\README.md."
}

Write-Host ""
Write-Host "Listo. La próxima vez que inicies sesión, JARVIS arrancará solo."
Write-Host "Para probar ahora: Start-ScheduledTask -TaskPath '$carpeta' -TaskName 'HUD'"
