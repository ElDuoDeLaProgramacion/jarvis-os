# Quita el arranque automático del HUD y la voz (las rutinas de 7, 9, 14 y 19 h no se tocan).
Get-ScheduledTask -TaskPath "\JARVIS\Inicio\" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
Write-Host "Arranque automático de JARVIS eliminado."
