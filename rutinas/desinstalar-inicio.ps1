# Quita el arranque automático del HUD y la voz.
Get-ScheduledTask -TaskPath "\JARVIS\Inicio\" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
Write-Host "Arranque automático de JARVIS eliminado."
