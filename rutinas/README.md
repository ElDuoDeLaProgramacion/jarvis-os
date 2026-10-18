# Arranque automático en Windows

Las rutinas de horario (resumen matutino, plan, pendientes, cierre, noticias, aprender) se quitaron: casi nunca hablaban sin que se lo pidieras y gastaban uso. Pídeselas a Orión cuando quieras. `scripts/actualizar.sh` borra una vez las tareas viejas de la carpeta `\JARVIS\` del Programador de tareas; si quieres hacerlo a mano: `powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\desinstalar-rutinas.ps1`.

## Arranque automático del HUD y la voz

Para que al iniciar sesión en Windows se abra el programa del HUD (su propia ventana, sin navegador) y la voz quede escuchando "Orión" y tus gestos (ventana minimizada):

```powershell
powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\instalar-inicio.ps1
```

- Instala antes el HUD (`hud\instalar.bat`) y la voz (`voz\instalar.bat`). Si solo quieres el HUD, añade `-SinVoz`.
- Para que el HUD ocupe toda la pantalla, añade `-PantallaCompleta`.
- Si tu distribución de WSL no se llama `Ubuntu`, añade `-Distro "NombreExacto"`.
- También crea la tarea **Actualizar**: al iniciar sesión y cada 2 horas trae lo nuevo de GitHub, sin `git pull` a mano (registro en `logs\actualizar.log`). Si no la quieres, añade `-SinActualizar`.
- Para quitarlo: `powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\desinstalar-inicio.ps1`

## Pausar Orión (por ejemplo, para cuidar la batería)

Desactiva el arranque automático y la actualización cada 2 horas sin borrar nada, y cierra el HUD y la voz (que usa la cámara para los gestos):

```powershell
powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\pausar.ps1
```

- Añade `-Rutinas` para pausar también las rutinas del día, y `-ApagarWSL` para apagar WSL (el proceso `vmmem`).
- Para volver a encenderlo: `powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\reanudar.ps1` (con `-Rutinas` si también las pausaste).
