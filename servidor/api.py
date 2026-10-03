"""
API de JARVIS para la app del celular.

Corre en el servidor (servidor/README.md) junto a la bóveda. Sirve la app en /app y recibe
pedidos de texto en /api/pedir, que pasan por scripts/jarvis.sh igual que la voz o WhatsApp.
Solo usa la biblioteca estándar de Python.

    python3 servidor/api.py            ->  http://127.0.0.1:7788/app

Todo /api/* exige la cabecera "Authorization: Bearer <JARVIS_API_TOKEN>" (.env).
La escucha es solo local: al celular llega por Tailscale (tailscale serve), nunca por internet abierto.
"""

import argparse
import hmac
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
APP = Path(__file__).resolve().parent / "app"
DATOS = RAIZ / "cola" / "app"
CONVERSACION = DATOS / "conversacion.json"
SEGUIR_MIN = 30           # minutos en que un pedido sigue la misma conversación (igual que WhatsApp)
LIMITE_SEG = 20 * 60      # tope de un pedido, como en la cola
MAX_MENSAJES = 200
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".json": "application/manifest+json", ".svg": "image/svg+xml", ".png": "image/png"}

SI = re.compile(r"^(si|sí|sip|dale|claro|confirmo|confirmado|hazlo|envialo|envíalo|mandalo|mándalo"
                r"|de una|ok|okay|listo|adelante)(?=$|[\s.,!?¡¿])", re.I)


def es_si(texto):
    """Mismo criterio que whatsapp/util.mjs (esSi): un "sí" claro, sin "no", "espera" ni "mejor"."""
    plano = texto.lower().strip().strip(" .,!¡¿?")
    return bool(SI.match(plano)) and not re.search(r"\b(no|espera|mejor)\b", plano)


def es_pregunta(respuesta):
    r = respuesta.strip()
    return r.endswith("?") or bool(re.search(r"\?\s*s[ií] o no", r[-160:], re.I))


def cargar_env(archivo=RAIZ / ".env"):
    """Lee .env (KEY=valor) sin pisar lo que ya esté en el entorno."""
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", linea)
        if m and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip("\"'")


