#!/usr/bin/env python3
"""Centinela de Orión: vigila el servidor, se defiende solo y le avisa a David por WhatsApp.

Corre como root cada minuto (orion-centinela.timer, lo instala centinela/instalar.sh) desde una copia en
/opt/orion-centinela, para que nadie que entre como david pueda cambiar lo que corre como root.

Qué vigila en cada ronda:
  ssh         intentos fallidos de entrar (robots probando claves) y entradas buenas desde IPs nuevas
  conexiones  demasiadas conexiones desde una IP, o una ola de SYN (DoS / DDoS)
  trafico     entrada o salida muy por encima de lo normal de este servidor (aprende lo normal solo)
  salida      un programa mandando cientos de MB a una sola IP (posible fuga de datos)
  archivos    cambios en usuarios, sudoers, llaves SSH, cron, servicios, Caddy (puertas traseras)
  puertos     un puerto nuevo escuchando hacia internet
  procesos    programas corriendo desde /tmp o /dev/shm, o mineros conocidos, gastando CPU

Qué hace solo (todo con marcha atrás):
  - Bloquea IPs atacantes en su propia tabla de nftables, con caducidad (1 h; 24 h si ataca la web; 7 días si reincide).
  - Las webs se vigilan casi al instante (orion-centinela-web.service, cada 2 s): pedir .env, .git, wp-login o
    meter una inyección grave bloquea a la primera.
  - Frena ráfagas de conexiones nuevas a SSH y a la web (reglas.nft).
  - Congela (SIGSTOP, no mata) un minero o un programa sospechoso de /tmp que se come la CPU.
Nunca bloquea: loopback, redes privadas, Cloudflare, Tailscale, las IPs de CENTINELA_PERMITIDOS, ni una
IP desde la que David entró por SSH en los últimos días. Así no puede dejarlo fuera.

Lo que no puede arreglar desde aquí (y lo dice en el aviso): un DDoS que llena el enlace entero se para
antes de llegar al servidor (Cloudflare o el proveedor); los archivos cambiados no los revierte solo
porque pudo ser David, pero guarda la versión anterior para "orion-centinela restaurar <ruta>".

Uso:  orion-centinela ronda | web-vivo | encender | apagar | estado | lista | bloquear IP [min] | desbloquear IP
                      | confiar IP [días] | aceptar | restaurar RUTA | soltar PID
"""
import difflib
import fcntl
import fnmatch
import glob
import hashlib
import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import web  # noqa: E402  (vive junto a este archivo, también en /opt/orion-centinela)

BASE = Path(os.environ.get("CENTINELA_DATOS", "/var/lib/orion-centinela"))
ESTADO = BASE / "estado.json"
AVISOS = BASE / "avisos"            # el puente de WhatsApp los lee y los borra
RESPALDO = BASE / "respaldo"        # versiones anteriores de los archivos vigilados (solo root)
REGISTRO = Path(os.environ.get("CENTINELA_REGISTRO", "/var/log/orion-centinela.jsonl"))
CONF = Path(os.environ.get("CENTINELA_CONF", "/etc/orion-centinela.conf"))
REGLAS = Path(__file__).resolve().with_name("reglas.nft")
TABLA = ("inet", "orion_centinela")

# Se cambian en /etc/orion-centinela.conf (CENTINELA_<NOMBRE>=valor).
AJUSTES = {
    "MODO": "actuar",            # actuar = bloquea y avisa; avisar = solo avisa
    "PERMITIDOS": "",            # IPs o redes que nunca se bloquean, separadas por comas
    "GRUPO": "david",            # grupo que puede leer avisos y registro (el del puente de WhatsApp)
    "SSH_FALLOS": 8,             # intentos fallidos...
    "SSH_VENTANA_MIN": 10,       # ...en estos minutos = bloqueo
    "BLOQUEO_MIN": 60,
    "REINCIDENTE_MIN": 10080,    # si ya se bloqueó esa IP en la última semana (7 días)
    "CONEXIONES_IP": 150,        # conexiones abiertas a la vez desde una IP
    "SYN_IP": 60,                # conexiones a medio abrir desde una IP
    "SYN_TOTAL": 300,            # a medio abrir en total: ola de SYN
    "RX_MB_S": 8,                # piso de entrada (MB/s) para llamar inusual al tráfico
    "TX_MB_S": 8,                # piso de salida (MB/s)
    "PPS": 30000,                # piso de paquetes por segundo de entrada
    "SALIDA_MB": 300,            # MB enviados a una sola IP...
    "SALIDA_VENTANA_MIN": 10,    # ...en estos minutos = posible fuga
    "CONOCIDOS": "syncthing,caddy,sshd,sshd-session,node,claude,git,git-remote-http,apt,http,https,"
                 "curl,tailscaled,snapd,unattended-upgr,systemd-resolve,chronyd",
    "CPU_PCT": 50,               # % de CPU sostenido para congelar un programa sospechoso
    "AVISO_REPETIR_MIN": 30,     # el mismo aviso no se repite antes de esto
    "CONFIANZA_DIAS": 3,
    # Webs del dominio (registro de Caddy, ver centinela/caddy-registro.sh)
    "WEB_REGISTRO": "/var/log/caddy/acceso.log",
    "WEB_BLOQUEO_MIN": 1440,     # quien ataca la web (inyección, secretos, escáner) se queda fuera 24 h
    "WEB_RAPIDO_S": 2,           # cada cuántos segundos mira el registro de Caddy (orion-centinela-web.service)
    "WEB_ATAQUES": 3,            # peticiones con inyección/XSS/etc. en 10 min = bloqueo (las graves, a la primera)
    "WEB_SENSIBLES": 3,          # otras rutas sensibles (config.php, .bak, /actuator...) en 10 min; .env, .git, wp-login: a la primera
    "WEB_ERRORES": 100,          # respuestas 404/4xx en 10 min (buscando rutas a ciegas)
    "WEB_LOGIN_FALLOS": 20,      # POST rechazados (401/403) en 10 min (fuerza bruta a un login)
    "WEB_PETICIONES_MIN": 600,   # peticiones por minuto de una sola IP (flood HTTP)
    "WEB_DESCARGA_MB": 500,      # MB que se lleva una IP en 10 min
    "WEB_TOTAL_MIN": 6000,       # piso de peticiones/min de todos juntos para llamar DDoS a un pico
    # Cloudflare: con token, bloquea en Cloudflare a quien ataca a través de él y activa "Under Attack"
    "CF_TOKEN": "",
    "CF_ZONA": "",
    # De dónde es cada IP de un aviso (país, ciudad y empresa, por ipinfo.io). 0 = no consultar.
    "ORIGEN": 1,
    "IPINFO_TOKEN": "",          # opcional: sin token ipinfo da 50.000 consultas al mes, de sobra
}

# Cloudflare (https://www.cloudflare.com/ips/): si los dominios pasan por su proxy, todo el tráfico web
# llega desde aquí; bloquear una de estas IPs tumbaría la web para todos.
CLOUDFLARE = """173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18
190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14
172.64.0.0/13 131.0.72.0/22 2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32
2a06:98c0::/29 2c0f:f248::/32""".split()
TAILSCALE = ["100.64.0.0/10", "fd7a:115c:a1e0::/48"]

