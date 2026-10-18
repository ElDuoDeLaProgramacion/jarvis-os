"""
El JARVIS del servidor visto desde el PC (servidor/api.py, el mismo que usan las apps del celular).

Con JARVIS_SERVIDOR y JARVIS_API_TOKEN en el .env del PC, la voz y el HUD mandan los pedidos allí:
una sola memoria, un solo .env y la misma conversación que el celular. Lo que necesita el PC
(tus archivos de P:\\, tus proyectos, la pantalla, el copiloto) se sigue haciendo aquí.
"""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Pedidos que solo se pueden hacer en el PC: tocan tus carpetas, tus proyectos o tu pantalla.
EN_EL_PC = re.compile(r"\ben (el|mi|este) (pc|computador|computadora|equipo|portatil)\b")
DEL_PC = re.compile(
    r"\b(archivos?|carpetas?|documentos?|"
    r"pdfs?|excel|word|powerpoint|descargas|escritorio|disco|p:|proyectos?|codigo|repos?|repositorios?|"
    r"scripts?|programa(r|cion)?|pantalla|copiloto|hands.free|deteccion.facial|bot.whatsapp.excel)\b")
AL_SERVIDOR = re.compile(r"\b(en el servidor|del servidor|al servidor)\b")


def _plano(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _env():
    datos = {}
    try:
        for linea in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return {k: os.environ.get(k) or datos.get(k, "") for k in ("JARVIS_SERVIDOR", "JARVIS_API_TOKEN")}


def configurado():
    e = _env()
    return bool(e["JARVIS_SERVIDOR"] and len(e["JARVIS_API_TOKEN"]) >= 24)


def va_al_servidor(pedido):
    """True si este pedido lo atiende el servidor; False si necesita el PC."""
    if not configurado():
        return False
    plano = _plano(pedido)
    if EN_EL_PC.search(plano):
        return False
    if AL_SERVIDOR.search(plano):
        return True
    return not DEL_PC.search(plano)


def nombra_el_servidor(pedido):
    """True si David pidió algo del servidor ("audita el servidor"): eso no se puede hacer en el PC."""
    return bool(AL_SERVIDOR.search(_plano(pedido)))


def _llamar(ruta, cuerpo=None, espera=20):
    e = _env()
    base = re.sub(r"/(app/?)?$", "", e["JARVIS_SERVIDOR"].strip())
    pedido = urllib.request.Request(base + ruta, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                    headers={"Authorization": "Bearer " + e["JARVIS_API_TOKEN"],
                                             "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=espera) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as err:
        if err.code == 401:
            raise ConnectionError("la clave JARVIS_API_TOKEN del PC no coincide con la del servidor") from err
        raise ConnectionError(f"el servidor respondió {err.code}") from err
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise ConnectionError(f"no pude conectar con {base} ({err})") from err


def preguntar(texto, limite_min=20):
    """Pide al servidor y espera su respuesta. Devuelve (texto, spotify:... o None).
    Lanza ConnectionError si el servidor no responde (apagado, sin internet, clave mala)."""
    # Al iniciar sesión, la red tarda unos segundos en conectarse: se reintenta antes de rendirse.
    for intento in range(3):
        try:
            mensajes = _llamar("/api/conversacion?desde=0")["mensajes"]
            break
        except ConnectionError:
            if intento == 2:
                raise
            time.sleep(4)
    desde = mensajes[-1]["n"] if mensajes else 0
    mio = _llamar("/api/pedir", {"texto": texto, "origen": "pc"}).get("n")
    fin = time.monotonic() + limite_min * 60
    while time.monotonic() < fin:
        time.sleep(1.5)
        datos = _llamar(f"/api/conversacion?desde={desde}")
        # Solo la respuesta a este pedido: otro pedido (del celular) puede terminar mientras tanto.
        suyos = [m for m in datos["mensajes"] if m["de"] == "jarvis" and (mio is None or m.get("para") == mio)]
        if mio is None and datos["ocupado"]:
            continue
        if suyos:
            abrir = next((m["abrir"] for m in reversed(suyos) if m.get("abrir")), None)
            return " ".join(m["texto"] for m in suyos), abrir
    return "El servidor sigue trabajando en eso. Te dejo la respuesta en la app del celular.", None
