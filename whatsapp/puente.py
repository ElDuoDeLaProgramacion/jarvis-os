#!/usr/bin/env python3
"""
Puente de WhatsApp para JARVIS (Kapso, la API oficial de WhatsApp Cloud).

JARVIS tiene su propio número. David le escribe desde el celular y JARVIS contesta por ahí mismo.

    ./whatsapp/iniciar.sh            (lo arranca la tarea de inicio de Windows)

Qué hace:
  1. Abre un túnel gratis de Cloudflare (cloudflared) hacia este puente: así Kapso puede avisar
     de cada mensaje nuevo sin abrir puertos en el router.
  2. Apunta el webhook de Kapso a la dirección del túnel (cambia cada vez que arranca).
  3. Recibe los mensajes, comprueba la firma (HMAC SHA256) y que vengan de un número permitido.
  4. Pasa el texto a ./scripts/jarvis.sh y manda la respuesta por WhatsApp.

Solo obedece a los números de WHATSAPP_PERMITIDOS. Lo que escriba cualquier otra persona se
guarda en boveda/raw/whatsapp/ y no se ejecuta.

Variables en .env:
  KAPSO_API_KEY           clave del proyecto en Kapso (no se sube a git)
  KAPSO_PHONE_NUMBER_ID   id del número de JARVIS en Kapso
  KAPSO_WEBHOOK_SECRET    secreto para firmar los avisos (lo genera whatsapp/instalar.sh)
  WHATSAPP_PERMITIDOS     tu número con código de país, sin + ni espacios (varios, separados por coma)
"""

import hashlib
import hmac
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 7778
RUTA = "/whatsapp/jarvis"                  # la ruta del webhook; así reconocemos el nuestro en Kapso
API = "https://api.kapso.ai"
META = f"{API}/meta/whatsapp/v24.0"
PLATAFORMA = f"{API}/platform/v1"
SEGUIR_MIN = 30                            # minutos en que un mensaje sigue la misma conversación
LOG = RAIZ / "logs" / "whatsapp.log"


def log(*partes):
    texto = " ".join(str(p) for p in partes)
    print(texto, flush=True)
    try:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")
    except OSError:
        pass


def cargar_env():
    archivo = RAIZ / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$", linea)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2).strip().strip('"').strip("'")


def solo_digitos(numero):
    return re.sub(r"\D", "", str(numero or ""))


# ---------- Kapso ----------

