# Cola de intenciones

Cada petición que no necesita respuesta inmediata (las rutinas, y más adelante los botones del HUD) se escribe aquí como un archivo Markdown, y el corredor las ejecuta una por una.

```
pendientes/  esperando turno
en-curso/    la que se está ejecutando ahora
hechas/      terminadas, con la respuesta de JARVIS al final
fallidas/    con error, con el mensaje al final
```

- Encolar: `./scripts/encolar.sh "plan de hoy"` (o desde el HUD)
- Ejecutar todo lo pendiente: `./scripts/corredor.sh`

El contenido de estas carpetas no se sube a git; lo que importa queda en la bóveda.

Si JARVIS se cierra a mitad de una intención, esta queda en `en-curso/`. El HUD lo nota y relanza el corredor; también lo hace la siguiente rutina:
- Si la intención tiene menos de 3 horas, se vuelve a ejecutar.
- Si es más vieja, pasa a `fallidas/` marcada como interrumpida.

Ninguna intención puede tardar más de 20 minutos.
