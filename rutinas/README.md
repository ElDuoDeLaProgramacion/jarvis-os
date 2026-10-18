# Arranque automático en Windows

Las rutinas de horario (resumen matutino, plan, pendientes, cierre, noticias, aprender) se quitaron: casi nunca hablaban sin que se lo pidieras y gastaban uso. Pídeselas a JARVIS cuando quieras. `scripts/actualizar.sh` borra una vez las tareas viejas de la carpeta `\JARVIS\` del Programador de tareas; si quieres hacerlo a mano: `powershell -ExecutionPolicy Bypass -File P:\jarvis-os\rutinas\desinstalar-rutinas.ps1`.

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
