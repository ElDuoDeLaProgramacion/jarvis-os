# Hace que el HUD y la voz de JARVIS arranquen solos al iniciar sesión en Windows.
# Crea dos tareas en el Programador de tareas, carpeta \JARVIS\Inicio\.
# Uso (PowerShell):  powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\instalar-inicio.ps1
param(
    [string]$Distro = "Ubuntu",
    [switch]$SinVoz
)

$repo = Split-Path $PSScriptRoot -Parent
$carpeta = "\JARVIS\Inicio\"
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$ajustes = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

function Registrar($nombre, $comando, $retraso) {
    $accion = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $comando"
    $disparador = New-ScheduledTaskTrigger -AtLogOn -User $usuario
    $disparador.Delay = $retraso
    Register-ScheduledTask -TaskPath $carpeta -TaskName $nombre -Action $accion `
        -Trigger $disparador -Settings $ajustes -Force | Out-Null
    Write-Host "OK  al iniciar sesión  ->  $nombre"
}

# El HUD espera 20 s para que Windows termine de arrancar; luego abre el navegador solo.
Registrar "HUD" "`"$repo\hud\abrir-hud.bat`" $Distro" "PT20S"

if (-not $SinVoz) {
    if (-not (Test-Path "$repo\voz\.venv")) {
        Write-Host "Aviso: la voz aún no está instalada. Ejecuta $repo\voz\instalar.bat antes de reiniciar."
    }
    # La voz queda en una ventana minimizada escuchando F9.
    Registrar "Voz" "start `"JARVIS voz`" /min `"$repo\voz\jarvis.bat`" --distro $Distro" "PT30S"
}

Write-Host ""
Write-Host "Listo. La próxima vez que inicies sesión, JARVIS arrancará solo."
Write-Host "Para probar ahora: Start-ScheduledTask -TaskPath '$carpeta' -TaskName 'HUD'"