VIGILADOS = [
    "/etc/passwd", "/etc/shadow", "/etc/group", "/etc/gshadow", "/etc/sudoers", "/etc/sudoers.d/*",
    "/etc/ssh/sshd_config", "/etc/ssh/sshd_config.d/*", "/root/.ssh/authorized_keys", "/home/*/.ssh/authorized_keys",
    "/etc/crontab", "/etc/cron.d/*", "/var/spool/cron/crontabs/*", "/etc/systemd/system/*.service",
    "/etc/systemd/system/*.timer", "/etc/ld.so.preload", "/etc/hosts", "/etc/profile.d/*", "/etc/rc.local",
    "/etc/caddy/Caddyfile", "/etc/caddy/conf.d/*", "/etc/pam.d/sshd", "/etc/pam.d/common-auth",
]
SECRETOS = {"/etc/shadow", "/etc/gshadow"}     # de estos nunca se muestra el contenido
MINEROS = re.compile(r"xmrig|kdevtmpfsi|kinsing|minerd|cpuminer|xmr-stak|nbminer|t-rex|lolminer|phoenixminer|"
                     r"ccminer|cryptonight|\bc3pool\b|sysupdate|networkservice", re.I)
CARPETAS_RARAS = ("/tmp/", "/var/tmp/", "/dev/shm/")

# ---------- utilidades ----------


def ahora():
    return time.time()


def leer_conf(ruta=CONF):
    c = dict(AJUSTES)
    try:
        for linea in ruta.read_text().splitlines():
            m = re.match(r"\s*CENTINELA_([A-Z_]+)\s*=\s*(.*?)\s*$", linea)
            if m and m.group(1) in c:
                v = m.group(2).strip("\"'")
                c[m.group(1)] = type(AJUSTES[m.group(1)])(v) if isinstance(AJUSTES[m.group(1)], int) else v
    except FileNotFoundError:
        pass
    except ValueError as e:
        print(f"Ajuste inválido en {ruta}: {e}", file=sys.stderr)
    return c


def correr(*cmd, entrada=None):
    try:
        r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def ip_valida(texto):
    try:
        ip = ipaddress.ip_address(str(texto).strip().strip("[]"))
    except ValueError:
        return None
    return ip.ipv4_mapped or ip if isinstance(ip, ipaddress.IPv6Address) else ip


def redes(lista):
    out = []
    for r in lista:
        r = r.strip()
        if not r:
            continue
        try:
            out.append(ipaddress.ip_network(r, strict=False))
        except ValueError:
            print(f"Red inválida ignorada: {r}", file=sys.stderr)
    return out


def mb(n):
    return f"{n / 1e6:.0f} MB" if n >= 1e7 else f"{n / 1e6:.1f} MB"


# ---------- lectura de lo que pasa (funciones puras, probadas en test_centinela.py) ----------

RE_FALLO = [
    re.compile(r"Failed (?:password|publickey|keyboard-interactive/pam) for (?:invalid user )?(\S*) from (\S+)"),
    re.compile(r"Invalid user (\S*) from (\S+)"),
    re.compile(r"authentication failure;.* rhost=(\S+)"),
    re.compile(r"Connection (?:closed|reset) by (?:authenticating|invalid) user (\S*) (\S+) port \d+ \[preauth\]"),
    re.compile(r"(?:Did not receive identification string|banner exchange: Connection) from (\S+)"),
    re.compile(r"maximum authentication attempts exceeded for (?:invalid user )?(\S*) from (\S+)"),
]
RE_ENTRADA = re.compile(r"Accepted (\S+) for (\S+) from (\S+)")


def eventos_ssh(lineas):
    """Líneas de journalctl de sshd -> [("fallo", ip, usuario) | ("entrada", ip, usuario, método)]."""
    out = []
    for linea in lineas:
        m = RE_ENTRADA.search(linea)
        if m and ip_valida(m.group(3)):
            out.append(("entrada", str(ip_valida(m.group(3))), m.group(2), m.group(1)))
            continue
        for r in RE_FALLO:
            m = r.search(linea)
            if m:
                ip = ip_valida(m.groups()[-1])
                if ip:
                    out.append(("fallo", str(ip), m.group(1) if len(m.groups()) > 1 else ""))
                break
    return out


def _direccion(texto):
    """'1.2.3.4:22', '[::ffff:1.2.3.4]:443', '[2001:db8::1]:22', '*:22' -> (ip|None, puerto)."""
    texto = re.sub(r"%\S+?(?=[:\]])", "", texto)      # 'fe80::1%eth0' -> 'fe80::1'
    host, _, puerto = texto.rpartition(":")
    return ip_valida(host), int(puerto) if puerto.isdigit() else 0


def conexiones(salida_ss):
    """Salida de 'ss -Htanp' (con o sin -i) -> [{estado, local, lport, remoto, rport, proc, bytes_acked, bytes_received}]."""
    out = []
    for linea in salida_ss.splitlines():
        if not linea.strip():
            continue
        if linea[0] in " \t":
            if out:
                for clave in ("bytes_acked", "bytes_received"):
                    m = re.search(rf"\b{clave}:(\d+)", linea)
                    if m:
                        out[-1][clave] = int(m.group(1))
            continue
        partes = linea.split()
        if len(partes) < 5:
            continue
        local, lport = _direccion(partes[3])
        remoto, rport = _direccion(partes[4])
        if remoto is not None and remoto.is_unspecified:     # LISTEN: '0.0.0.0:*'
            remoto = None
        proc = re.search(r'users:\(\("([^"]+)"', linea)
        out.append({"estado": partes[0], "local": local, "lport": lport, "remoto": remoto, "rport": rport,
                    "proc": proc.group(1) if proc else "", "bytes_acked": 0, "bytes_received": 0})
    return out


def escuchando(salida_ss):
    """'ss -Hltunp' -> {'tcp:22': 'sshd', ...} solo lo que escucha hacia fuera (no 127.0.0.x ni ::1)."""
    out = {}
    for linea in salida_ss.splitlines():
        p = linea.split()
        if len(p) < 6:
            continue
        ip, puerto = _direccion(p[4])
        if ip is not None and ip.is_loopback:
            continue
        proc = re.search(r'users:\(\("([^"]+)"', linea)
        nombre = proc.group(1) if proc else "?"
        # UDP en el rango efímero (Syncthing, QUIC, descubrimiento): cambia de puerto a cada rato. Se vigila
        # por programa: avisa si un programa NUEVO abre puertos altos, no cada vez que uno conocido cambia.
        if p[0] == "udp" and puerto >= 32768:
            out[f"udp:alto({nombre})"] = nombre
        else:
            out[f"{p[0]}:{puerto}"] = nombre
    return out


def contadores_red(texto):
    """/proc/net/dev -> (rx_bytes, rx_paquetes, tx_bytes) sumando todas las interfaces menos lo."""
    rx = rxp = tx = 0
    for linea in texto.splitlines()[2:]:
        nombre, _, datos = linea.partition(":")
        if nombre.strip() == "lo" or not datos:
            continue
        c = datos.split()
        rx, rxp, tx = rx + int(c[0]), rxp + int(c[1]), tx + int(c[8])
    return rx, rxp, tx


class Normal:
    """Lo normal de una medida (media y varianza que se mueven despacio). Un valor es raro si pasa la media
    en 6 desviaciones Y además un piso fijo, así un servidor tranquilo no alerta por un pico de 1 MB."""

    def __init__(self, d=None):
        d = d or {}
        self.n, self.media, self.var = d.get("n", 0), d.get("media", 0.0), d.get("var", 0.0)

    def raro(self, x, piso, aprendiendo=1440):
        if x < piso:
            return False
        if self.n < aprendiendo:          # el primer día solo cuenta el piso, multiplicado por 3
            return x > piso * 3
        return x > self.media + 6 * self.var ** 0.5

    def sumar(self, x, alfa=0.01):
        if self.n == 0:
            self.media = x
        d = x - self.media
        self.media += alfa * d
        self.var = (1 - alfa) * (self.var + alfa * d * d)
        self.n += 1

    def dict(self):
        return {"n": self.n, "media": self.media, "var": self.var}


