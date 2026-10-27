# Orión Equipo

Un segundo Orión, separado del tuyo, para tus amigos de ciberseguridad: les hace de **senior** (explica, guía, revisa su trabajo, reparte roles) y de **pentester** sobre los objetivos que tú autorices del proyecto. Las revisiones pasivas corren solas; las pruebas activas esperan tu autorización desde tu panel. Al final, cada quien (y Orión) te deja un informe.

No es una "partición" del Orión de David, es otra instancia. Una partición dentro del mismo Orión dependería de que ningún bug ni ningún pedido ingenioso cruce la raya; aquí la raya la pone el sistema operativo: Orión Equipo **no tiene** tus llaves ni tus datos, así que no los puede filtrar aunque alguien lo intente.

## Qué tiene y qué no

| | Orión de David | Orión Equipo |
|---|---|---|
| Usuario Linux | `david` | `equipo` (sin sudo, sin SSH) |
| Código | tu copia del repo | `/opt/orion-equipo`: solo `equipo/` y `scripts/seguridad.sh`, de root, solo lectura. Sin tu bóveda ni tus habilidades. |
| Cuenta de Claude | la tuya (con Gmail, Calendar, Spotify...) | una **clave de API** propia del equipo con tope de gasto; los conectores de claude.ai se apagan |
| Bóveda | `boveda/` personal | `~equipo/espacio/boveda`, vacía al empezar |
| Correo, agenda, WhatsApp, billetera, Spotify, IAs externas, publicar sitios | sí | no existen aquí |
| Herramientas | muchas | leer/escribir en su espacio, web, `seguridad.sh` (pasivo) y `pentest.sh` (activo con tu autorización) |
| Objetivos de seguridad | `JARVIS_OBJETIVOS_SEGURIDAD` de tu `.env` | su propia lista en `~equipo/.env`, que editas tú. Ni `local` ni localhost. |
| Cómo se entra | voz, PC, app, tu WhatsApp | la **sala web**, usuario y contraseña por persona |
| Lo ves y controlas | — | tu **panel** en `/panel`: aprobar/rechazar pruebas activas, alertas, quitar gente, pausar |

Capas del aislamiento, de fuera hacia dentro:
1. **systemd encierra el servicio** (`orion-equipo.service`): el resto de `/home` no existe para él, el sistema es de solo lectura, no ve procesos de otros usuarios y no puede hablar con la red local (ni tu API en `127.0.0.1:7788`, ni Syncthing, ni Tailscale, ni la red interna del proveedor). Internet sí, para la web y los escaneos.
2. **Otro usuario** sin sudo: aunque saliera del encierro, tu carpeta es `750`.
3. **Claude con lista corta**: solo `Read` en su espacio, `Write/Edit` en su bóveda, web, `seguridad.sh` y `pentest.sh`. Sin MCP ni conectores. No tiene shell libre: las herramientas van por el harness, que comprueba el objetivo.
4. **Dos candados en el harness** (`pentest.sh`): (a) solo objetivos de tu lista `JARVIS_OBJETIVOS_SEGURIDAD`, nunca terceros; (b) las pruebas activas (nikto, sqlmap, fuzz, hydra...) quedan pendientes y te avisan al panel: corren solo cuando las apruebas, por el tiempo que elijas. Tú tienes botón de **pausa** para frenar todo.
5. **Reglas** (`plantilla/CLAUDE.md`, habilidades `mentor`, `qa-seguridad`, `informe`): los mismos candados escritos, nada de DoS sobre datos de clientes reales, y si alguien pide un objetivo fuera de la lista, Orión se niega y te deja la alerta.

## Dónde correrlo

- **En el mismo servidor, aislado (lo que hace `instalar.sh`)**: gratis, se monta en minutos y las capas de arriba bastan para un chat con Claude. Es lo recomendado para empezar.
- **En otro servidor (~4-8 €/mes)**: aislamiento total, ni siquiera comparten máquina. Pásate a esto si algún día quieres darles acceso de terminal (SSH) o correr herramientas intrusivas acordadas; en tu servidor nunca les des SSH.

## Instalar (en el servidor, con tu usuario)

```bash
cd ~/jarvis-os && git pull
./servidor/publicar.sh           # una vez, para que Caddy cargue sitios extra (conf.d)
./equipo/instalar.sh             # o: ./equipo/instalar.sh equipo.tudominio.com
sudo nano /home/equipo/.env      # ANTHROPIC_API_KEY y JARVIS_OBJETIVOS_SEGURIDAD
sudo systemctl restart orion-equipo
./equipo/admin.sh                # clave de tu panel + código de 6 dígitos (2 pasos)
./equipo/persona.sh agregar ana  # crea a 'ana' y te muestra su usuario y contraseña
```

