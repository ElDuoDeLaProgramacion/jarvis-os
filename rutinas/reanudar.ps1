# Vuelve a encender lo que pausó pausar.ps1: arranque automático y actualización cada 2 horas.
# Añade -Rutinas si también pausaste las rutinas del día.
# Uso (PowerShell):  powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\reanudar.ps1
param(
    [switch]$Rutinas
)

$carpetas = @("\JARVIS\Inicio\")
if ($Rutinas) { $carpetas += "\JARVIS\" }

foreach ($c in $carpetas) {
    Get-ScheduledTask -TaskPath $c -ErrorAction SilentlyContinue | ForEach-Object {
        Enable-ScheduledTask -TaskPath $c -TaskName $_.TaskName | Out-Null
        Write-Host "Activada  ->  $c$($_.TaskName)"
    }
}

Write-Host ""
Write-Host "Listo. JARVIS arrancará solo la próxima vez que inicies sesión."
Write-Host "Para abrirlo ya: Start-ScheduledTask -TaskPath '\JARVIS\Inicio\' -TaskName 'HUD'"