def diferencias(antes, despues, max_lineas=8):
    """Líneas añadidas y quitadas, cortas, para el aviso."""
    out = []
    for l in difflib.unified_diff(antes.splitlines(), despues.splitlines(), lineterm="", n=0):
        if l.startswith(("+++", "---", "@@")):
            continue
        out.append(l[:110] + ("…" if len(l) > 110 else ""))
    return out[:max_lineas] + ([f"(+{len(out) - max_lineas} líneas más)"] if len(out) > max_lineas else [])


def duracion(minutos):
    if minutos >= 2880:
        return f"{minutos // 1440} días"
    return f"{minutos // 60} h" if minutos >= 60 else f"{minutos} min"


# ---------- el centinela ----------


class Centinela:
    def __init__(self, conf=None, estado_ruta=ESTADO):
        self.c = conf or leer_conf()
        self.estado_ruta = estado_ruta
        try:
            self.e = json.loads(estado_ruta.read_text())
        except (FileNotFoundError, ValueError):
            self.e = {}
        for clave in ("bloqueos", "historial", "confianza", "avisados", "fallos", "huellas", "puertos",
                      "salida", "cpu", "congelados", "normal", "web", "cf_bloqueos", "origen"):
            self.e.setdefault(clave, {})
        self.primera_vez = "inicio" not in self.e
        self.e.setdefault("inicio", ahora())
        self.protegidas = redes(CLOUDFLARE + TAILSCALE + self.c["PERMITIDOS"].split(","))
        self.mias = set()
        self.cf = web.Cloudflare(self.c["CF_TOKEN"], self.c["CF_ZONA"]) if self.c["CF_TOKEN"] and self.c["CF_ZONA"] else None
        self.cloudflare = redes(CLOUDFLARE)
        self.buscar_origen = lambda ip: web.origen(ip, self.c["IPINFO_TOKEN"])

    def es_cloudflare(self, ip):
        ip = ip_valida(ip)
        return ip is not None and any(ip in r for r in self.cloudflare if r.version == ip.version)

    # --- memoria ---

    def guardar(self):
        BASE.mkdir(parents=True, exist_ok=True)
        tmp = self.estado_ruta.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.e, f)
        os.replace(tmp, self.estado_ruta)

    def anotar(self, tipo, **datos):
        linea = json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "tipo": tipo, **datos}, ensure_ascii=False)
        try:
            nuevo = not REGISTRO.exists()
            with open(REGISTRO, "a") as f:
                f.write(linea + "\n")
            if nuevo:
                self._para_grupo(REGISTRO, 0o640)
        except OSError as e:
            print(f"No pude escribir el registro: {e}", file=sys.stderr)
        print(linea)

    def _para_grupo(self, ruta, modo):
        try:
            import grp
            os.chown(ruta, 0, grp.getgrnam(self.c["GRUPO"]).gr_gid)
            os.chmod(ruta, modo)
        except (KeyError, OSError, PermissionError):
            pass

    def avisar(self, clave, gravedad, texto):
        """Deja el aviso para WhatsApp (el puente lo envía en segundos). El mismo no se repite en 30 min."""
        self.anotar("aviso", gravedad=gravedad, texto=texto)
        if ahora() - self.e["avisados"].get(clave, 0) < self.c["AVISO_REPETIR_MIN"] * 60:
            return
        self.e["avisados"][clave] = ahora()
        icono = {"alta": "🚨", "media": "⚠️", "info": "🛡️"}.get(gravedad, "🛡️")
        cuerpo = f"{icono} *Centinela ({gravedad})*\n{texto}" + self.origenes(texto)
        try:
            AVISOS.mkdir(parents=True, exist_ok=True)
            ruta = AVISOS / f"{int(ahora() * 1000)}-{os.getpid()}-{len(self.e['avisados'])}.txt"
            # O_EXCL + O_NOFOLLOW: la carpeta la puede escribir el grupo; nunca se sigue un enlace puesto ahí.
            fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
            with os.fdopen(fd, "w") as f:
                f.write(cuerpo)
            self._para_grupo(ruta, 0o640)
        except OSError as e:
            print(f"No pude dejar el aviso: {e}", file=sys.stderr)

    def origen(self, ip):
        """De dónde es una IP pública, con memoria de 7 días (un fallo se reintenta en 1 h). None si no se sabe."""
        if not self.c["ORIGEN"] or self.protegida(ip):
            return None
        guardado = self.e["origen"].get(ip)
        if guardado and ahora() - guardado["t"] < (7 * 86400 if guardado["txt"] else 3600):
            return guardado["txt"] or None
        txt = self.buscar_origen(ip) or ""
        self.e["origen"][ip] = {"t": ahora(), "txt": txt}
        if len(self.e["origen"]) > 500:      # que el estado no crezca sin fin: se olvidan las más viejas
            for vieja in sorted(self.e["origen"], key=lambda k: self.e["origen"][k]["t"])[:100]:
                del self.e["origen"][vieja]
        return txt or None

    def origenes(self, texto):
        """Líneas "📍 IP: país (ciudad), empresa" para las IPs públicas que nombra un aviso (máx. 3)."""
        lineas, vistas = [], set()
        for candidata in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{0,4}){2,7}\b", texto):
            ip = ip_valida(candidata)
            if ip is None or str(ip) in vistas or len(vistas) >= 3:
                continue
            vistas.add(str(ip))
            donde = self.origen(str(ip))
            if donde:
                lineas.append(f"📍 {ip}: {donde}")
        return ("\n" + "\n".join(lineas)) if lineas else ""

    # --- quién no se toca ---

    def protegida(self, ip):
        ip = ip_valida(ip)
        if ip is None:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return True
        if str(ip) in self.mias or any(ip in r for r in self.protegidas if r.version == ip.version):
            return True
        return self.e["confianza"].get(str(ip), 0) > ahora()

    def _mis_ips(self):
        _, out, _ = correr("ip", "-j", "addr")
        try:
            self.mias = {a["local"] for i in json.loads(out or "[]") for a in i.get("addr_info", [])}
        except ValueError:
            self.mias = set()

    # --- nftables ---

    def _nft(self, *args, entrada=None):
        return correr("nft", *args, entrada=entrada)

    def tabla_viva(self):
        return self._nft("list", "table", *TABLA)[0] == 0

    def _elemento(self, accion, conjunto, ip, segundos=None):
        ip = ip_valida(ip)
        fam = "4" if ip.version == 4 else "6"
        extra = f" timeout {int(segundos)}s" if segundos else ""
        return self._nft(accion, "element", *TABLA, f"{conjunto}{fam}", "{ " + str(ip) + extra + " }")

    def encender(self):
        if not REGLAS.exists():
            return print(f"No encuentro {REGLAS}")
        cod, _, err = self._nft("-f", str(REGLAS))
        if cod:
            return print(f"nftables no aceptó las reglas: {err.strip()}")
        fijas = [r for r in self.protegidas]
        for v in (4, 6):
            lista = ", ".join(str(r) for r in fijas if r.version == v)
            if lista:
                self._nft("add", "element", *TABLA, f"permitidos{v}", "{ " + lista + " }")
        for ip, hasta in self.e["confianza"].items():
            if hasta > ahora() + 1:
                self._elemento("add", "confianza", ip, hasta - ahora())
        for ip, b in self.e["bloqueos"].items():
            if b["hasta"] > ahora() + 1:
                self._elemento("add", "bloqueados", ip, b["hasta"] - ahora())
        self.e["apagado"] = False
        print("Centinela encendido: reglas cargadas.")

    def apagar(self):
        self._nft("delete", "table", *TABLA)
        self.e["apagado"] = True
        self.anotar("apagado")
        print("Centinela apagado: sin bloqueos ni límites. Sigue mirando y avisando. Para volver: orion-centinela encender")

    def actua(self):
        return self.c["MODO"] == "actuar" and not self.e.get("apagado")

    def bloquear(self, ip, minutos, motivo, a_mano=False):
        """Bloquea la IP en ambos sentidos con caducidad. Devuelve el texto para el aviso."""
        ip = str(ip_valida(ip))
        if self.protegida(ip):
            self.anotar("no-bloqueada", ip=ip, motivo=motivo)
            return f"No la bloqueé porque {ip} está en tu lista de confianza (tuya, Cloudflare, red privada o entraste desde ella)."
        if not a_mano and not self.actua():
            return "Estoy en modo solo avisar, así que no la bloqueé. Para bloquearla: `sudo orion-centinela bloquear " + ip + "`"
        if not a_mano and self.e["historial"].get(ip, 0) > ahora() - 7 * 86400:
            minutos = max(minutos, self.c["REINCIDENTE_MIN"])
        hasta = ahora() + minutos * 60
        cod, _, err = self._elemento("add", "bloqueados", ip, minutos * 60)
        if cod:
            self.anotar("error-bloqueo", ip=ip, error=err.strip())
            return f"Intenté bloquear {ip} y nftables dijo: {err.strip()[:120]}"
        self.e["bloqueos"][ip] = {"hasta": hasta, "motivo": motivo, "desde": ahora()}
        self.e["historial"][ip] = ahora()
        self.anotar("bloqueo", ip=ip, minutos=minutos, motivo=motivo)
        dura = duracion(minutos)
        return f"Bloqueé {ip} por {dura} (se quita sola). Para soltarla ya: `sudo orion-centinela desbloquear {ip}`"

    def bloquear_en_cloudflare(self, ip, minutos, motivo):
        """Para quien ataca a través de Cloudflare: bloquearlo aquí cortaría a Cloudflare entero."""
        ip = str(ip_valida(ip))
        if self.protegida(ip):
            self.anotar("no-bloqueada", ip=ip, motivo=motivo)
            return f"No la bloqueé porque {ip} está en tu lista de confianza."
        if not self.cf:
            return ("Llega a través de Cloudflare, así que aquí no la puedo cortar sin cortar a todos. Con el token de "
                    "Cloudflare en /etc/orion-centinela.conf la bloqueo allá sola; mientras, bloquéala en Cloudflare: "
                    f"Security > WAF > Tools > IP Access Rules > {ip} > Block.")
        if not self.actua():
            return "Estoy en modo solo avisar, así que no la bloqueé en Cloudflare."
        if self.e["historial"].get(ip, 0) > ahora() - 7 * 86400:
            minutos = max(minutos, self.c["REINCIDENTE_MIN"])
        hasta = ahora() + minutos * 60
        regla, r = self.cf.bloquear(ip, f"orion-centinela: {motivo} (hasta {time.strftime('%d/%m %H:%M', time.localtime(hasta))})")
        if not regla:
            self.anotar("error-cloudflare", ip=ip, error=web.Cloudflare.error(r))
            return f"Intenté bloquearla en Cloudflare y respondió: {web.Cloudflare.error(r)[:120]}"
        self.e["cf_bloqueos"][ip] = {"id": regla, "hasta": hasta, "motivo": motivo}
        self.e["historial"][ip] = ahora()
        self.anotar("bloqueo-cloudflare", ip=ip, minutos=minutos, motivo=motivo)
        dura = duracion(minutos)
        return f"La bloqueé en Cloudflare por {dura} (se quita sola). Para soltarla: `sudo orion-centinela desbloquear {ip}`"

    def desbloquear(self, ip):
        ip = str(ip_valida(ip))
        self._elemento("delete", "bloqueados", ip)
        self.e["bloqueos"].pop(ip, None)
        cf = self.e["cf_bloqueos"].pop(ip, None)
        if cf and self.cf:
            self.cf.soltar(cf["id"])
        self.anotar("desbloqueo", ip=ip)
        return f"{ip} desbloqueada."

    def confiar(self, ip, dias, motivo=""):
        ip = str(ip_valida(ip))
        self.e["confianza"][ip] = ahora() + dias * 86400
        if self.tabla_viva():
            self._elemento("delete", "bloqueados", ip)
            self._elemento("add", "confianza", ip, dias * 86400)
        self.e["bloqueos"].pop(ip, None)
        self.anotar("confianza", ip=ip, dias=dias, motivo=motivo)

    # --- las revisiones ---

    def revisar_ssh(self):
        cursor = BASE / "ssh.cursor"
        args = ["journalctl", "-q", "--no-pager", "-o", "cat", f"--cursor-file={cursor}",
                "_COMM=sshd", "_COMM=sshd-session"]
        if not cursor.exists():
            args.append("--since=-10min")
        _, out, _ = correr(*args)
        ventana = self.c["SSH_VENTANA_MIN"] * 60
        for ev in eventos_ssh(out.splitlines()):
            if ev[0] == "entrada":
                _, ip, usuario, metodo = ev
                nueva = ip not in self.e["confianza"] and not self.protegida(ip)
                self.confiar(ip, self.c["CONFIANZA_DIAS"], f"entrada SSH de {usuario}")
                if usuario == "root":
                    self.avisar(f"root-{ip}", "alta", f"Alguien entró por SSH como *root* desde {ip} ({metodo}). "
                                "Si no fuiste tú, el servidor está comprometido: cambia claves y revisa `sudo orion-centinela estado`.")
                elif nueva and not self.primera_vez:
                    self.avisar(f"entrada-{ip}", "media", f"Entrada SSH de *{usuario}* desde una IP nueva: {ip} ({metodo}). "
                                f"Si fuiste tú, nada que hacer (ya es de confianza). Si no: `sudo orion-centinela bloquear {ip}`, "
                                "cambia tus claves y revisa ~/.ssh/authorized_keys.")
                continue
            _, ip, usuario = ev
            lista = [t for t in self.e["fallos"].get(ip, []) if t > ahora() - ventana] + [ahora()]
            self.e["fallos"][ip] = lista
            if len(lista) >= self.c["SSH_FALLOS"] and ip not in self.e["bloqueos"]:
                r = self.bloquear(ip, self.c["BLOQUEO_MIN"], f"{len(lista)} intentos fallidos de SSH")
                self.avisar(f"ssh-{ip}", "media", f"{len(lista)} intentos de entrar por SSH desde {ip} en "
                            f"{self.c['SSH_VENTANA_MIN']} min (usuario: {usuario or '?'}). {r}")
        self.e["fallos"] = {ip: l for ip, l in self.e["fallos"].items() if l and l[-1] > ahora() - ventana}

    def excesos(self):
        """IPs que nftables pilló pasándose del límite de conexiones nuevas -> {ip: 'ssh'|'web'}."""
        out = {}
        for tipo in ("ssh", "web"):
            for v in (4, 6):
                _, js, _ = self._nft("-j", "list", "set", *TABLA, f"exceso_{tipo}{v}")
                try:
                    datos = json.loads(js or "{}")["nftables"]
                except (ValueError, KeyError):
                    continue
                for d in datos:
                    for el in d.get("set", {}).get("elem", []):
                        ip = el.get("elem", {}).get("val") if isinstance(el, dict) else el
                        if ip_valida(ip):
                            out[str(ip_valida(ip))] = tipo
        return out

    def revisar_excesos(self):
        """Quien se pasó del límite ya vio su exceso tirado al instante; aquí se bloquea del todo y se avisa."""
        if not self.tabla_viva():
            return
        for ip, tipo in self.excesos().items():
            self._elemento("delete", f"exceso_{tipo}", ip)
            if ip in self.e["bloqueos"]:
                continue
            if tipo == "ssh":
                motivo, texto = "más de 10 conexiones SSH nuevas por minuto", "abrió más de 10 conexiones SSH por minuto (robot probando claves)"
            else:
                motivo, texto = "más de 50 conexiones nuevas por segundo", "lanzó más de 50 conexiones nuevas por segundo al servidor (inundación / DoS)"
            r = self.bloquear(ip, self.c["BLOQUEO_MIN"], motivo)
            self.avisar(f"exceso-{ip}", "media", f"{ip} {texto}. El servidor tiró el exceso al momento y no se cayó. {r}")

    def _leer_registro_web(self):
        """Las líneas nuevas del registro de Caddy desde la última ronda (aguanta rotaciones)."""
        ruta = Path(self.c["WEB_REGISTRO"])
        try:
            st = ruta.stat()
        except OSError:
            return []
        pos = self.e["web"].get("pos", {})
        inicio = pos.get("offset", 0) if pos.get("inodo") == st.st_ino and st.st_size >= pos.get("offset", 0) else 0
        if self.primera_vez or not pos:
            inicio = st.st_size                     # lo de antes de encender no se juzga
        inicio = max(inicio, st.st_size - 20 * 1024 * 1024)   # como mucho 20 MB por ronda
        with open(ruta, "rb") as f:
            f.seek(inicio)
            datos = f.read()
        corte = datos.rfind(b"\n") + 1                  # una línea a medio escribir se lee la próxima vez
        self.e["web"]["pos"] = {"inodo": st.st_ino, "offset": inicio + corte}
        return datos[:corte].decode(errors="replace").splitlines()

    def revisar_web(self, rapida=False):
        """Ataques a las webs del dominio: inyecciones, escáneres, fuerza bruta, floods HTTP, descargas masivas.
        Corre cada 2 s (rapida=True, desde web-vivo) y también en la ronda de cada minuto, que además mira si hay DDoS."""
        ventana = 600
        hist = self.e["web"].get("ips", {})
        ronda, total = {}, 0
        for texto in self._leer_registro_web():
            a = web.linea(texto)
            if not a:
                continue
            total += 1
            ip, via_cf = web.ip_real(a, self.es_cloudflare)
            if not ip_valida(ip) or self.protegida(ip):
                continue
            ip = str(ip_valida(ip))
            r = ronda.setdefault(ip, {"pet": 0, "ataques": 0, "graves": 0, "sensibles": 0, "errores": 0, "login": 0,
                                      "bytes": 0, "tipos": [], "ejemplo": "", "host": a["host"], "cf": via_cf})
            r["pet"] += 1
            r["bytes"] += a["bytes"]
            r["errores"] += 400 <= a["estado"] < 500
            r["login"] += a["metodo"] == "POST" and a["estado"] in (401, 403)
            tipos = web.ataques_en(a)
            for t in tipos:
                if t not in r["tipos"]:
                    r["tipos"].append(t)
            if tipos:
                r["sensibles"] += "busca archivos sensibles" in tipos
                otros = [t for t in tipos if t != "busca archivos sensibles"]
                r["ataques"] += bool(otros)
                r["graves"] += any(t in web.GRAVES or t == "escáner automático" for t in otros)
                r["ejemplo"] = r["ejemplo"] or f"{a['metodo']} {a['host']}{a['uri']}"[:110].replace("`", "'")
        claves = ("pet", "ataques", "graves", "sensibles", "errores", "login", "bytes")
        for ip, r in ronda.items():
            hist[ip] = [x for x in hist.get(ip, []) if x[0] > ahora() - ventana] + [[ahora()] + [r[k] for k in claves]]
        hist = {ip: l for ip, l in hist.items() if l and l[-1][0] > ahora() - ventana}
        self.e["web"]["ips"] = hist
        for ip, r in ronda.items():
            suma = dict(zip(claves, (sum(x[i + 1] for x in hist[ip]) for i in range(len(claves)))))
            motivo = None
            if suma["graves"]:
                motivo = f"ataque a la web ({', '.join(r['tipos'])})"
            elif suma["ataques"] >= self.c["WEB_ATAQUES"]:
                motivo = f"{suma['ataques']} intentos de {', '.join(r['tipos'])}"
            elif suma["sensibles"] >= self.c["WEB_SENSIBLES"]:
                motivo = f"buscó {suma['sensibles']} archivos sensibles (.env, .git, wp-login...)"
            elif suma["login"] >= self.c["WEB_LOGIN_FALLOS"]:
                motivo = f"{suma['login']} intentos de login rechazados (fuerza bruta)"
            elif suma["errores"] >= self.c["WEB_ERRORES"]:
                motivo = f"{suma['errores']} páginas inexistentes en 10 min (buscando rutas a ciegas)"
            elif (pet_min := sum(x[1] for x in hist[ip] if x[0] > ahora() - 60)) >= self.c["WEB_PETICIONES_MIN"]:
                motivo = f"{pet_min} peticiones en un minuto (flood HTTP)"
            if motivo and ip not in self.e["bloqueos"] and ip not in self.e["cf_bloqueos"]:
                minutos = self.c["WEB_BLOQUEO_MIN"] if suma["graves"] or suma["ataques"] or suma["sensibles"] else self.c["BLOQUEO_MIN"]
                if r["cf"]:
                    hecho = self.bloquear_en_cloudflare(ip, minutos, motivo)
                else:
                    hecho = self.bloquear(ip, minutos, motivo)
                ejemplo = f"\nEjemplo: `{r['ejemplo']}`" if r["ejemplo"] else ""
                self.avisar(f"web-{ip}", "alta" if suma["graves"] else "media",
                            f"Ataque a {r['host'] or 'la web'} desde {ip}: {motivo}.{ejemplo}\n{hecho}")
            elif suma["bytes"] >= self.c["WEB_DESCARGA_MB"] * 1e6:
                self.avisar(f"webdesc-{ip}", "media", f"{ip} se ha llevado {mb(suma['bytes'])} de {r['host']} en 10 min. "
                            f"Si no es un cliente tuyo, `sudo orion-centinela bloquear {ip}`.")
        # El DDoS se juzga por minuto: las vueltas rápidas van sumando y la ronda del minuto decide.
        self.e["web"]["total"] = self.e["web"].get("total", 0) + total
        if not rapida:
            self._modo_ataque(self.e["web"].pop("total"))

    def _modo_ataque(self, total):
        """Si llegan muchísimas más peticiones de lo normal, sube Cloudflare a "Under Attack"; lo baja tras 30 min en calma."""
        n = Normal(self.e["normal"].get("web"))
        pico = n.raro(total, self.c["WEB_TOTAL_MIN"])
        if not pico:
            n.sumar(total)
        self.e["normal"]["web"] = n.dict()
        ua = self.e["web"].get("under_attack")
        if pico:
            if ua:
                ua["ultimo_pico"] = ahora()
                return
            if self.cf and self.actua():
                antes = self.cf.nivel() or "medium"
                r = self.cf.poner_nivel("under_attack")
                if r.get("success"):
                    self.e["web"]["under_attack"] = {"antes": antes, "desde": ahora(), "ultimo_pico": ahora()}
                    self.anotar("under-attack", peticiones=total)
                    hecho = "Activé el modo *Under Attack* de Cloudflare: los visitantes ven un reto de 5 s y los bots no pasan. Lo apago solo tras 30 min de calma."
                else:
                    hecho = f"Quise activar Under Attack en Cloudflare y respondió: {web.Cloudflare.error(r)[:120]}"
            else:
                hecho = "Actívalo a mano en Cloudflare: Overview > Under Attack Mode (o pon el token para que lo haga yo)."
            self.avisar("ddos-web", "alta", f"Posible DDoS a las webs: {total} peticiones en un minuto (lo normal: "
                        f"{n.media:.0f}). {hecho}")
        elif ua and ahora() - ua["ultimo_pico"] > 1800 and self.cf:
            r = self.cf.poner_nivel(ua["antes"])
            if r.get("success"):
                self.e["web"].pop("under_attack")
                self.anotar("under-attack-fin")
                self.avisar("ddos-web-fin", "info", f"30 min sin picos: Cloudflare vuelve al nivel de seguridad '{ua['antes']}'.")

    def revisar_conexiones(self, conns, puertos_abiertos):
        abiertos = {int(p.split(":")[1]) for p in puertos_abiertos if p.startswith("tcp:")} | {22, 80, 443}
        por_ip, syn_ip, syn_total = {}, {}, 0
        for c in conns:
            if c["remoto"] is None or c["lport"] not in abiertos:
                continue
            ip = str(c["remoto"])
            if c["estado"].startswith("SYN-REC"):
                syn_total += 1
                syn_ip[ip] = syn_ip.get(ip, 0) + 1
            elif c["estado"] == "ESTAB":
                por_ip[ip] = por_ip.get(ip, 0) + 1
        for ip, n in sorted(por_ip.items(), key=lambda x: -x[1]):
            if n >= self.c["CONEXIONES_IP"] and ip not in self.e["bloqueos"]:
                r = self.bloquear(ip, 15, f"{n} conexiones abiertas a la vez")
                self.avisar(f"con-{ip}", "media", f"{ip} tiene {n} conexiones abiertas a la vez (lo normal es un puñado). "
                            f"Parece un intento de tumbar el servidor (DoS). {r}")
        for ip, n in syn_ip.items():
            if n >= self.c["SYN_IP"] and ip not in self.e["bloqueos"]:
                r = self.bloquear(ip, self.c["BLOQUEO_MIN"], f"{n} conexiones a medio abrir (SYN)")
                self.avisar(f"syn-{ip}", "media", f"{ip} abrió {n} conexiones a medias (inundación SYN). {r}")
        if syn_total >= self.c["SYN_TOTAL"]:
            top = ", ".join(f"{ip} ({n})" for ip, n in sorted(syn_ip.items(), key=lambda x: -x[1])[:5])
            self.avisar("syn-total", "alta", f"Ola de {syn_total} conexiones a medio abrir desde muchas IPs: parece un "
                        f"DDoS (SYN flood). Las cookies SYN del kernel lo aguantan y freno a quien abre demasiadas. "
                        f"Las que más: {top}. Si la web se cae, actívalo en Cloudflare: Security > Under Attack.")
        return por_ip

    def revisar_trafico(self, intervalo, rx, rxp, tx, por_ip):
        rx_s, pps, tx_s = rx / intervalo, rxp / intervalo, tx / intervalo
        n = self.e["normal"]
        medidas = {"rx": (rx_s, self.c["RX_MB_S"] * 1e6), "pps": (pps, self.c["PPS"]), "tx": (tx_s, self.c["TX_MB_S"] * 1e6)}
        raros = {}
        for clave, (valor, piso) in medidas.items():
            norm = Normal(n.get(clave))
            if norm.raro(valor, piso):
                raros[clave] = (valor, norm.media)
            else:
                norm.sumar(valor)       # lo raro no se aprende como normal
            n[clave] = norm.dict()
        if "rx" in raros or "pps" in raros:
            top = ", ".join(f"{ip} ({c})" for ip, c in sorted(por_ip.items(), key=lambda x: -x[1])[:5]) or "ninguna destaca"
            if "rx" in raros:
                medida = f"{mb(raros['rx'][0])}/s ({pps:.0f} paquetes/s; lo normal aquí es {mb(raros['rx'][1])}/s)"
            else:
                medida = f"{pps:.0f} paquetes/s ({mb(rx_s)}/s; lo normal aquí son {raros['pps'][1]:.0f} paquetes/s)"
            self.avisar("rx", "alta", f"Entra muchísimo más tráfico de lo normal: {medida}. "
                        f"Puede ser un DDoS. IPs con más conexiones: {top}. "
                        "Bloqueo sola a la que se pase de la raya; si son miles de IPs, lo que lo para es Cloudflare "
                        "(Under Attack) o el proveedor, porque el ataque llena el cable antes de llegar aquí.")
        if "tx" in raros:
            v, m = raros["tx"]
            self.avisar("tx", "alta", f"Sale muchísimo más tráfico de lo normal: {mb(v)}/s (lo normal: {mb(m)}/s). "
                        "Revisa la siguiente alerta de fuga si la hay, o pídeme `estado del centinela`.")

    def revisar_salida(self, conns, puertos_abiertos, intervalo):
        """Cuenta los bytes que cada programa manda a cada IP. Mucho a una sola IP = posible fuga."""
        abiertos = {int(p.split(":")[1]) for p in puertos_abiertos if p.startswith("tcp:")}
        previo, actual, por_destino = self.e["salida"].get("sockets", {}), {}, {}
        for c in conns:
            if c["remoto"] is None or c["remoto"].is_loopback or c["estado"] != "ESTAB":
                continue
            clave = f"{c['local']}:{c['lport']}>{c['remoto']}:{c['rport']}"
            actual[clave] = c["bytes_acked"]
            delta = c["bytes_acked"] - previo.get(clave, c["bytes_acked"] if self.primera_vez else 0)
            if delta > 0:
                d = por_destino.setdefault(str(c["remoto"]), {"bytes": 0, "procs": set(), "entrante": c["lport"] in abiertos})
                d["bytes"] += delta
                d["procs"].add(c["proc"] or "?")
        ventana = self.c["SALIDA_VENTANA_MIN"] * 60
        hist = self.e["salida"].get("hist", {})
        conocidos = set(self.c["CONOCIDOS"].split(","))
        for ip, d in por_destino.items():
            hist[ip] = [x for x in hist.get(ip, []) if x[0] > ahora() - ventana] + [[ahora(), d["bytes"]]]
            total = sum(x[1] for x in hist[ip])
            procs = ", ".join(sorted(d["procs"]))
            todos_conocidos = d["procs"] <= conocidos
            limite = self.c["SALIDA_MB"] * 1e6 * (5 if todos_conocidos or d["entrante"] else 1)
            if total < limite or self.protegida(ip):
                continue
            if d["entrante"]:
                self.avisar(f"descarga-{ip}", "media", f"{ip} se ha llevado {mb(total)} del servidor en "
                            f"{self.c['SALIDA_VENTANA_MIN']} min ({procs}). Si no es tuyo, `sudo orion-centinela bloquear {ip}`.")
            elif todos_conocidos:
                self.avisar(f"fuga-{ip}", "media", f"{procs} mandó {mb(total)} a {ip} en {self.c['SALIDA_VENTANA_MIN']} min. "
                            f"Es un programa conocido (puede ser Syncthing o una subida tuya). Si no lo reconoces: "
                            f"`sudo orion-centinela bloquear {ip}`.")
            elif ip not in self.e["bloqueos"]:
                r = self.bloquear(ip, self.c["BLOQUEO_MIN"], f"posible fuga: {mb(total)} por {procs}")
                self.avisar(f"fuga-{ip}", "alta", f"Posible *fuga de datos*: {procs} mandó {mb(total)} a {ip} en "
                            f"{self.c['SALIDA_VENTANA_MIN']} min, y no es un programa conocido. {r} "
                            "Mira qué es con `sudo ss -tnp dst " + ip + "`.")
        self.e["salida"] = {"sockets": actual, "hist": {ip: l for ip, l in hist.items() if l and l[-1][0] > ahora() - ventana}}

    def _huella(self, ruta):
        try:
            datos = Path(ruta).read_bytes()
        except OSError:
            return None
        h = hashlib.sha256(datos).hexdigest()
        RESPALDO.mkdir(parents=True, exist_ok=True, mode=0o700)
        copia = RESPALDO / h
        if not copia.exists():
            fd = os.open(copia, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(datos)
        return h

    def revisar_archivos(self, aceptar=False):
        antes = self.e["huellas"]
        ahora_h = {}
        for patron in VIGILADOS:
            for ruta in sorted(glob.glob(patron)):
                if os.path.isfile(ruta):
                    h = self._huella(ruta)
                    if h:
                        ahora_h[ruta] = h
        if not antes or aceptar:
            self.e["huellas"] = ahora_h
            return
        cambios = []
        for ruta in sorted(set(antes) | set(ahora_h)):
            a, d = antes.get(ruta), ahora_h.get(ruta)
            if a == d:
                continue
            if a is None:
                cambios.append(f"• Nuevo: {ruta}")
            elif d is None:
                cambios.append(f"• Borrado: {ruta}")
            else:
                cambios.append(f"• Cambió: {ruta}")
            if d and ruta not in SECRETOS:
                try:
                    viejo = (RESPALDO / a).read_text(errors="replace") if a else ""
                    cambios += ["   " + l for l in diferencias(viejo, Path(ruta).read_text(errors="replace"), 4)]
                except OSError:
                    pass
        raices = [l.split(":")[0] for l in Path("/etc/passwd").read_text().splitlines() if l.split(":")[2:3] == ["0"]]
        if any(u != "root" for u in raices):
            self.avisar("uid0", "alta", f"Hay usuarios con poderes de root que no son root: {', '.join(u for u in raices if u != 'root')}. "
                        "Eso es típico de una intrusión.")
        if cambios:
            texto = "\n".join(cambios[:25])
            self.avisar("archivos-" + hashlib.sha1(texto.encode()).hexdigest()[:8], "alta" if any(
                k in texto for k in ("authorized_keys", "sudoers", "passwd", "shadow", "ld.so.preload", "pam.d")) else "media",
                "Cambiaron archivos sensibles del servidor:\n" + texto + "\n\nSi fuiste tú (instalaste algo, añadiste "
                "una llave), todo bien. Si no, deshazlo con `sudo orion-centinela restaurar <ruta>`. "
                "Ya guardé la versión anterior.")
            self.e["huellas_previas"] = {**self.e.get("huellas_previas", {}), **{r: antes[r] for r in antes if antes.get(r) != ahora_h.get(r)}}
        self.e["huellas"] = ahora_h

    def revisar_puertos(self, puertos, aceptar=False):
        previos = self.e["puertos"]
        if previos and not aceptar:
            nuevos = {p: proc for p, proc in puertos.items() if p not in previos}
            if nuevos:
                lista = ", ".join(f"{p} ({proc})" for p, proc in nuevos.items())
                self.avisar("puertos-" + "-".join(sorted(nuevos)), "media", f"Hay puertos nuevos escuchando hacia internet: "
                            f"{lista}. Si no instalaste nada, puede ser una puerta trasera. Para cerrarlo: "
                            "`sudo ufw deny <puerto>` y mira el programa con `sudo ss -ltnp`.")
        self.e["puertos"] = puertos

    def revisar_procesos(self, intervalo):
        cpu_previa, cpu_ahora = self.e["cpu"], {}
        tics = os.sysconf("SC_CLK_TCK")
        for d in glob.glob("/proc/[0-9]*"):
            pid = d.rsplit("/", 1)[1]
            try:
                exe = os.readlink(f"{d}/exe")
                stat = Path(f"{d}/stat").read_text()
                comm = stat[stat.index("(") + 1:stat.rindex(")")]
                campos = stat[stat.rindex(")") + 2:].split()
                usado = (int(campos[11]) + int(campos[12])) / tics
            except (OSError, ValueError, IndexError):
                continue
            clave = f"{pid}:{campos[19]}"           # pid + momento de arranque: no confunde pids reciclados
            cpu_ahora[clave] = usado
            pct = 100 * (usado - cpu_previa.get(clave, usado)) / max(intervalo, 1)
            raro = exe.startswith(CARPETAS_RARAS)
            minero = bool(MINEROS.search(comm) or MINEROS.search(exe))
            if not (raro or minero) or clave in self.e["congelados"]:
                continue
            if minero or pct >= self.c["CPU_PCT"]:
                if self.actua():
                    try:
                        os.kill(int(pid), signal.SIGSTOP)
                        self.e["congelados"][clave] = {"pid": int(pid), "exe": exe, "desde": ahora()}
                        self.anotar("congelado", pid=pid, exe=exe, cpu=round(pct))
                        hecho = (f"Lo congelé (no lo maté). Para matarlo: `sudo kill -9 {pid}`; si era tuyo, "
                                 f"`sudo orion-centinela soltar {pid}`.")
                    except OSError as e:
                        hecho = f"No pude congelarlo: {e}"
                else:
                    hecho = f"Modo solo avisar: no lo toqué. `sudo kill -STOP {pid}` lo congela."
                self.avisar(f"proc-{clave}", "alta", f"Programa sospechoso: *{comm}* ({exe}, pid {pid}) gasta {pct:.0f} % "
                            f"de CPU{' y parece un minero de cripto' if minero else ' y corre desde una carpeta temporal'}. {hecho}")
            elif raro:
                self.avisar(f"tmp-{clave}", "media", f"Hay un programa corriendo desde una carpeta temporal: {comm} ({exe}, "
                            f"pid {pid}). No siempre es malo, pero es raro en un servidor. Lo vigilo.")
        self.e["cpu"] = cpu_ahora
        self.e["congelados"] = {k: v for k, v in self.e["congelados"].items() if k in cpu_ahora}

    def ronda(self):
        t0 = ahora()
        intervalo = max(1.0, t0 - self.e.get("ultima", t0 - 60))
        self._mis_ips()
        if self.c["MODO"] == "actuar" and not self.e.get("apagado") and not self.tabla_viva():
            self.encender()            # tras un reinicio la tabla no existe: se vuelve a poner
        for ip in [ip for ip, b in self.e["bloqueos"].items() if b["hasta"] < t0]:
            self.e["bloqueos"].pop(ip)
        for ip in [ip for ip, b in self.e["cf_bloqueos"].items() if b["hasta"] < t0]:
            b = self.e["cf_bloqueos"].pop(ip)
            r = self.cf.soltar(b["id"]) if self.cf else {"success": False, "errors": [{"message": "sin token"}]}
            self.anotar("desbloqueo-cloudflare", ip=ip, **({} if r.get("success") else {"error": web.Cloudflare.error(r)}))
        self.e["confianza"] = {ip: h for ip, h in self.e["confianza"].items() if h > t0}
        self.e["historial"] = {ip: h for ip, h in self.e["historial"].items() if h > t0 - 7 * 86400}
        self.e["avisados"] = {k: h for k, h in self.e["avisados"].items() if h > t0 - 86400}

        _, ss_l, _ = correr("ss", "-Hltunp")
        _, ss_c, _ = correr("ss", "-Htanpi")
        puertos = escuchando(ss_l)
        conns = conexiones(ss_c)
        rx, rxp, tx = contadores_red(Path("/proc/net/dev").read_text())
        previo = self.e.get("red")
        self.e["red"] = [rx, rxp, tx]

        pasos = [
            ("ssh", self.revisar_ssh),
            ("web", self.revisar_web),
            ("excesos", self.revisar_excesos),
            ("conexiones", lambda: self.revisar_conexiones(conns, puertos)),
            ("trafico", lambda: previo and rx >= previo[0] and self.revisar_trafico(
                intervalo, rx - previo[0], rxp - previo[1], tx - previo[2], self._por_ip(conns, puertos))),
            ("salida", lambda: self.revisar_salida(conns, puertos, intervalo)),
            ("archivos", self.revisar_archivos),
            ("puertos", lambda: self.revisar_puertos(puertos)),
            ("procesos", lambda: self.revisar_procesos(intervalo)),
        ]
        for nombre, paso in pasos:
            try:
                paso()
            except Exception as e:      # una revisión rota no apaga las demás
                self.anotar("error", paso=nombre, error=f"{type(e).__name__}: {e}")
        if self.primera_vez:
            self.avisar("encendido", "info", "Centinela encendido. Ya aprendí cómo está el servidor (archivos, puertos) "
                        "y vigilo cada minuto: ataques a SSH, DoS/DDoS, fugas de datos, cambios y programas raros. "
                        f"Modo: {'bloqueo solo y aviso' if self.actua() else 'solo aviso'}.")
        self.e["ultima"] = t0
        self.guardar()

    def _por_ip(self, conns, puertos):
        abiertos = {int(p.split(":")[1]) for p in puertos if p.startswith("tcp:")}
        out = {}
        for c in conns:
            if c["remoto"] is not None and c["lport"] in abiertos and not self.protegida(c["remoto"]):
                out[str(c["remoto"])] = out.get(str(c["remoto"]), 0) + 1
        return out

    # --- para David (y para Orión, que lo llama con sudo) ---

    def lista(self):
        vivos = {ip: b for ip, b in self.e["bloqueos"].items() if b["hasta"] > ahora()}
        vivos.update({ip: {**b, "motivo": "en Cloudflare: " + b["motivo"]} for ip, b in self.e["cf_bloqueos"].items()
                      if b["hasta"] > ahora()})
        if not vivos:
            return "No hay IPs bloqueadas ahora."
        return "\n".join(f"{ip}  hasta {time.strftime('%d/%m %H:%M', time.localtime(b['hasta']))}  ({b['motivo']})"
                         for ip, b in sorted(vivos.items(), key=lambda x: x[1]["hasta"]))

    def resumen(self, n=15):
        modo = "apagado (solo avisa)" if self.e.get("apagado") else ("bloquea y avisa" if self.actua() else "solo avisa")
        lineas = [f"Centinela: {modo}. Reglas en nftables: {'sí' if self.tabla_viva() else 'no'}.",
                  f"Última ronda: {time.strftime('%d/%m %H:%M', time.localtime(self.e.get('ultima', 0)))}.",
                  self._estado_cloudflare(),
                  "", "Bloqueadas:", self.lista(), "", f"Últimos {n} eventos:"]
        try:
            ult = REGISTRO.read_text().splitlines()[-n:]
        except OSError:
            ult = []
        for l in ult:
            try:
                d = json.loads(l)
            except ValueError:
                continue
            lineas.append(f"{d.pop('t')} {d.pop('tipo')}: " + " ".join(f"{k}={v}" for k, v in d.items())[:220])
        return "\n".join(lineas)

    def _estado_cloudflare(self):
        if not self.cf:
            return "Cloudflare: sin token (los ataques que llegan por Cloudflare solo se avisan)."
        nivel = self.cf.nivel()
        if not nivel:
            return "Cloudflare: el token NO funciona (revisa CENTINELA_CF_TOKEN, CENTINELA_CF_ZONA y sus permisos)."
        ua = " · Under Attack puesto por el centinela" if self.e["web"].get("under_attack") else ""
        return f"Cloudflare: conectado, nivel de seguridad {nivel}{ua}."

    def restaurar(self, ruta):
        ruta = os.path.abspath(ruta)
        if not any(fnmatch.fnmatch(ruta, p) for p in VIGILADOS):
            return f"{ruta} no es un archivo vigilado."
        h = self.e.get("huellas_previas", {}).get(ruta)
        if not h or not (RESPALDO / h).exists():
            return f"No tengo una versión anterior de {ruta}."
        datos = (RESPALDO / h).read_bytes()
        try:
            modo = os.stat(ruta).st_mode & 0o7777
        except FileNotFoundError:
            modo = 0o600 if ruta in SECRETOS else 0o644
        tmp = ruta + ".centinela-tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, modo)
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        os.replace(tmp, ruta)
        self.anotar("restaurado", ruta=ruta)
        self.revisar_archivos(aceptar=True)
        return f"{ruta} vuelve a la versión anterior. Si era sshd_config: `sudo sshd -t && sudo systemctl reload ssh`."

    def soltar(self, pid):
        os.kill(int(pid), signal.SIGCONT)
        self.e["congelados"] = {k: v for k, v in self.e["congelados"].items() if v["pid"] != int(pid)}
        self.anotar("soltado", pid=pid)
        return f"Proceso {pid} descongelado."


def web_vivo():
    """Vigila el registro de Caddy cada pocos segundos, para cortar a un atacante a la primera petición."""
    cerrojo = open(BASE / "cerrojo", "w")
    while True:
        espera = 2
        fcntl.flock(cerrojo, fcntl.LOCK_EX)
        try:
            cen = Centinela()
            espera = cen.c["WEB_RAPIDO_S"]
            if not cen.primera_vez:            # hasta la primera ronda no hay nada aprendido
                cen.revisar_web(rapida=True)
                cen.guardar()
        except Exception as e:                  # un fallo no apaga la vigilancia
            print(f"web-vivo: {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            fcntl.flock(cerrojo, fcntl.LOCK_UN)
        time.sleep(max(1, espera))


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "ayuda"):
        return print(__doc__)
    if os.geteuid() != 0:
        sys.exit("Necesito root: sudo orion-centinela " + " ".join(argv))
    orden, args = argv[0], argv[1:]
    BASE.mkdir(parents=True, exist_ok=True)
    if orden == "web-vivo":
        return web_vivo()
    # Una cosa a la vez: la ronda, la vigilancia rápida de la web y las órdenes a mano comparten estado.
    cerrojo = open(BASE / "cerrojo", "w")
    fcntl.flock(cerrojo, fcntl.LOCK_EX)
    cen = Centinela()
    if orden in ("bloquear", "desbloquear", "confiar") and (not args or not ip_valida(args[0])):
        sys.exit(f"Uso: orion-centinela {orden} <IP>")
    if orden == "ronda":
        cen.ronda()
    elif orden == "encender":
        cen.encender()
        cen.anotar("encendido")
    elif orden == "apagar":
        cen.apagar()
    elif orden == "lista":
        print(cen.lista())
    elif orden == "estado":
        print(cen.resumen())
    elif orden == "bloquear":
        minutos = int(args[1]) if len(args) > 1 and args[1].isdigit() else cen.c["BLOQUEO_MIN"]
        print(cen.bloquear(args[0], min(minutos, 30 * 1440), "a mano", a_mano=True))
    elif orden == "desbloquear":
        print(cen.desbloquear(args[0]))
    elif orden == "confiar":
        dias = int(args[1]) if len(args) > 1 and args[1].isdigit() else 30
        cen.confiar(args[0], dias, "a mano")
        print(f"{args[0]} es de confianza por {dias} días: nunca se bloquea.")
    elif orden == "aceptar":
        cen.revisar_archivos(aceptar=True)
        _, ss_l, _ = correr("ss", "-Hltunp")
        cen.revisar_puertos(escuchando(ss_l), aceptar=True)
        cen.anotar("aceptado")
        print("Listo: lo que hay ahora en archivos y puertos queda como lo normal.")
    elif orden == "restaurar" and args:
        print(cen.restaurar(args[0]))
    elif orden == "soltar" and args and args[0].isdigit():
        print(cen.soltar(args[0]))
    else:
        sys.exit(__doc__)
    cen.guardar()


if __name__ == "__main__":
    main(sys.argv[1:])
