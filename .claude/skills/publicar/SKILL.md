---
name: publicar
description: Publica en el servidor de Orión una página web o app web que hizo Orión (o una carpeta que David diga) y le da el link para verla. Úsala solo cuando David lo pide ("publícalo", "súbelo al servidor", "ponlo en internet", "dame el link"), o para quitar o listar lo publicado.
---

# Publicar una página

David lo pidió (2026-10-18): cuando un proyecto es una página web y dice "publícalo", Orión la sube al servidor y le da el link. Publicar es mostrarlo en internet: hazlo solo cuando David lo pide con sus palabras, nunca por tu cuenta ni desde la cola.

## 1. Qué publicar
- La página del último trabajo (la carpeta que dejaste en `boveda/outputs/` o el proyecto en `P:\` / `/mnt/p/`), o la carpeta que David nombre. Si no está claro cuál, busca en la bóveda el trabajo más reciente de páginas antes de preguntar.
- Solo archivos estáticos: HTML, CSS, JS, imágenes, fuentes. Si el proyecto tiene `package.json` con un script `build` (React, Vite, Next exportado...), construye primero: `npm ci` si falta `node_modules`, luego `npm run build`, y publica la carpeta que salga (`dist/`, `build/` u `out/`; el script la encuentra solo).
- Si la página necesita un servidor propio (Node con base de datos, PHP, Python), dile a David que eso no se publica así todavía y anótalo en `boveda/wiki/ideas-jarvis.md`.
- Antes de publicar, revisa que no lleve claves, tokens, `.env` ni datos privados (correos, teléfonos de terceros). Si los lleva, quítalos o pregunta.
- Si es tuya, que esté bien: si no la probaste, pruébala con `webapp-testing` y revisa el contraste con `ui-ux-pro-max`.

## 2. Publicar
```bash
python3 scripts/publicar_sitio.py <carpeta> --nombre <nombre-corto>
```
- `--nombre`: corto, en minúscula y con guiones (`angele`, `portafolio-david`). Con el mismo nombre se reemplaza la versión anterior, así que para "actualízala" usa el mismo.
- En el servidor escribe directo; en el PC la manda a la API del servidor. Imprime `Publicado (N archivos): https://sitios.<dominio>/<nombre>/`.
- Otros: `--lista` (lo publicado, en el servidor) y `--quitar <nombre>` (cuando David diga "quítala" o "despublícala").

## 3. Responder
Di que ya está y da el link completo tal cual lo imprimió el script (en la app y en WhatsApp se puede tocar). Guarda una línea en `boveda/wiki/proyectos/<proyecto>.md` (o en la nota del trabajo) con la fecha y el link.

Si el script falla:
- "No llego al servidor": revisa `JARVIS_SERVIDOR` y que el servidor esté encendido.
- 404 en el link: el servidor no tiene aún la parte de sitios; David debe correr una vez `./servidor/publicar.sh` en el servidor.
