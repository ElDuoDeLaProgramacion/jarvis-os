# Rutinas del día real

| Hora | Rutina | Qué pide | Habilidad |
|---|---|---|---|
| 07:00 | Resumen matutino | "resumen matutino" | `resumen-dia` |
| 09:00 | Plan de hoy | "plan de hoy" | `plan` |
| 14:00 | Revisa pendientes | "revisa mis pendientes y los correos que esperan respuesta" | `tareas` + `correo` |
| 19:00 | Cierra el día | "cierra el día" | `cierre-dia` |

Usan el **Programador de tareas de Windows** (no cron dentro de WSL), porque WSL se apaga cuando cierras la terminal y Windows sí está siempre encendido. Cada tarea ejecuta `wsl.exe ... ./scripts/rutina.sh "<pedido>"`, que encola la intención y corre el corredor. El resultado queda en la bóveda (`boveda/outputs/`) y en `cola/hechas/`.

## Instalar

En PowerShell (no hace falta administrador):

```powershell
powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\instalar-rutinas.ps1
```

Si tu distribución de WSL no se llama `Ubuntu` (míralo con `wsl -l`), añade `-Distro "NombreExacto"`.

## Probar sin esperar a la hora

```powershell
Start-ScheduledTask -TaskPath "\JARVIS\" -TaskName "Plan de hoy"
```

O desde Ubuntu: `./scripts/rutina.sh "plan de hoy"`.

## Cambiar horas o pedidos

Edita `rutinas.csv` y vuelve a ejecutar `instalar-rutinas.ps1` (reemplaza las tareas existentes).

## Quitar

```powershell
powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\desinstalar-rutinas.ps1
```

## Arranque automático del HUD y la voz

Para que al iniciar sesión en Windows se abra el programa del HUD (su propia ventana, sin navegador) y la voz quede escuchando "Jarvis" y tus gestos (ventana minimizada):

```powershell
powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\instalar-inicio.ps1
```

- Instala antes el HUD (`hud\instalar.bat`) y la voz (`voz\instalar.bat`). Si solo quieres el HUD, añade `-SinVoz`.
- Para que el HUD ocupe toda la pantalla, añade `-PantallaCompleta`.
- Si tu distribución de WSL no se llama `Ubuntu`, añade `-Distro "NombreExacto"`.
- También crea la tarea **Actualizar**: al iniciar sesión y cada 2 horas trae lo nuevo de GitHub, sin `git pull` a mano (registro en `logs\actualizar.log`). Si no la quieres, añade `-SinActualizar`.
- Para quitarlo: `powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\desinstalar-inicio.ps1`

## Pausar JARVIS (por ejemplo, para cuidar la batería)

Desactiva el arranque automático y la actualización cada 2 horas sin borrar nada, y cierra el HUD y la voz (que usa la cámara para los gestos):

```powershell
powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\pausar.ps1
```

- Añade `-Rutinas` para pausar también las rutinas del día, y `-ApagarWSL` para apagar WSL (el proceso `vmmem`).
- Para volver a encenderlo: `powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\reanudar.ps1` (con `-Rutinas` si también las pausaste).
