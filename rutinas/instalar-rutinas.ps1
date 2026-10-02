# Crea en el Programador de tareas de Windows una tarea por cada línea de rutinas.csv.
# Cada tarea abre WSL, encola la intención y ejecuta el corredor.
# Uso (PowerShell):  powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\instalar-rutinas.ps1
param(
    [string]$Distro = "Ubuntu",
    [string]$Repo = "/mnt/p/jarvis-os"
)

$carpeta = "\JARVIS\"
$rutinas = Import-Csv (Join-Path $PSScriptRoot "rutinas.csv")

foreach ($r in $rutinas) {
    $argumentos = "-d $Distro --cd $Repo --exec ./scripts/rutina.sh `"$($r.pedido)`""
    $accion = New-ScheduledTaskAction -Execute "wsl.exe" -Argument $argumentos
    $disparador = New-ScheduledTaskTrigger -Daily -At $r.hora
    # Si el PC estaba apagado a esa hora, la rutina corre en cuanto se encienda.
    $ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

    Register-ScheduledTask -TaskPath $carpeta -TaskName $r.nombre `
        -Action $accion -Trigger $disparador -Settings $ajustes -Force | Out-Null
    Write-Host "OK  $($r.hora)  $($r.nombre)  ->  $($r.pedido)"
}

Write-Host ""
Write-Host "Listo. Las verás en el Programador de tareas, carpeta JARVIS."
Write-Host "Para probar una ya: Start-ScheduledTask -TaskPath '$carpeta' -TaskName 'Plan de hoy'"
