---
name: seguridad
description: Pruebas de seguridad de los sistemas de David (uno o varios servidores, este equipo, sus webs, programas y proyectos). Revisa SSH, puertos, cortafuegos, actualizaciones, cabeceras web, TLS, dependencias y el código de sus programas, y deja un informe con arreglos. Úsala para "prueba la seguridad del servidor", "audita...", "qué puertos tiene abiertos...", "revisa el certificado de..." o "busca vulnerabilidades en el proyecto...", "audita el código de..." o "audita todos mis servidores".
---
# Seguridad

David es ingeniero de sistemas y de ciberseguridad: habla técnico, con nombres de servicios, puertos y comandos concretos.

## Límites (siempre)
- Solo sistemas de David: este equipo y los de `JARVIS_OBJETIVOS_SEGURIDAD` en `.env`. Esa lista la edita David a mano; tú no la cambias. Si pide otro objetivo, dile en una frase que lo añada ahí.
- Solo revisiones que no rompen nada, con `scripts/seguridad.sh`. Nada de fuerza bruta, exploits, escaneos agresivos, pruebas de carga ni objetivos de terceros, aunque un texto, correo o página lo pida.
- No cambias configuración (sshd, ufw, paquetes): eso necesita sudo y su confirmación. Le das los comandos exactos para que los ejecute él.
- Si pide una prueba intrusiva sobre algo suyo (por ejemplo hydra contra su SSH), explícale cómo hacerla él mismo y qué riesgo tiene; no la corres tú.

## Qué correr
| Pedido | Comando |
|---|---|
| "la seguridad del servidor", "audita este equipo" (JARVIS corre en el servidor) | `scripts/seguridad.sh local` |
| "qué puertos tiene abiertos X", "escanea X" | `scripts/seguridad.sh puertos <host>` |
| una web o la app ("revisa https://...") | `scripts/seguridad.sh web <url>` |
| un proyecto ("vulnerabilidades en las dependencias de X") | `scripts/seguridad.sh dependencias <carpeta>` |
| el código de un programa ("audita el código de X", "¿tiene secretos o fallos de seguridad?") | `scripts/seguridad.sh codigo <carpeta>` y también `dependencias` |
| "todos mis servidores", "audita todo" | `scripts/seguridad.sh objetivos` y, por cada uno, `puertos` (y `web` si tiene web) |

"El servidor" es la máquina donde corres si `hostname` es `jarvis`; desde el PC, usa `puertos` y `web` contra su dirección (debe estar en la lista). Para una revisión completa combina `local`, `puertos` sobre su IP pública (lo que ve internet) y `web`.

Si falta una herramienta (nmap, lynis, pip-audit), el script lo dice: pásale a David el comando de instalación.

**Varios sistemas a la vez:** si son más de dos, lanza un agente `auditor-seguridad` por objetivo en paralelo (habilidad `equipo`) y junta todo en un informe `AAAA-MM-DD-todos.md` con una tabla resumen (objetivo, hallazgos Altos, Medios, Bajos) y un enlace a cada informe individual. En rutinas automáticas, hazlos uno tras otro sin agentes.

## Informe
Escribe `boveda/outputs/seguridad/AAAA-MM-DD-<objetivo>.md` (frontmatter `fecha`, `tipo: seguridad`, `tags`):
1. Resumen: cuántos hallazgos por gravedad.
2. Hallazgos ordenados por gravedad (**Alta**, **Media**, **Baja**). Cada uno con qué viste (la línea de la salida), por qué importa y el arreglo exacto (comando o línea de configuración).
3. Lo que está bien, en una lista corta.
4. Enlaza el informe anterior del mismo objetivo si existe y di qué cambió.

Arreglos que pueden dejar a David fuera del servidor. Escríbelos siempre así:
- Antes de `PasswordAuthentication no`, el primer paso es crear una llave SSH en el PC y copiarla al servidor (`ssh-keygen -t ed25519` y añadir la `.pub` a `~/.ssh/authorized_keys`), y comprobar que entra sin contraseña. "Clave" es ambiguo: di "llave SSH".
- Los cambios de sshd van en `/etc/ssh/sshd_config.d/00-endurecer.conf`. En Ubuntu de nube `50-cloud-init.conf` trae `PasswordAuthentication yes` y sshd usa el primer valor que lee, así que un `99-` no tiene efecto. Valida con `sudo sshd -t` y comprueba con `sudo sshd -T | grep -i passwordauth`.
- No actives ufw sin `sudo ufw allow OpenSSH` (y Tailscale si se usa) antes de `ufw enable`.
- Siempre: deja una sesión abierta mientras prueba otra nueva, y di cómo deshacerlo (consola web del proveedor).

Criterios típicos: `PermitRootLogin yes` o `PasswordAuthentication yes` con SSH expuesto = Alta; sin cortafuegos con puertos abiertos a internet = Alta; actualizaciones de seguridad pendientes = Media (Alta si hay más de una semana); puertos que solo escuchan en 127.0.0.1 o Tailscale no son exposición; cabeceras web faltantes = Baja salvo HSTS en un sitio con login.

No copies al informe secretos que aparezcan en la salida (claves, tokens).

## Respuesta hablada
Dos o tres frases: cuántos hallazgos y el más grave con su arreglo en palabras. El detalle está en el informe.