Tu panel queda en `https://equipo.tudominio.com/panel`. Para poner además un login de Cloudflare delante, ver `equipo/CLOUDFLARE.md`.

- **Clave de API**: en console.anthropic.com crea un workspace "Orión Equipo", ponle un tope de gasto mensual y saca una clave ahí. No uses tu cuenta de Claude: compartirla con otras personas no está permitido y le daría al equipo tus conectores.
- **Objetivos**: solo dominios/IP tuyos del proyecto, separados por comas, por ejemplo `JARVIS_OBJETIVOS_SEGURIDAD=midominio.co,www.midominio.co,api.midominio.co`. Ni el equipo ni Orión pueden cambiarla.
- **Código para auditar**: `sudo cp -r <carpeta> /home/equipo/espacio/proyectos/ && sudo chown -R equipo: /home/equipo/espacio/proyectos` (sin `.env` ni secretos dentro).
- **Contexto del proyecto**: edita `/home/equipo/espacio/boveda/wiki/proyecto.md`.
- **Actualizar**: después de un `git pull`, vuelve a correr `./equipo/instalar.sh`. La bóveda del equipo no se toca; sus reglas y habilidades sí se renuevan.

## Gente

```bash
./equipo/persona.sh agregar luis    # crea a luis y muestra su usuario + contraseña (pásalos por privado)
./equipo/persona.sh clave luis      # le pone una contraseña nueva
./equipo/persona.sh quitar luis     # deja de entrar al instante
./equipo/persona.sh lista
```

Cada persona entra con su usuario y contraseña. Desde tu panel también puedes quitar a alguien (sale de inmediato). Cada quien tiene un tope de pedidos al día (`ORION_EQUIPO_LIMITE_DIA`, 40 por defecto). Tras 5 intentos fallidos, esa IP espera 15 minutos.

Todos ven la misma sala y Orión sabe quién habla ("ana: ..."). La conversación sigue 30 minutos después del último pedido.

## Tu panel (`/panel`)

Entras con la clave de `./equipo/admin.sh` y, si lo activaste, el código de 6 dígitos de tu app (Google/Microsoft Authenticator). Desde ahí:
- **Autorizaciones pendientes**: cada vez que el equipo pide una prueba activa, aparece aquí; la apruebas (eliges por cuántas horas) o la rechazas. Hasta entonces no corre.
- **Alertas**: lo que pasó, incluido si alguien pidió un objetivo fuera de la lista o algo activo.
- **Equipo**: quién está y cuántos pedidos lleva hoy; botón para quitar a alguien.
- **Pausa**: frena todas las pruebas activas de golpe.
- **Informes**: el de Orión y el de cada estudiante por sesión.

## Pentest y autorización

El equipo usa `pentest.sh` (lo maneja Orión). Las pruebas **pasivas** (recon, cabeceras, TLS, puertos, DNS) corren al momento. Las **activas** (nikto, sqlmap, directorios, fuzz, nmap-vuln, wpscan) y las **altas** (hydra, carga) quedan pendientes y te avisan al panel. Nada de esto toca un objetivo que no esté en tu lista, ni datos de clientes reales con pruebas destructivas. Para apuntar a un sistema nuevo, lo agregas tú a `JARVIS_OBJETIVOS_SEGURIDAD`.

## Informe por sesión

Al cerrar, cada estudiante entrega su informe (botón "Mi informe" en la sala, o se lo dicta a Orión) y Orión escribe el suyo. Todos te llegan al panel. Les sirve para la carrera: es justo lo que se entrega en un trabajo real.

## Revisar que está aislado

```bash
sudo systemd-analyze security orion-equipo         # puntuación del encierro
sudo -u equipo ls /home/david                       # Permission denied
journalctl -u orion-equipo -n 30
```

Desde la sala, prueba pedirle "lee el perfil de David", "escanea google.com" o "audita este servidor": debe negarse. Pídele un nikto a un objetivo tuyo: debe quedar **pendiente** en tu panel, no correr.

## Pendiente (según lo que decidan)

- **Grupo de WhatsApp** propio del equipo: necesita otro número vinculado (nunca el tuyo) y adaptar el puente para un grupo. Se puede añadir sobre esta misma instancia.
- Sesiones separadas por persona en vez de una sala común.
