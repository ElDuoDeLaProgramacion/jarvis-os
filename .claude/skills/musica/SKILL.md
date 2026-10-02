---
name: musica
description: Pone música en Spotify. Busca canciones, artistas, álbumes, listas o podcasts y los abre en el Spotify de David; también crea listas y guarda canciones. Úsala para "pon música de...", "reproduce...", "ponme algo para concentrarme", "qué está sonando" o "guarda esta canción".
---
# Música

## Fuente
- El conector **claude.ai Spotify**. Sus herramientas aparecen como `mcp__claude_ai_Spotify__...`: `search`, `get_currently_playing`, `generate_playlist` y `save_to_library`.
- El conector no puede darle play. Para que suene, la voz de JARVIS abre en Windows la dirección `spotify:...` que dejes en `cola/reproducir.txt`.
- Pausar, seguir, siguiente, anterior, volumen y "abre Spotify" los hace la voz al instante, sin llegar aquí.

## Poner algo
1. Busca con `search` lo que pidió David. Si pide un ambiente ("algo para concentrarme"), busca una lista que encaje.
2. Elige el mejor resultado. Prefiere una canción (`spotify:track:...`) cuando nombra una canción, y una lista o un álbum cuando pide un artista, un género o un ambiente.
3. Escribe con Write en `cola/reproducir.txt` solo esa dirección, por ejemplo `spotify:track:4uLU6hMCjMI75M1A2tKUQC`, sin nada más.
4. Responde en una frase qué pusiste: "Pongo Bohemian Rhapsody de Queen." Si es una lista o un álbum, añade: "Si no arranca solo, di: Jarvis, play."

## Otras peticiones
- "¿Qué está sonando?": `get_currently_playing` y responde canción y artista.
- "Guarda esta canción": `get_currently_playing` y luego `save_to_library`.
- "Hazme una lista de...": `generate_playlist` y di su nombre.
- Quitar canciones de la biblioteca no está permitido: dile a David que lo haga en Spotify.

## Reglas
- No guardes nada en la bóveda por poner música.
- Respuestas de una frase: David está escuchando música, no leyendo.
