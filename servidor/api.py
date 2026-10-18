"""
API de JARVIS para la app del celular.

Corre en el servidor (servidor/README.md) junto a la bóveda. Sirve la app en /app y recibe
pedidos de texto en /api/pedir, que pasan por scripts/jarvis.sh igual que la voz o WhatsApp.
La app de Android (android/) manda el audio a /api/voz: se transcribe aquí con faster-whisper
(el mismo de las notas de voz de WhatsApp) y sigue como un pedido de texto.
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
import select
import subprocess
import sys
import threading
import time
import unicodedata
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

RAIZ = Path(__file__).resolve().parent.parent
REPRODUCIR = RAIZ / "cola" / "reproducir.txt"   # la habilidad musica deja aquí el spotify:... que eligió
APP = Path(__file__).resolve().parent / "app"
HUD_DIR = RAIZ / "hud"
DATOS = RAIZ / "cola" / "app"
CONVERSACION = DATOS / "conversacion.json"
SEGUIR_MIN = 30           # minutos en que un pedido sigue la misma conversación (igual que WhatsApp)
LIMITE_SEG = 20 * 60      # tope de un pedido, como en la cola
MAX_MENSAJES = 200
MAX_AUDIO = 5 * 1024 * 1024    # unos 2 minutos de WAV a 16 kHz; una orden dura segundos
TRANSCRIBIR = [str(RAIZ / "whatsapp" / ".venv" / "bin" / "python"), str(RAIZ / "whatsapp" / "transcribir.py")]
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/manifest+json", ".svg": "image/svg+xml",
         ".png": "image/png"}

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


def cargar_modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


spotify = cargar_modulo("spotify", RAIZ / "voz" / "spotify.py")

NUMEROS = {"una": 1, "un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}


def orden_musica(texto):
    """Órdenes de música que no necesitan a Claude: ("pausar",) ("seguir",) ("saltar", n, atras). None si no es."""
    plano = unicodedata.normalize("NFD", texto.lower())
    plano = re.sub(r"[\u0300-\u036f.,!¡¿?]", "", plano).strip()
    plano = re.sub(r"^(jarvis|orion)\s+", "", plano)
    if re.fullmatch(r"(pausa|pon pausa|para la musica|deten la musica|pausa la musica)", plano):
        return ("pausar",)
    if re.fullmatch(r"(play|dale play|ponle play|sigue|reanuda|continua|sigue la musica)", plano):
        return ("seguir",)
    if re.fullmatch(r"(siguiente|siguiente cancion|pasa la cancion|salta la cancion)", plano):
        return ("saltar", 1, False)
    if re.fullmatch(r"(anterior|cancion anterior|la anterior)", plano):
        return ("saltar", 1, True)
    m = re.fullmatch(r"(pasa|salta|adelanta|retrocede|devuelve|regresa)\s+(\d+|\w+)\s+canciones?", plano)
    if m:
        n = int(m.group(2)) if m.group(2).isdigit() else NUMEROS.get(m.group(2))
        if n and 0 < n <= 20:
            return ("saltar", n, m.group(1) in ("retrocede", "devuelve", "regresa"))
    return None


def musica_al_instante(orden):
    if not spotify.disponible():
        return ("Para controlar Spotify desde aquí, conecta Spotify en el servidor "
                "(servidor/README.md, Música desde el celular).")
    try:
        if orden[0] == "pausar":
            spotify.pausar()
            return "Pausado."
        if orden[0] == "seguir":
            spotify.seguir()
            return "Sigue la música."
        spotify.saltar(orden[1], orden[2])
        return ("Vuelvo " if orden[2] else "Paso ") + (f"{orden[1]} canciones." if orden[1] > 1 else "una canción.")
    except Exception as e:  # sin dispositivo activo, Spotify responde 404
        return f"Spotify no respondió ({e}). Abre Spotify en el celular y dale play una vez."


def ia_externa():
    """scripts/ia_externa.py, para que el PC use las IAs externas con las claves del servidor."""
    spec = importlib.util.spec_from_file_location("ia_externa", RAIZ / "scripts" / "ia_externa.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


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

    def anotar(self, de, texto, **extra):
        with self.cerrojo:
            n = (self.mensajes[-1]["n"] + 1) if self.mensajes else 1
            self.mensajes.append({"n": n, "de": de, "texto": texto, "hora": datetime.now().strftime("%H:%M"), **extra})
            self.mensajes = self.mensajes[-MAX_MENSAJES:]
            self._guardar()
            return n

    def desde(self, n):
        with self.cerrojo:
            return [m for m in self.mensajes if m["n"] > n], self.ocupado > 0

    def pedir(self, texto, origen="app"):
        """Anota el pedido y lo atiende en segundo plano. origen "pc": viene de la voz o el HUD del PC."""
        with self.cerrojo:
            self.ocupado += 1
        n = self.anotar("yo", texto, **({"origen": origen} if origen != "app" else {}))
        threading.Thread(target=self._atender, args=(texto, origen, n), daemon=True).start()
        return n

    def _atender(self, texto, origen="app", n=None):
        try:
            with self.turno:
                orden = orden_musica(texto)
                if orden:
                    self.anotar("jarvis", musica_al_instante(orden), para=n)
                    return
                inicio = time.time()
                respuesta = self._jarvis(texto)
                uri = self._musica_pedida(inicio, poner=origen != "pc")   # el PC la pone en su Spotify
                if uri:
                    self.anotar("jarvis", respuesta, abrir=uri, para=n)
                else:
                    self.anotar("jarvis", respuesta, para=n)
        finally:
            with self.cerrojo:
                self.ocupado -= 1

    @staticmethod
    def _musica_pedida(desde, poner=True):
        """Si JARVIS eligió música en este pedido (cola/reproducir.txt), la pone en el Spotify activo
        (normalmente el del celular) y devuelve la dirección para el botón "Abrir en Spotify"."""
        try:
            if REPRODUCIR.stat().st_mtime < desde - 1:
                return None
            uri = REPRODUCIR.read_text(encoding="utf-8").strip()
            REPRODUCIR.unlink(missing_ok=True)
        except OSError:
            return None
        if not re.fullmatch(r"spotify:[a-z]+:[A-Za-z0-9]+", uri):
            return None
        if poner and spotify.disponible():
            try:
                spotify.reproducir(uri, preferir="Smartphone")   # el pedido viene del celular
            except Exception:
                pass   # sin dispositivo activo: queda el botón para abrir Spotify en el celular
        return uri

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


# ---------- Audio de la app de Android ----------

# Lo que Whisper "oye" en ruido o silencio (lo aprendió de subtítulos de videos): no es un pedido.
FANTASMAS = re.compile(r"^(gracias( por ver( el video)?)?|muchas gracias|subt[ií]tulos.*|suscr[ií]bete.*|"
                       r"amara\.org.*|chao|adi[oó]s|\[.*\]|\(.*\)|\W*)$", re.I)


def es_pedido(texto):
    """Descarta lo que no es una orden: vacío, ruido y las frases fantasma de Whisper."""
    return bool(texto) and not FANTASMAS.match(texto.strip().strip(".,¡!¿? ").strip())

class Transcriptor:
    """Mantiene vivo whatsapp/transcribir.py (cargar el modelo tarda) y le pasa un audio a la vez."""

    def __init__(self, comando=None):
        self.comando = comando or (os.environ.get("JARVIS_TRANSCRIBIR", "").split() or TRANSCRIBIR)
        self.cerrojo = threading.Lock()
        self.proceso = None

    def _linea(self, espera):
        listo, _, _ = select.select([self.proceso.stdout], [], [], espera)
        linea = self.proceso.stdout.readline() if listo else ""
        if not linea:
            raise RuntimeError("el transcriptor no respondió")
        return json.loads(linea)

    def _arrancar(self):
        if self.proceso and self.proceso.poll() is None:
            return
        self.proceso = subprocess.Popen(self.comando, cwd=RAIZ, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._linea(300)   # {"listo": true} cuando el modelo cargó

    def texto(self, ruta):
        with self.cerrojo:
            try:
                self._arrancar()
                self.proceso.stdin.write(f"{ruta}\n")
                self.proceso.stdin.flush()
                r = self._linea(120)
            except (OSError, ValueError, RuntimeError) as e:
                if self.proceso:
                    self.proceso.kill()
                self.proceso = None
                raise RuntimeError(f"no pude transcribir: {e}") from e
        if "error" in r:
            raise RuntimeError(f"no pude transcribir: {r['error']}")
        return r.get("texto", "").strip()


# ---------- HTTP ----------

class Manejador(BaseHTTPRequestHandler):
    timeout = 60          # una conexión que no manda nada no deja un hilo colgado para siempre
    conversacion = None
    token = ""
    modulo_hud = None
    modulo_ia = None
    transcriptor = None

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

    def _archivo(self, nombre, carpeta=APP):
        ruta = (carpeta / nombre).resolve()
        if ruta.parent != carpeta.resolve() or not ruta.is_file():
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
        elif url.path == "/app/propuestas":
            # La misma ventana del HUD; pide los datos con el token que la app guardó.
            self._archivo("propuestas.html", HUD_DIR)
        elif url.path.startswith("/app/vendor/"):
            self._archivo(url.path[12:], HUD_DIR / "vendor")
        elif url.path.startswith("/app/"):
            self._archivo(url.path[5:] or "index.html")
        elif url.path == "/api/ia":
            if self._autorizado():
                ia = self.modulo_ia
                ia.cargar_env()
                self._json({"proveedores": [n for n, p in ia.PROVEEDORES.items() if os.environ.get(p["clave"])]})
        elif url.path == "/api/propuestas":
            if self._autorizado():
                self._json({"propuestas": self.modulo_hud.propuestas_lista()})
        elif url.path.startswith("/api/propuestas/"):
            if self._autorizado():
                datos = self.modulo_hud.propuesta(unquote(url.path[16:]))
                self._json(datos if datos else {"error": "no existe"}, 200 if datos else 404)
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
        ruta = urlparse(self.path).path
        if ruta not in ("/api/pedir", "/api/voz", "/api/ia", "/api/propuestas/borrar"):
            return self._json({"error": "no existe"}, 404)
        if not self._autorizado():
            return
        if ruta == "/api/voz":
            return self._voz()
        if ruta == "/api/ia":
            return self._ia()
        if ruta == "/api/propuestas/borrar":
            try:
                largo = int(self.headers.get("Content-Length", 0))
                if not 0 <= largo <= 200000:
                    return self._json({"error": "largo inválido"}, 413)
                ids = json.loads(self.rfile.read(largo) or b"{}").get("ids", [])
                if not isinstance(ids, list):
                    raise ValueError
            except (ValueError, AttributeError):
                return self._json({"error": "json"}, 400)
            return self._json({"ok": True, "borradas": self.modulo_hud.borrar_propuestas(ids)})
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if not 0 <= largo <= 20000:   # negativo: read(-1) esperaría el fin de la conexión
                return self._json({"error": "largo inválido"}, 413)
            datos = json.loads(self.rfile.read(largo) or b"{}")
            texto = str(datos.get("texto", "")).strip()
            origen = "pc" if datos.get("origen") == "pc" else "app"
        except (ValueError, AttributeError):
            return self._json({"error": "json"}, 400)
        if not texto:
            return self._json({"error": "vacío"}, 400)
        n = self.conversacion.pedir(texto, origen)
        self._json({"ok": True, "n": n}, 202)   # la respuesta llevará "para": n

    def _ia(self):
        """El PC le pide a Gemini u OpenRouter con las claves del servidor (scripts/ia_externa.py)."""
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if not 0 <= largo <= 400000:
                return self._json({"error": "largo inválido"}, 413)
            datos = json.loads(self.rfile.read(largo) or b"{}")
            proveedor, ruta, cuerpo = datos.get("proveedor"), datos.get("ruta"), datos.get("cuerpo")
        except (ValueError, AttributeError):
            return self._json({"error": "json"}, 400)
        ia = self.modulo_ia
        ia.cargar_env()
        # Solo estas dos rutas: el servidor no es un proxy abierto hacia esas APIs.
        if proveedor not in ia.PROVEEDORES or ruta not in ("/models", "/chat/completions") \
                or (ruta == "/chat/completions") != isinstance(cuerpo, dict):
            return self._json({"error": "pedido no permitido"}, 400)
        if not os.environ.get(ia.PROVEEDORES[proveedor]["clave"]):
            return self._json({"error": f"el servidor no tiene {ia.PROVEEDORES[proveedor]['clave']}"}, 404)
        try:
            self._json(ia.llamar(proveedor, ruta, cuerpo))
        except RuntimeError as e:
            self._json({"error": str(e)}, getattr(e, "codigo", 502))

    def _voz(self):
        """Audio WAV de la app de Android: lo transcribe y lo pide como texto. Devuelve lo que entendió."""
        try:
            largo = int(self.headers.get("Content-Length", 0))
        except ValueError:
            largo = 0
        if not 0 < largo <= MAX_AUDIO:
            return self._json({"error": "audio vacío o demasiado largo"}, 413)
        datos = self.rfile.read(largo)
        carpeta = DATOS / "voz"
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / f"{time.time_ns()}.wav"
        archivo.write_bytes(datos)
        try:
            texto = self.transcriptor.texto(str(archivo))
        except RuntimeError as e:
            return self._json({"error": str(e)}, 500)
        finally:
            archivo.unlink(missing_ok=True)
        if not es_pedido(texto):
            return self._json({"texto": ""}, 200)
        n = self.conversacion.pedir(texto)
        self._json({"texto": texto, "n": n}, 202)

    def log_message(self, formato, *args):
        pass


def main():
    p = argparse.ArgumentParser(description="API de Orión para la app del celular")
    p.add_argument("--puerto", type=int, default=int(os.environ.get("JARVIS_API_PUERTO", 7788)))
    args = p.parse_args()
    cargar_env()
    token = os.environ.get("JARVIS_API_TOKEN", "").strip()
    if len(token) < 24:
        sys.exit("Falta JARVIS_API_TOKEN en .env (24 caracteres o más). servidor/instalar.sh lo crea.")
    Manejador.token = token
    Manejador.conversacion = Conversacion()
    Manejador.modulo_hud = hud()
    Manejador.modulo_ia = ia_externa()
    Manejador.transcriptor = Transcriptor()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
    print(f"App de Orión en http://127.0.0.1:{args.puerto}/app/", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
