"""
Control de Spotify con la API oficial (Web API), para lo que las teclas multimedia no pueden:
poner una lista, un álbum o un artista concreto y que empiece a sonar, y saltar varias canciones.

Necesita Spotify Premium (la API no deja controlar la reproducción en cuentas gratis) y una app
de desarrollador propia (gratis). Una sola vez:
  1. https://developer.spotify.com/dashboard -> Create app.
     Redirect URI: http://127.0.0.1:8888/callback   ·   API: Web API
  2. Copia el Client ID en .env:  SPOTIFY_CLIENT_ID=...
  3. En PowerShell, dentro de P:\\jarvis-os:  voz\\.venv\\Scripts\\python voz\\spotify.py --login
     Se abre el navegador, aceptas con la cuenta de la app de Spotify del PC y listo.

Sin esto, la voz sigue funcionando como antes (abre la dirección spotify: y usa las teclas).
"""

import base64
import hashlib
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TOKEN = Path(__file__).resolve().parent / ".spotify-token.json"   # no va a git
REDIRECT = "http://127.0.0.1:8888/callback"
PERMISOS = "user-read-playback-state user-modify-playback-state"
API = "https://api.spotify.com/v1"


def client_id():
    if os.environ.get("SPOTIFY_CLIENT_ID"):
        return os.environ["SPOTIFY_CLIENT_ID"]
    env = RAIZ / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*SPOTIFY_CLIENT_ID\s*=\s*(\S+)", linea)
            if m:
                return m.group(1).strip("\"'")
    return ""


def disponible():
    return bool(client_id()) and TOKEN.exists()


def _cuenta(datos):
    pedido = urllib.request.Request("https://accounts.spotify.com/api/token",
                                    data=urllib.parse.urlencode(datos).encode(),
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=15) as r:
        nuevo = json.loads(r.read())
    viejo = json.loads(TOKEN.read_text()) if TOKEN.exists() else {}
    viejo.update(nuevo)
    viejo["vence"] = time.time() + nuevo.get("expires_in", 3600) - 60
    TOKEN.write_text(json.dumps(viejo))
    return viejo


def _token():
    datos = json.loads(TOKEN.read_text())
    if time.time() > datos.get("vence", 0):
        datos = _cuenta({"grant_type": "refresh_token", "refresh_token": datos["refresh_token"],
                         "client_id": client_id()})
    return datos["access_token"]


def _api(metodo, ruta, cuerpo=None):
    pedido = urllib.request.Request(API + ruta, method=metodo,
                                    data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                    headers={"Authorization": f"Bearer {_token()}",
                                             "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=15) as r:
        texto = r.read()
        return json.loads(texto) if texto.strip() else {}


def _dispositivo(preferir=None):
    """El tipo preferido si está abierto (la app del celular pide "Smartphone"); si no, el que esté
    sonando; si ninguno, el Spotify de este PC (tiene que estar abierto)."""
    lista = _api("GET", "/me/player/devices").get("devices", [])
    preferido = next((d for d in lista if preferir and d.get("type") == preferir), None)
    activo = next((d for d in lista if d.get("is_active")), None)
    return (preferido or activo or next((d for d in lista if d.get("type") == "Computer"), None) or
            (lista[0] if lista else None))


def reproducir(uri, preferir=None):
    """Pone a sonar una canción, lista, álbum o artista (spotify:...). True si lo logró."""
    dispositivo = _dispositivo(preferir)
    if not dispositivo:
        return False
    cuerpo = {"uris": [uri]} if uri.startswith(("spotify:track:", "spotify:episode:")) else {"context_uri": uri}
    _api("PUT", f"/me/player/play?device_id={dispositivo['id']}", cuerpo)
    return True


def pausar():
    _api("PUT", "/me/player/pause")


def seguir():
    _api("PUT", "/me/player/play")


def saltar(n, atras=False):
    for _ in range(n):
        _api("POST", "/me/player/previous" if atras else "/me/player/next")
        time.sleep(0.25)


def login():
    if not client_id():
        sys.exit("Falta SPOTIFY_CLIENT_ID en .env (mira las instrucciones al principio de voz/spotify.py).")
    verificador = secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(16)
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id(), "response_type": "code", "redirect_uri": REDIRECT, "scope": PERMISOS,
        "code_challenge_method": "S256", "code_challenge": reto, "state": estado})
    recibido = {}

    class Vuelta(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            recibido.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Listo. Ya puedes cerrar esta pestaña y volver a JARVIS.".encode())

    import webbrowser
    webbrowser.open(url)
    # En el servidor no hay navegador: se abre este enlace en el PC, con el túnel
    # ssh -L 8888:127.0.0.1:8888 abierto (servidor/README.md, "Música desde el celular").
    print("Acepta en el navegador. Si no se abrió solo, abre este enlace:\n\n" + url + "\n")
    HTTPServer(("127.0.0.1", 8888), Vuelta).handle_request()
    if recibido.get("state", [""])[0] != estado or "code" not in recibido:
        sys.exit(f"No se completó el permiso: {recibido.get('error', ['desconocido'])[0]}")
    _cuenta({"grant_type": "authorization_code", "code": recibido["code"][0], "redirect_uri": REDIRECT,
             "client_id": client_id(), "code_verifier": verificador})
    print("Spotify conectado. Reinicia la voz de JARVIS (o la app en el servidor: sudo systemctl restart jarvis-app).")


if __name__ == "__main__":
    if "--login" in sys.argv:
        login()
    else:
        print(__doc__)
