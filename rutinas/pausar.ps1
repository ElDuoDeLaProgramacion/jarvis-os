# Pausa JARVIS en este PC sin borrar nada: desactiva el arranque automático (HUD, voz, WhatsApp)
# y la actualización cada 2 horas, y cierra lo que esté corriendo ahora.
# Las rutinas del día (\JARVIS\) siguen igual; añade -Rutinas para pausarlas también.
# Para volver a encenderlo: reanudar.ps1
# Uso (PowerShell):  powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\pausar.ps1
param(
    [switch]$Rutinas,
    [switch]$ApagarWSL
)

$carpetas = @("\JARVIS\Inicio\")
if ($Rutinas) { $carpetas += "\JARVIS\" }

foreach ($c in $carpetas) {
    Get-ScheduledTask -TaskPath $c -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-ScheduledTask -TaskPath $c -TaskName $_.TaskName -ErrorAction SilentlyContinue
        Disable-ScheduledTask -TaskPath $c -TaskName $_.TaskName | Out-Null
        Write-Host "Pausada  ->  $c$($_.TaskName)"
    }
}

# Cierra el HUD y la voz (con la cámara de gestos) si están abiertos.
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match 'jarvis_hud\.py|jarvis_voz\.py' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Cerrado  ->  $(if ($_.CommandLine -match 'jarvis_hud') { 'HUD' } else { 'voz y gestos' })"
    }

# WSL (vmmem) se queda encendido un rato tras cada rutina o actualización.
if ($ApagarWSL) {
    wsl.exe --shutdown
    Write-Host "WSL apagado."
}

Write-Host ""
Write-Host "JARVIS en pausa en este PC. Para encenderlo de nuevo:"
Write-Host "  powershell -ExecutionPolicy Bypass -File $PSScriptRoot\reanudar.ps1"