def kapso(metodo, url, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pedido = urllib.request.Request(url, data=datos, method=metodo, headers={
        "X-API-Key": os.environ["KAPSO_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=30) as r:
        texto = r.read().decode("utf-8", "replace")
        return json.loads(texto) if texto.strip() else {}


def enviar_texto(numero, texto, phone_number_id=None):
    pnid = phone_number_id or os.environ["KAPSO_PHONE_NUMBER_ID"]
    for trozo in partir(texto):
        kapso("POST", f"{META}/{pnid}/messages", {
            "messaging_product": "whatsapp", "to": solo_digitos(numero),
            "type": "text", "text": {"body": trozo}})


def partir(texto, largo=3500):
    """WhatsApp corta los mensajes muy largos: los mandamos en trozos por párrafos."""
    trozos, actual = [], ""
    for parrafo in texto.split("\n"):
        while len(parrafo) > largo:                 # un párrafo enorme va en varios trozos
            trozos += [actual] if actual else []
            trozos.append(parrafo[:largo])
            actual, parrafo = "", parrafo[largo:]
        if len(actual) + len(parrafo) + 1 > largo and actual:
            trozos.append(actual)
            actual = ""
        actual += ("\n" if actual else "") + parrafo
    return trozos + ([actual] if actual else [])


def lista(respuesta):
    if isinstance(respuesta, list):
        return respuesta
    for clave in ("data", "webhooks", "whatsapp_webhooks", "items", "results"):
        if isinstance(respuesta.get(clave), list):
            return respuesta[clave]
    return []


def apuntar_webhook(base):
    """Kapso debe avisar a la dirección del túnel de hoy: actualiza nuestro webhook o lo crea."""
    url = base.rstrip("/") + RUTA
    pnid = os.environ["KAPSO_PHONE_NUMBER_ID"]
    secreto = os.environ["KAPSO_WEBHOOK_SECRET"]
    try:
        existentes = lista(kapso("GET", f"{PLATAFORMA}/whatsapp_webhooks?per_page=100"))
    except urllib.error.HTTPError as e:
        log("Kapso: no pude listar los webhooks:", e.code, e.read()[:300])
        existentes = []
    nuestro = next((w for w in existentes if str(w.get("url", "")).endswith(RUTA)), None)
    if nuestro:
        kapso("PATCH", f"{PLATAFORMA}/whatsapp_webhooks/{nuestro['id']}",
              {"url": url, "secret_key": secreto, "active": True})
        log("Kapso: webhook actualizado ->", url)
    else:
        kapso("POST", f"{PLATAFORMA}/whatsapp/phone_numbers/{pnid}/webhooks",
              {"url": url, "secret_key": secreto, "events": ["whatsapp.message.received"], "active": True})
        log("Kapso: webhook creado ->", url)


# ---------- Mensajes ----------

def firma_valida(cuerpo, firma):
    esperada = hmac.new(os.environ["KAPSO_WEBHOOK_SECRET"].encode(), cuerpo, hashlib.sha256).hexdigest()
    return bool(firma) and hmac.compare_digest(esperada, firma.strip().lower())


def mensajes_de(evento):
    """Del aviso de Kapso (suelto o en lote) saca (número, tipo, texto, phone_number_id)."""
    if evento.get("batch") and isinstance(evento.get("data"), list):
        piezas = evento["data"]
    elif isinstance(evento.get("data"), dict):
        piezas = [evento["data"]]
    else:
        piezas = [evento]
    for p in piezas:
        msg, conv, cfg = p.get("message") or {}, p.get("conversation") or {}, p.get("whatsapp_config") or {}
        if str(msg.get("direction", "inbound")).lower() not in ("inbound", "incoming", "received"):
            continue
        texto = (msg.get("content") or (msg.get("text") or {}).get("body")
                 or (msg.get("kapso") or {}).get("content") or "")
        numero = msg.get("from") or msg.get("phone_number") or conv.get("phone_number") or ""
        tipo = msg.get("message_type") or msg.get("type") or "text"
        pnid = cfg.get("phone_number_id") or conv.get("phone_number_id") or msg.get("phone_number_id")
        if numero:
            yield solo_digitos(numero), tipo, str(texto).strip(), pnid


SI = re.compile(r"^(si|sí|sip|dale|claro|confirmo|confirmado|hazlo|envialo|envíalo|mandalo|mándalo|"
                r"de una|ok|okay|listo|adelante)\b", re.I)


def es_si(texto):
    plano = texto.lower().strip(" .,!¡¿?")
    return bool(SI.match(plano)) and not re.search(r"\bno\b|\bespera\b|\bmejor\b", plano)


def es_pregunta(respuesta):
    return respuesta.strip().endswith("?") or bool(re.search(r"\?\s*s[ií] o no", respuesta[-160:].lower()))


def limpiar(texto):
    """WhatsApp no entiende Markdown completo: dejamos *negrita* simple y quitamos lo demás."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"*\1*", texto)
    texto = re.sub(r"^#+\s*", "", texto, flags=re.M)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", texto).strip()


def guardar_ajeno(numero, texto):
    """Mensajes de números no permitidos: solo se anotan en la bóveda."""
    carpeta = RAIZ / "boveda" / "raw" / "whatsapp"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{datetime.now():%Y-%m-%d}-mensajes.md"
    if not archivo.exists():
        archivo.write_text(f"---\nfecha: {datetime.now():%Y-%m-%d}\ntipo: captura\ntags: [whatsapp]\n---\n"
                           "# Mensajes al número de JARVIS (no ejecutados)\n\n", encoding="utf-8")
    with archivo.open("a", encoding="utf-8") as f:
        f.write(f"- {datetime.now():%H:%M} +{numero}: {texto}\n")


def registrar(pedido, respuesta):
    """Aparece en la actividad del HUD, como lo de la voz."""
    try:
        destino = RAIZ / "cola" / "hechas" / f"{datetime.now():%Y%m%d-%H%M%S}-whatsapp.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        seguro = pedido.replace('"', '\\"')
        destino.write_text(f'---\npedido: "{seguro}"\norigen: whatsapp\ncreado: '
                           f'{datetime.now().isoformat(timespec="seconds")}\n---\n'
                           f"\n## Resultado (hecha, whatsapp)\n\n{respuesta}\n", encoding="utf-8")
    except OSError:
        pass


class Trabajador(threading.Thread):
    """Atiende los mensajes de uno en uno, en orden de llegada."""

    def __init__(self):
        super().__init__(daemon=True)
        self.cola = queue.Queue()
        self.sesiones = {}      # número -> (id de conversación, hasta cuándo sigue, ¿JARVIS preguntó?)

    def run(self):
        while True:
            numero, tipo, texto, pnid = self.cola.get()
            try:
                self.atender(numero, tipo, texto, pnid)
            except Exception as e:  # un mensaje raro nunca tumba el puente
                log("Error atendiendo un mensaje:", repr(e))

    def atender(self, numero, tipo, texto, pnid):
        if tipo != "text" or not texto:
            enviar_texto(numero, "Por ahora solo entiendo mensajes de texto.", pnid)
            return
        log(f"\nWhatsApp +{numero}: {texto}")
        sesion, hasta, pregunto = self.sesiones.get(numero, (None, 0, False))
        reanudar = sesion if sesion and time.time() < hasta else None
        cmd = ["./scripts/jarvis.sh", "--sesion", "--voz"]
        if reanudar:
            cmd += ["--reanudar", reanudar]
            if pregunto and es_si(texto):
                cmd.append("--confirmado")   # "sí" a un "¿Lo envío?", igual que por voz
        pedido = f"{texto}\n\n(Llega por WhatsApp desde el celular de David: responde corto, apto para leer en el móvil.)"
        r = subprocess.run(cmd + ["--", pedido], cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=900)
        nueva = next((l[7:].strip() for l in r.stderr.splitlines() if l.startswith("SESION=")), None)
        respuesta = r.stdout.strip() if r.returncode == 0 else "Hubo un error al ejecutar el pedido. Quedó en logs/jarvis.log."
        respuesta = limpiar(respuesta) or "Listo."
        if nueva:
            self.sesiones[numero] = (nueva, time.time() + SEGUIR_MIN * 60, es_pregunta(respuesta))
        log(f"JARVIS -> +{numero}: {respuesta}")
        registrar(texto, respuesta)
        enviar_texto(numero, respuesta, pnid)


class Manejador(BaseHTTPRequestHandler):
    trabajador = None
    vistos = {}                 # X-Idempotency-Key -> cuándo; Kapso reintenta si tardamos

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/estado" else 404)
        self.end_headers()

    def do_POST(self):
        if self.path.split("?")[0] != RUTA:
            self.send_response(404)
            return self.end_headers()
        largo = int(self.headers.get("Content-Length", 0))
        if largo > 2_000_000:
            self.send_response(413)
            return self.end_headers()
        cuerpo = self.rfile.read(largo)
        if not firma_valida(cuerpo, self.headers.get("X-Webhook-Signature", "")):
            log("Aviso rechazado: firma inválida.")
            self.send_response(401)
            return self.end_headers()
        # Kapso pide un 200 en menos de 10 s: contestamos ya y trabajamos después.
        self.send_response(200)
        self.end_headers()
        clave = self.headers.get("X-Idempotency-Key")
        ahora = time.time()
        for k in [k for k, t in self.vistos.items() if ahora - t > 3600]:
            del self.vistos[k]
        if clave:
            if clave in self.vistos:
                return
            self.vistos[clave] = ahora
        try:
            evento = json.loads(cuerpo or b"{}")
        except json.JSONDecodeError:
            return
        tipo_evento = self.headers.get("X-Webhook-Event") or evento.get("type") or ""
        if tipo_evento and tipo_evento != "whatsapp.message.received":
            return
        permitidos = {solo_digitos(n) for n in os.environ.get("WHATSAPP_PERMITIDOS", "").split(",") if n.strip()}
        for numero, tipo, texto, pnid in mensajes_de(evento):
            if numero in permitidos:
                self.trabajador.cola.put((numero, tipo, texto, pnid))
            else:
                log(f"Mensaje de +{numero} (no permitido), guardado sin ejecutar.")
                guardar_ajeno(numero, texto or f"({tipo})")


def abrir_tunel():
    """cloudflared crea una dirección https://....trycloudflare.com que llega a este puente."""
    proc = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PUERTO}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    for linea in proc.stderr:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", linea)
        if m:
            threading.Thread(target=lambda: [None for _ in proc.stderr], daemon=True).start()  # vaciar el resto
            return proc, m.group(0)
    raise RuntimeError("cloudflared no dio una dirección. ¿Está instalado? Ejecuta whatsapp/instalar.sh")


def main():
    cargar_env()
    faltan = [v for v in ("KAPSO_API_KEY", "KAPSO_PHONE_NUMBER_ID", "KAPSO_WEBHOOK_SECRET", "WHATSAPP_PERMITIDOS")
              if not os.environ.get(v)]
    if faltan:
        log("Falta en .env:", ", ".join(faltan), "(ver whatsapp/README.md)")
        sys.exit(1)
    trabajador = Trabajador()
    trabajador.start()
    Manejador.trabajador = trabajador
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    proc, base = abrir_tunel()
    log("Túnel listo:", base)
    apuntar_webhook(base)
    log("WhatsApp de JARVIS en línea. Escríbele desde", os.environ["WHATSAPP_PERMITIDOS"])
    try:
        proc.wait()          # si el túnel se cae, salimos y la tarea de inicio lo vuelve a lanzar
    finally:
        servidor.shutdown()
    sys.exit(1)


if __name__ == "__main__":
    main()
