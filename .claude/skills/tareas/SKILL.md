---
name: tareas
description: Gestiona la lista de pendientes de David. Añadir, listar, completar o reprogramar tareas. Úsala para "anota la tarea", "qué tengo pendiente", "marca como hecho", "recuérdame hacer".
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

Responde en voz confirmando en una frase, o leyendo como máximo 5 tareas.
