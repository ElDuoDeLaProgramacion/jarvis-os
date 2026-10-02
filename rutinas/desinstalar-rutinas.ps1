# Borra las tareas de JARVIS del Programador de tareas de Windows.
Get-ScheduledTask -TaskPath "\JARVIS\" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
Write-Host "Rutinas de JARVIS eliminadas."