def hud():
    """Las funciones del HUD (tareas, plan, comandos) sin duplicarlas."""
    spec = importlib.util.spec_from_file_location("hud_servidor", RAIZ / "hud" / "servidor.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ---------- Conversación ----------

class Conversacion:
    """Mensajes de la app y la conversación de Claude que siguen los pedidos.

    Un solo pedido a la vez: los demás esperan su turno, como en la cola."""

    def __init__(self, archivo=CONVERSACION):
        self.archivo = archivo
        self.cerrojo = threading.Lock()
        self.turno = threading.Lock()
        self.mensajes, self.sesion, self.ocupado = [], None, 0
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
            self.mensajes, self.sesion = datos.get("mensajes", []), datos.get("sesion")
        except (OSError, ValueError):
            pass

    def _guardar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.archivo.with_suffix(".tmp")
        tmp.write_text(json.dumps({"mensajes": self.mensajes, "sesion": self.sesion}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.archivo)

    def anotar(self, de, texto):
        with self.cerrojo:
            n = (self.mensajes[-1]["n"] + 1) if self.mensajes else 1
            self.mensajes.append({"n": n, "de": de, "texto": texto, "hora": datetime.now().strftime("%H:%M")})
            self.mensajes = self.mensajes[-MAX_MENSAJES:]
            self._guardar()
            return n

    def desde(self, n):
        with self.cerrojo:
            return [m for m in self.mensajes if m["n"] > n], self.ocupado > 0

    def pedir(self, texto):
        """Anota el pedido y lo atiende en segundo plano."""
        with self.cerrojo:
            self.ocupado += 1
        self.anotar("yo", texto)
        threading.Thread(target=self._atender, args=(texto,), daemon=True).start()

    def _atender(self, texto):
        try:
            with self.turno:
                self.anotar("jarvis", self._jarvis(texto))
        finally:
            with self.cerrojo:
                self.ocupado -= 1

    def _jarvis(self, texto):
        args = ["--sesion", "--voz"]
        s = self.sesion
        if s and s.get("hasta", 0) > time.time():
            args += ["--reanudar", s["id"]]
            if s.get("pregunto") and es_si(texto):
                args.append("--confirmado")      # "sí" a un "¿lo envío?" de correo, igual que por voz
        guion = os.environ.get("JARVIS_SCRIPT") or str(RAIZ / "scripts" / "jarvis.sh")
        entorno = {**os.environ, "JARVIS_ORIGEN": "app"}
        entorno.pop("JARVIS_AUTOMATICO", None)
        try:
            r = subprocess.run([guion, *args, "--", texto], cwd=RAIZ, env=entorno, capture_output=True,
                               text=True, timeout=LIMITE_SEG, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return "Se me acabó el tiempo con eso. Pídemelo otra vez, más concreto."
        respuesta = r.stdout.strip()
        if r.returncode != 0 or not respuesta:
            ultima = (r.stderr.strip().splitlines() or ["sin detalle"])[-1]
            return f"No pude hacerlo ({ultima[:200]})."
        sesion = next((l[7:].strip() for l in r.stderr.splitlines() if l.startswith("SESION=")), None)
        with self.cerrojo:
            if sesion:
                self.sesion = {"id": sesion, "hasta": time.time() + SEGUIR_MIN * 60,
                               "pregunto": es_pregunta(respuesta)}
            self._guardar()
        return respuesta


# ---------- HTTP ----------

class Manejador(BaseHTTPRequestHandler):
    conversacion = None
    token = ""
    modulo_hud = None

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _autorizado(self):
        dado = self.headers.get("Authorization", "")
        ok = dado.startswith("Bearer ") and hmac.compare_digest(dado[7:].strip().encode(), self.token.encode())
        if not ok:
            self._json({"error": "token"}, 401)
        return ok

    def _archivo(self, nombre):
        ruta = (APP / nombre).resolve()
        if ruta.parent != APP.resolve() or not ruta.is_file():
            return self._json({"error": "no existe"}, 404)
        cuerpo = ruta.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(ruta.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/app"):
            self.send_response(302)
            self.send_header("Location", "/app/")
            self.end_headers()
        elif url.path.startswith("/app/"):
            self._archivo(url.path[5:] or "index.html")
        elif url.path == "/api/conversacion":
            if self._autorizado():
                try:
                    n = int(parse_qs(url.query).get("desde", ["0"])[0])
                except ValueError:
                    n = 0
                mensajes, ocupado = self.conversacion.desde(n)
                self._json({"mensajes": mensajes, "ocupado": ocupado})
        elif url.path == "/api/resumen":
            if self._autorizado():
                h = self.modulo_hud
                self._json({"tareas": h.tareas_abiertas(), "plan": h.plan_de_hoy(),
                            "comandos": [{"etiqueta": e, "pedido": p} for e, p in h.COMANDOS]})
        else:
            self._json({"error": "no existe"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/pedir":
            return self._json({"error": "no existe"}, 404)
        if not self._autorizado():
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if largo > 20000:
                return self._json({"error": "demasiado largo"}, 413)
            texto = str(json.loads(self.rfile.read(largo) or b"{}").get("texto", "")).strip()
        except (ValueError, AttributeError):
            return self._json({"error": "json"}, 400)
        if not texto:
            return self._json({"error": "vacío"}, 400)
        self.conversacion.pedir(texto)
        self._json({"ok": True}, 202)

    def log_message(self, formato, *args):
        pass


def main():
    p = argparse.ArgumentParser(description="API de JARVIS para la app del celular")
    p.add_argument("--puerto", type=int, default=int(os.environ.get("JARVIS_API_PUERTO", 7788)))
    args = p.parse_args()
    cargar_env()
    token = os.environ.get("JARVIS_API_TOKEN", "").strip()
    if len(token) < 24:
        sys.exit("Falta JARVIS_API_TOKEN en .env (24 caracteres o más). servidor/instalar.sh lo crea.")
    Manejador.token = token
    Manejador.conversacion = Conversacion()
    Manejador.modulo_hud = hud()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
    print(f"App de JARVIS en http://127.0.0.1:{args.puerto}/app/", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
