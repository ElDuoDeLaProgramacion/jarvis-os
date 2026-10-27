"""
Sala de Orión Equipo: un chat web compartido para los amigos de ciberseguridad (equipo/README.md).

Cada persona entra con su propia clave (archivo ~/personas: "nombre clave" por línea, lo escribe
equipo/persona.sh). Todos ven la misma sala; Orión atiende un pedido a la vez y sabe quién habla.
No tiene nada del Orión de David: ni billetera, ni música, ni sitios, ni IAs externas; solo
pasa los pedidos a equipo/orion-equipo.sh. Solo usa la biblioteca estándar de Python.

    python3 equipo/servidor.py                       ->  socket /run/orion-equipo/sala.sock (Caddy)
    python3 equipo/servidor.py --puerto 7790         ->  http://127.0.0.1:7790 (pruebas)
"""

import argparse
import hmac
import json
import os
import re
import socketserver
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
HOGAR = Path(os.environ.get("HOME", "/home/equipo"))
PERSONAS = Path(os.environ.get("ORION_EQUIPO_PERSONAS", HOGAR / "personas"))
SALA = Path(os.environ.get("ORION_EQUIPO_SALA", HOGAR / "sala" / "sala.json"))
SEGUIR_MIN = 30           # minutos en que un pedido sigue la misma conversación
LIMITE_SEG = 15 * 60      # tope de un pedido
MAX_MENSAJES = 300
MAX_TEXTO = 4000


def cargar_env(archivo=HOGAR / ".env"):
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", linea)
        if m and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip("\"'")


def leer_personas(archivo=None):
    """{clave: nombre}. Se lee en cada pedido: agregar o quitar a alguien no pide reiniciar."""
    personas = {}
    try:
        archivo = archivo or PERSONAS
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            partes = linea.split()
            if len(partes) == 2 and not linea.startswith("#") and len(partes[1]) >= 24:
                personas[partes[1]] = partes[0]
    except OSError:
        pass
    return personas


def quien(dado, personas):
    """Nombre de la persona dueña de la clave, comparando en tiempo constante. None si no es de nadie."""
    hallado = None
    for clave, nombre in personas.items():
        if hmac.compare_digest(dado.encode(), clave.encode()):
            hallado = nombre
    return hallado


# ---------- Sala ----------

