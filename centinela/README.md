# Centinela de Orión

Vigila el servidor cada minuto, se defiende solo con cosas que se pueden deshacer y te avisa por WhatsApp
(en tu chat contigo mismo, como el resto de Orión).

## Activarlo (una vez, en el servidor)
```bash
cd ~/jarvis-os
./scripts/actualizar.sh
./centinela/instalar.sh            # bloquea solo y avisa
# o, para probar unos días sin que bloquee nada:
./centinela/instalar.sh avisar
```
Hazlo **por SSH desde tu casa**: tu IP de ese momento queda permitida para siempre. En un minuto te llega
"Centinela encendido" por WhatsApp.

## Qué vigila y qué hace
| Qué ve | Qué hace solo | Aviso |
|---|---|---|
| 8 claves SSH malas en 10 min desde una IP | Bloquea la IP 1 h (24 h si reincide en la semana) | ⚠️ |
| Entrada SSH buena desde una IP nueva | La marca de confianza 3 días (para no bloquearte nunca) | ⚠️ (🚨 si es root) |
| Más de 10 conexiones SSH nuevas por minuto o 50 web por segundo desde una IP (flood SYN tipo hping3) | El kernel tira el exceso al instante y en menos de 1 min bloquea la IP 1 h | ⚠️ |
| 150 conexiones abiertas o 60 a medio abrir desde una IP (DoS) | Bloquea 15 min / 1 h | ⚠️ |
| Ola de conexiones a medio abrir desde muchas IPs (DDoS SYN) | Cookies SYN del kernel + frena a las peores | 🚨 |
| Tráfico de entrada o salida muy por encima de lo normal (aprende lo normal solo, el primer día es prudente) | — | 🚨 |
| Un programa desconocido manda 300 MB a una sola IP en 10 min (fuga) | Bloquea esa IP en ambos sentidos 1 h | 🚨 |
| Lo mismo con un programa conocido (Syncthing, Caddy, node…) o alguien que descarga mucho de tu web | — | ⚠️ |
| Cambian usuarios, sudoers, llaves SSH, cron, servicios, Caddy, PAM, `ld.so.preload` | Guarda la versión anterior | ⚠️/🚨 con lo que cambió |
| Usuario con UID 0 que no es root | — | 🚨 |
| Puerto nuevo escuchando hacia internet | — | ⚠️ |
| Minero de cripto, o un programa de `/tmp` o `/dev/shm` comiéndose la CPU | Lo **congela** (SIGSTOP, no lo mata) | 🚨 |

**Nunca bloquea:** tus IPs de `CENTINELA_PERMITIDOS`, la IP pública del propio servidor, IPs desde las que
entraste por SSH en los últimos 3 días, redes privadas, Tailscale y Cloudflare (si tus dominios pasan por
Cloudflare, bloquear una de sus IPs tumbaría la web para todos).

**Lo que no puede hacer desde aquí:** un DDoS que llena el cable no se para dentro del servidor; para eso
está Cloudflare (Security → *Under Attack*) o el proveedor. Los archivos cambiados no los revierte solo,
porque pudiste ser tú: te dice el comando para deshacerlo.

## Comandos
```bash
sudo orion-centinela estado                 # modo, IPs bloqueadas y últimos eventos
sudo orion-centinela lista                  # solo las bloqueadas
sudo orion-centinela bloquear 1.2.3.4 120   # a mano (minutos opcional)
sudo orion-centinela desbloquear 1.2.3.4
sudo orion-centinela confiar 1.2.3.4 30     # nunca bloquear esa IP en 30 días
sudo orion-centinela aceptar                # "ese cambio lo hice yo": lo de ahora queda como normal
sudo orion-centinela restaurar /etc/ssh/sshd_config
sudo orion-centinela soltar 4242            # descongela un proceso
sudo orion-centinela apagar                 # quita TODOS los bloqueos y límites (sigue avisando)
sudo orion-centinela encender
```
Por WhatsApp también: "¿me están atacando?", "qué IPs bloqueaste", "bloquea 1.2.3.4", "desbloquea 1.2.3.4".
Orión solo puede esas cuatro cosas (sudoers); apagar, aceptar y restaurar son solo tuyos, a propósito.

## Si te bloquea a ti
No debería (ver arriba), pero si pasa: el bloqueo caduca solo en 1 h. Si no puedes esperar, entra por la
consola web del proveedor (Clouding → tu servidor → Consola) y corre `sudo orion-centinela apagar`.

## Dónde vive
- Lo que corre: `/opt/orion-centinela/` (copia que solo root cambia; `instalar.sh` la actualiza). El
  actualizador automático de Orión NO toca esta copia: vuelve a correr `./centinela/instalar.sh` tras
  cambios en `centinela/`.
- Ajustes: `/etc/orion-centinela.conf` (umbrales en `AJUSTES` de `centinela.py`).
- Registro: `/var/log/orion-centinela.jsonl`. Estado: `/var/lib/orion-centinela/`.
- Reglas: tabla propia `inet orion_centinela` de nftables; no toca ufw.
- Pruebas: `python3 -m unittest centinela/test_centinela.py` (con `CENTINELA_PROBAR_NFT=1` y root, prueba
  nftables de verdad).
