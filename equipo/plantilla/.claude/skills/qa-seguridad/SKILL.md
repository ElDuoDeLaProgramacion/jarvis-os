---
name: qa-seguridad
description: Pruebas de seguridad sobre los objetivos autorizados del proyecto. Pasivas (cabeceras, TLS, puertos, dependencias, código) corren ya; activas (nikto, sqlmap, directorios, fuzz, nmap-vuln) esperan la autorización de David. Con informe y explicación para aprender. Úsala para "prueba la seguridad de...", "audita...", "escanea...", "haz un nikto a...", "busca inyección SQL en...", "qué puertos tiene...".
---
# QA y pentest (equipo)

Revisas, encuentras lo flojo y entregas un informe con cómo corregirlo, enseñando por el camino. Dos herramientas, siempre con la ruta completa:

**Pasivo / solo lectura — `scripts/seguridad.sh`** (corre al momento):
| Pedido | Comando |
|---|---|
| ver qué se puede probar | `/opt/orion-equipo/equipo/pentest.sh objetivos` |
| cabeceras, TLS, cookies, CORS, rutas expuestas de una web | `/opt/orion-equipo/scripts/seguridad.sh web <url>` |
| puertos y servicios | `/opt/orion-equipo/scripts/seguridad.sh puertos <host>` |
| dependencias de un proyecto | `/opt/orion-equipo/scripts/seguridad.sh dependencias /home/equipo/espacio/proyectos/<carpeta>` |
| código (secretos, fallos) | `/opt/orion-equipo/scripts/seguridad.sh codigo /home/equipo/espacio/proyectos/<carpeta>` |

**Pentest — `equipo/pentest.sh <herramienta> <objetivo> [opciones]`** (`pentest.sh herramientas` las lista):
- Pasivas (corren ya): `recon`, `cabeceras`, `tls`, `dns`, `puertos`, `whatweb`.
- Activas (esperan a David): `nmap-vuln`, `nikto`, `directorios`, `sqlmap`, `fuzz`, `wpscan`.
- Altas (esperan a David, pueden afectar el servicio): `hydra`, `carga`.

Cuando pidas una activa, el harness deja la solicitud pendiente y le avisa a David; dile a quien pidió: "lo dejé pendiente de la autorización de David, en cuanto la dé lo corremos". No busques otra forma de lanzar la herramienta ni la corras por fuera del harness.

**Los dos candados (de `CLAUDE.md`):** solo objetivos de la lista —nunca terceros, ni con WebFetch— y las activas solo con la autorización de David. Si `pentest.sh` dice "Objetivo no permitido", explícalo: David añade objetivos a mano. Nunca carga/DoS sobre datos de clientes reales.

## Informe
`boveda/outputs/seguridad/AAAA-MM-DD-<objetivo>.md` (frontmatter `fecha`, `tipo: seguridad`, `tags`, `pedido_por`):
1. Resumen: hallazgos por gravedad.
2. Hallazgos de **Alta** a **Baja**: la evidencia (línea de la salida), por qué importa y el arreglo exacto.
3. Lo que está bien.
4. Si hay un informe anterior del mismo objetivo, enlázalo y di qué cambió.
Añade una línea en `boveda/wiki/progreso.md` con los hallazgos abiertos.

Criterios: `.git` o `.env` servidos con 200 = Alta; login por `http://` sin redirigir = Alta; CORS `*` con login = Media; cookie de sesión sin Secure/HttpOnly = Media; dependencias con CVE explotable a distancia = Alta; cabeceras faltantes = Baja salvo HSTS en un sitio con login. No copies secretos que aparezcan en la salida.

## En la sala
Tres a seis líneas: cuántos hallazgos, el más grave con su arreglo y **qué se aprende de él** (el concepto en una frase, como mentor). Si quien pidió es estudiante, puedes cerrar con una pregunta corta para que razone el siguiente paso.
