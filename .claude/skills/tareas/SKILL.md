---
name: tareas
description: Gestiona la lista de pendientes de David. Añadir, listar, completar o reprogramar tareas. Úsala para "anota la tarea", "qué tengo pendiente", "marca como hecho", "recuérdame hacer", "agenda...", "elimina del calendario...".
---
# Tareas

La lista vive en `boveda/wiki/tareas.md`, agrupada por área (Trabajo, Programación, Correo, Personal, Canales...).

Formato de cada línea:
```
- [ ] Texto de la tarea 📅 AAAA-MM-DD #area
```
(La fecha es opcional. Compatible con el plugin Tasks de Obsidian.)

- **Añadir**: agrega la línea bajo su área. Si no dice fecha, déjala sin fecha.
- **Listar**: muestra las abiertas; primero las vencidas, luego hoy, luego el resto.
- **Completar**: cambia `[ ]` por `[x]` y añade `✅ AAAA-MM-DD`.
- **Reprogramar**: cambia la fecha.

## En Google Calendar
Si David pide agendar algo, ponerlo en el calendario o "agrega el pendiente a Google Calendar":
1. Crea el evento con el conector **claude.ai Google Calendar** (`create_event`) en el calendario principal, hora de Bogotá. Si no dice hora, ponlo de día completo en la fecha de la tarea. Si dice cuánto antes avisar, añade el recordatorio.
2. Si viene de una tarea de `boveda/wiki/tareas.md`, deja la tarea como está y añádele ` 📆 en calendario`.
3. Mover o cambiar un evento (`update_event`) solo si David lo pide.
4. **Borrar un evento** ("elimina", "cancela", "quita del calendario"): búscalo y, sin borrar todavía, pregunta "¿Borro <título> del <día> a las <hora>? Sí o no." Si coincide más de uno, nómbralos y pregunta cuál. Solo en la respuesta "sí" de David tienes `delete_event`; bórralo entonces y confirma. Si la herramienta no está disponible, es que no hubo ese "sí": no insistas y dile que lo borre él. Nunca borres en rutinas ni varios eventos de una vez sin nombrarlos.

Responde en voz confirmando en una frase, o leyendo como máximo 5 tareas.