class Sala:
    """Mensajes de todos y la conversación de Claude que los sigue. Un pedido a la vez."""

    def __init__(self, archivo=None, guion=None, limite_dia=40):
        self.archivo = archivo or SALA
        self.guion = guion or str(AQUI / "orion-equipo.sh")
        self.limite_dia = limite_dia
        self.cerrojo = threading.Lock()
        self.turno = threading.Lock()
        self.mensajes, self.sesion, self.ocupado, self.cuenta = [], None, 0, {}
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
            self.mensajes, self.sesion = datos.get("mensajes", []), datos.get("sesion")
            self.cuenta = datos.get("cuenta", {})
        except (OSError, ValueError):
            pass

    def _guardar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.archivo.with_suffix(".tmp")
        tmp.write_text(json.dumps({"mensajes": self.mensajes, "sesion": self.sesion, "cuenta": self.cuenta},
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.archivo)

    def anotar(self, de, texto, **extra):
        with self.cerrojo:
            n = (self.mensajes[-1]["n"] + 1) if self.mensajes else 1
            self.mensajes.append({"n": n, "de": de, "texto": texto,
                                  "hora": datetime.now().strftime("%d/%m %H:%M"), **extra})
            self.mensajes = self.mensajes[-MAX_MENSAJES:]
            self._guardar()
            return n

    def desde(self, n):
        with self.cerrojo:
            return [m for m in self.mensajes if m["n"] > n], self.ocupado > 0

    def gastar(self, nombre):
        """Cuenta un pedido de hoy. False si esa persona ya llegó al tope del día (cuida la clave de la API)."""
        hoy = datetime.now().strftime("%Y-%m-%d")
        with self.cerrojo:
            if self.cuenta.get("dia") != hoy:
                self.cuenta = {"dia": hoy}
            usados = self.cuenta.get(nombre, 0)
            if self.limite_dia and usados >= self.limite_dia:
                return False
            self.cuenta[nombre] = usados + 1
            return True

    def pedir(self, nombre, texto):
        with self.cerrojo:
            self.ocupado += 1
        n = self.anotar(nombre, texto)
        threading.Thread(target=self._atender, args=(nombre, texto, n), daemon=True).start()
        return n

    def _atender(self, nombre, texto, n):
        try:
            with self.turno:
                self.anotar("orion", self._orion(f"{nombre}: {texto}"), para=n)
        finally:
            with self.cerrojo:
                self.ocupado -= 1

    def _orion(self, pedido):
        args = []
        s = self.sesion
        if s and s.get("hasta", 0) > time.time():
            args += ["--reanudar", s["id"]]
        try:
            r = subprocess.run([self.guion, *args, "--", pedido], capture_output=True, text=True,
                               timeout=LIMITE_SEG, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return "Se me acabó el tiempo con eso. Pídemelo otra vez, más concreto."
        respuesta = r.stdout.strip()
        if r.returncode != 0 or not respuesta:
            ultima = (r.stderr.strip().splitlines() or ["sin detalle"])[-1]
            return f"No pude hacerlo ({ultima[:200]})."
        sesion = next((l[7:].strip() for l in r.stderr.splitlines() if l.startswith("SESION=")), None)
        with self.cerrojo:
            if sesion:
                self.sesion = {"id": sesion, "hasta": time.time() + SEGUIR_MIN * 60}
            self._guardar()
        return respuesta


# ---------- HTTP ----------

class Fallos:
    """Tras 5 claves malas en 10 minutos, esa IP espera 15 minutos."""
    MAXIMO, VENTANA, CASTIGO = 5, 600, 900

    def __init__(self):
        self.intentos, self.hasta, self.cerrojo = {}, {}, threading.Lock()

    def bloqueada(self, ip):
        with self.cerrojo:
            return self.hasta.get(ip, 0) > time.time()

    def anotar(self, ip):
        ahora = time.time()
        with self.cerrojo:
            recientes = [t for t in self.intentos.get(ip, []) if ahora - t < self.VENTANA] + [ahora]
            self.intentos[ip] = recientes
            if len(recientes) >= self.MAXIMO:
                self.hasta[ip], self.intentos[ip] = ahora + self.CASTIGO, []
            if len(self.intentos) > 10000:
                self.intentos = {k: v for k, v in self.intentos.items() if v and ahora - v[-1] < self.VENTANA}
                self.hasta = {k: v for k, v in self.hasta.items() if v > ahora}


class Manejador(BaseHTTPRequestHandler):
    timeout = 60
    sala = None
    fallos = None

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                         "img-src 'self' data:; frame-ancestors 'none'")
        super().end_headers()

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _ip(self):
        # Por el socket de Caddy no hay IP: la real viene en X-Forwarded-For.
        directa = self.client_address[0] if isinstance(self.client_address, tuple) else "local"
        return self.headers.get("X-Forwarded-For", "").split(",")[-1].strip() or directa

    def _persona(self):
        ip = self._ip()
        if self.fallos.bloqueada(ip):
            self._json({"error": "demasiados intentos, espera unos minutos"}, 429)
            return None
        dado = self.headers.get("Authorization", "")
        nombre = quien(dado[7:].strip(), leer_personas()) if dado.startswith("Bearer ") else None
        if not nombre:
            self.fallos.anotar(ip)
            self._json({"error": "clave"}, 401)
        return nombre

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            cuerpo = (AQUI / "sala.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(cuerpo)
        elif url.path == "/api/yo":
            nombre = self._persona()
            if nombre:
                self._json({"nombre": nombre})
        elif url.path == "/api/sala":
            if self._persona():
                try:
                    n = int(parse_qs(url.query).get("desde", ["0"])[0])
                except ValueError:
                    n = 0
                mensajes, ocupado = self.sala.desde(n)
                self._json({"mensajes": mensajes, "ocupado": ocupado})
        else:
            self._json({"error": "no existe"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/pedir":
            return self._json({"error": "no existe"}, 404)
        nombre = self._persona()
        if not nombre:
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if not 0 <= largo <= 20000:
                return self._json({"error": "largo inválido"}, 413)
            texto = str(json.loads(self.rfile.read(largo) or b"{}").get("texto", "")).strip()
        except (ValueError, AttributeError):
            return self._json({"error": "json"}, 400)
        if not texto:
            return self._json({"error": "vacío"}, 400)
        if len(texto) > MAX_TEXTO:
            return self._json({"error": f"máximo {MAX_TEXTO} caracteres"}, 413)
        if not self.sala.gastar(nombre):
            return self._json({"error": "llegaste al tope de pedidos de hoy; mañana sigues"}, 429)
        self._json({"ok": True, "n": self.sala.pedir(nombre, texto)}, 202)

    def log_message(self, formato, *args):
        pass


class ServidorUnix(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    p = argparse.ArgumentParser(description="Sala web de Orión Equipo")
    p.add_argument("--puerto", type=int, help="escuchar en 127.0.0.1:PUERTO en vez del socket")
    p.add_argument("--socket", default=os.environ.get("ORION_EQUIPO_SOCKET", "/run/orion-equipo/sala.sock"))
    args = p.parse_args()
    cargar_env()
    Manejador.sala = Sala(limite_dia=int(os.environ.get("ORION_EQUIPO_LIMITE_DIA", "40") or 0))
    Manejador.fallos = Fallos()
    if args.puerto:
        servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
        print(f"Sala de Orión Equipo en http://127.0.0.1:{args.puerto}/", flush=True)
    else:
        # Un socket de archivo, no un puerto: así el servicio puede tener prohibida toda la red local
        # (equipo/instalar.sh, IPAddressDeny) y aun así Caddy le llega.
        Path(args.socket).unlink(missing_ok=True)
        servidor = ServidorUnix(args.socket, Manejador)
        os.chmod(args.socket, 0o666)
        print(f"Sala de Orión Equipo en {args.socket}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
