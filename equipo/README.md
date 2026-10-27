# Orión Equipo

Un segundo Orión, separado del tuyo, para tus amigos de ciberseguridad: les hace de **senior** (explica, guía, revisa su trabajo, reparte tareas) y de **QA de seguridad de solo lectura** sobre los objetivos que tú autorices del proyecto.

No es una "partición" del Orión de David, es otra instancia. Una partición dentro del mismo Orión dependería de que ningún bug ni ningún pedido ingenioso cruce la raya; aquí la raya la pone el sistema operativo: Orión Equipo **no tiene** tus llaves ni tus datos, así que no los puede filtrar aunque alguien lo intente.

## Qué tiene y qué no

| | Orión de David | Orión Equipo |
|---|---|---|
| Usuario Linux | `david` | `equipo` (sin sudo, sin SSH) |
| Código | tu copia del repo | `/opt/orion-equipo`: solo `equipo/` y `scripts/seguridad.sh`, de root, solo lectura. Sin tu bóveda ni tus habilidades. |
| Cuenta de Claude | la tuya (con Gmail, Calendar, Spotify...) | una **clave de API** propia del equipo con tope de gasto; los conectores de claude.ai se apagan |
| Bóveda | `boveda/` personal | `~equipo/espacio/boveda`, vacía al empezar |
| Correo, agenda, WhatsApp, billetera, Spotify, IAs externas, publicar sitios | sí | no existen aquí |
| Herramientas | muchas | leer/escribir en su espacio, buscar en la web y `seguridad.sh` (web, puertos, dependencias, código) |
| Objetivos de seguridad | `JARVIS_OBJETIVOS_SEGURIDAD` de tu `.env` | su propia lista en `~equipo/.env`, que editas tú. Ni `local` ni localhost. |
| Cómo se entra | voz, PC, app, tu WhatsApp | la **sala web**, una clave por persona |

Capas del aislamiento, de fuera hacia dentro:
1. **systemd encierra el servicio** (`orion-equipo.service`): el resto de `/home` no existe para él, el sistema es de solo lectura, no ve procesos de otros usuarios y no puede hablar con la red local (ni tu API en `127.0.0.1:7788`, ni Syncthing, ni Tailscale, ni la red interna del proveedor). Internet sí, para la web y los escaneos.
2. **Otro usuario** sin sudo: aunque saliera del encierro, tu carpeta es `750`.
3. **Claude con lista corta**: solo `Read` dentro de su espacio, `Write/Edit` en su bóveda, web y el script de seguridad. Sin MCP ni conectores.
4. **Reglas** (`plantilla/CLAUDE.md`, habilidades `mentor` y `qa-seguridad`): solo lectura, solo objetivos de la lista, nada de exploits, fuerza bruta, fuzzing, carga ni terceros, aunque se lo pidan.

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
./equipo/persona.sh agregar ana  # imprime el enlace con la clave de Ana
```

- **Clave de API**: en console.anthropic.com crea un workspace "Orión Equipo", ponle un tope de gasto mensual y saca una clave ahí. No uses tu cuenta de Claude: compartirla con otras personas no está permitido y le daría al equipo tus conectores.
- **Objetivos**: solo dominios/IP tuyos del proyecto, separados por comas, por ejemplo `JARVIS_OBJETIVOS_SEGURIDAD=midominio.co,www.midominio.co,api.midominio.co`. Ni el equipo ni Orión pueden cambiarla.
- **Código para auditar**: `sudo cp -r <carpeta> /home/equipo/espacio/proyectos/ && sudo chown -R equipo: /home/equipo/espacio/proyectos` (sin `.env` ni secretos dentro).
- **Contexto del proyecto**: edita `/home/equipo/espacio/boveda/wiki/proyecto.md`.
- **Actualizar**: después de un `git pull`, vuelve a correr `./equipo/instalar.sh`. La bóveda del equipo no se toca; sus reglas y habilidades sí se renuevan.

## Gente

```bash
./equipo/persona.sh agregar luis    # enlace https://equipo.../#clave=...  (pásalo por privado)
./equipo/persona.sh quitar luis     # deja de entrar al instante
./equipo/persona.sh lista
```

La clave va en el fragmento del enlace (`#clave=`), que el navegador no envía al servidor; la sala la guarda en ese navegador. Cada persona tiene un tope de pedidos al día (`ORION_EQUIPO_LIMITE_DIA`, 40 por defecto). Tras 5 claves malas, esa IP espera 15 minutos.

Todos ven la misma sala y Orión sabe quién habla ("ana: ..."). La conversación sigue 30 minutos después del último pedido.

## Revisar que está aislado

```bash
sudo systemd-analyze security orion-equipo         # puntuación del encierro
sudo -u equipo ls /home/david                       # Permission denied
journalctl -u orion-equipo -n 30
```

Desde la sala, prueba pedirle "lee boveda/wiki/perfil.md de David", "escanea google.com" o "audita este servidor": debe negarse.

## Pendiente (según lo que decidan)

- **Grupo de WhatsApp** propio del equipo: necesita otro número vinculado (nunca el tuyo) y adaptar el puente para un grupo. Se puede añadir sobre esta misma instancia.
- Sesiones separadas por persona en vez de una sala común.
