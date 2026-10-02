---
name: programacion
description: Tareas de programación en los proyectos de David. Explicar código, arreglar errores, crear scripts, revisar el estado de un repo, correr pruebas. Úsala para cualquier petición sobre código, repositorios, errores, scripts o proyectos de software.
---
# Programación

## Dónde
- Los proyectos están en `P:\` (`/mnt/p` en WSL) y listados en "Proyectos" de `boveda/wiki/perfil.md`.
- Cualquier proyecto nuevo se crea en `/mnt/p`.
- Si David nombra un proyecto, trabaja dentro de esa carpeta y lee su README y CLAUDE.md primero.

## Cómo
1. **Entiende antes de tocar**: lee los archivos relevantes y el `git status`.
2. **Cambios**: trabaja en una rama nueva (`jarvis/<tema>`), nunca directo en main. Haz cambios pequeños.
3. **Verifica**: corre las pruebas o el linter del proyecto si existen. Si no hay, ejecuta el código al menos una vez.
4. **Registra**: escribe `boveda/outputs/programacion/AAAA-MM-DD-<proyecto>-<tema>.md` con qué cambió, por qué y cómo se probó.
5. No hagas push, merge ni despliegues sin confirmación de David.

## Proyecto nuevo ("hazme un proyecto de...")
1. Crea la carpeta en `/mnt/p/<Nombre-Del-Proyecto>` (pregunta el nombre solo si David no dio ninguno y no se deduce).
2. Dentro: `README.md` (qué es y cómo correrlo), `.gitignore` del lenguaje y el esqueleto mínimo que funcione.
3. `git init`, `git checkout -b main` si hace falta, `git add` y un primer `git commit`.
4. Pruébalo una vez y añade el proyecto a "Proyectos" en `boveda/wiki/perfil.md`.
5. El repositorio en GitHub no lo creas tú (publicar necesita a David): deja en el README y en la nota de `outputs/programacion/` los dos comandos para subirlo cuando él cree el repo vacío en github.com (`git remote add origin <url>` y `git push -u origin main`), y díselo en una frase.

## Respuesta hablada
Di qué hiciste y si las pruebas pasaron, en dos frases. Nunca leas código en voz alta: di dónde está.
