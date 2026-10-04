"""Pruebas de la API de la app (sin Claude: un jarvis.sh falso). python3 -m unittest servidor/test_api.py"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api  # noqa: E402

FALSO = """#!/usr/bin/env bash
echo "$*" >> "$REGISTRO"
pedido="${@: -1}"
echo "SESION=s1" >&2
case "$pedido" in
  *correo*) echo "Listo el borrador para Ana. ¿Lo envío?" ;;
  *falla*) echo "se rompió" >&2; exit 1 ;;
  *queen*) echo "spotify:playlist:37i9dQZF1DX" > "$REPRO"; echo "Pongo Queen." ;;
  *tarda*) sleep 1; echo "Por fin: $pedido" ;;
  *) echo "Hecho: $pedido" ;;
esac
"""


# Transcriptor falso: el "audio" es texto plano; "ruido" no se entiende.
TRANSCRIPTOR_FALSO = """import json, sys
print(json.dumps({"listo": True}), flush=True)
for linea in sys.stdin:
    ruta = linea.strip()
    texto = open(ruta, encoding="utf-8").read()
    print(json.dumps({"ruta": ruta, "texto": "" if texto == "ruido" else texto}), flush=True)
"""


class SpotifyFalso:
    def __init__(self):
        self.llamadas = []

    def disponible(self):
        return True

    def pausar(self):
        self.llamadas.append("pausar")

    def seguir(self):
        self.llamadas.append("seguir")

    def saltar(self, n, atras=False):
        self.llamadas.append(("saltar", n, atras))

    def reproducir(self, uri, preferir=None):
        self.llamadas.append(("reproducir", uri, preferir))
        return True


class PruebaApi(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        guion = self.dir / "jarvis.sh"
        guion.write_text(FALSO)
        guion.chmod(0o755)
        self.registro = self.dir / "registro.txt"
        os.environ.update(JARVIS_SCRIPT=str(guion), REGISTRO=str(self.registro), REPRO=str(self.dir / "reproducir.txt"))
        api.REPRODUCIR = self.dir / "reproducir.txt"
        api.spotify = self.spotify = SpotifyFalso()
        api.Manejador.token = "t" * 30
        api.Manejador.conversacion = api.Conversacion(self.dir / "conversacion.json")
        api.Manejador.modulo_hud = api.hud()
        api.DATOS = self.dir
        falso = self.dir / "transcribir.py"
        falso.write_text(TRANSCRIPTOR_FALSO)
        api.Manejador.transcriptor = api.Transcriptor([sys.executable, str(falso)])
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Manejador)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def pedir(self, ruta, datos=None, token="t" * 30):
        req = urllib.request.Request(self.base + ruta, data=json.dumps(datos).encode() if datos else None,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())

    def esperar(self):
        for _ in range(100):
            _, d = self.pedir("/api/conversacion")
            if not d["ocupado"]:
                return d["mensajes"]
            time.sleep(0.05)
        self.fail("no terminó")

    def test_sin_token_401(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.pedir("/api/conversacion", token="otro")
        self.assertEqual(e.exception.code, 401)

    def test_app_sin_token(self):
        with urllib.request.urlopen(self.base + "/app/") as r:
            self.assertIn(b"JARVIS", r.read())
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base + "/app/../api.py")

    def test_conversacion_y_si_confirmado(self):
        self.assertEqual(self.pedir("/api/pedir", {"texto": "redacta un correo a Ana"})[0], 202)
        m = self.esperar()
        self.assertEqual([x["de"] for x in m], ["yo", "jarvis"])
        self.assertIn("¿Lo envío?", m[1]["texto"])
        self.pedir("/api/pedir", {"texto": "sí"})
        m = self.esperar()
        self.assertEqual(len(m), 4)
        llamadas = self.registro.read_text().splitlines()
        self.assertEqual(llamadas[0], "--sesion --voz -- redacta un correo a Ana")
        self.assertEqual(llamadas[1], "--sesion --voz --reanudar s1 --confirmado -- sí")
        # Un "sí" que no responde a una pregunta no confirma nada.
        self.pedir("/api/pedir", {"texto": "sí"})
        self.esperar()
        self.assertNotIn("--confirmado", self.registro.read_text().splitlines()[2])
        _, d = self.pedir("/api/conversacion?desde=4")
        self.assertEqual([x["n"] for x in d["mensajes"]], [5, 6])

    def test_error_legible(self):
        self.pedir("/api/pedir", {"texto": "esto falla"})
        self.assertIn("se rompió", self.esperar()[-1]["texto"])

    def test_resumen(self):
        _, d = self.pedir("/api/resumen")
        self.assertTrue(d["comandos"])
        self.assertIn("prioridades", d["plan"])

    def test_propuestas(self):
        h = api.Manejador.modulo_hud
        h.PANELES = self.dir / "panel"
        carpeta = h.PANELES / "2026-10-04-landing"
        carpeta.mkdir(parents=True)
        (carpeta / "panel-marketing.json").write_text(json.dumps(
            {"rol": "marketing", "pregunta": "p", "respuestas": [{"modelo": "m", "texto": "```html\n<b>x</b>\n```"}]}))
        (h.PANELES / "2026-10-04-landing.md").write_text("# Conclusión")
        _, d = self.pedir("/api/propuestas")
        self.assertEqual(d["propuestas"][0]["roles"], ["marketing"])
        self.assertTrue(d["propuestas"][0]["conclusion"])
        _, d = self.pedir("/api/propuestas/2026-10-04-landing")
        self.assertEqual(d["conclusion"], "# Conclusión")
        self.assertEqual(d["paneles"][0]["respuestas"][0]["modelo"], "m")
        for ruta in ("/api/propuestas/..", "/api/propuestas/..%2F..%2Fservidor", "/api/propuestas/nada"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.pedir(ruta)
            self.assertEqual(e.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.pedir("/api/propuestas", token="otro")
        self.assertEqual(e.exception.code, 401)
        # La ventana y sus bibliotecas se sirven sin clave (los datos no); nada fuera de hud/vendor.
        with urllib.request.urlopen(self.base + "/app/propuestas") as r:
            self.assertIn(b"PROPUESTAS", r.read())
        with urllib.request.urlopen(self.base + "/app/vendor/marked.js") as r:
            self.assertIn("javascript", r.headers["Content-Type"])
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base + "/app/vendor/..%2Fservidor.py")

    def test_musica_al_instante_sin_claude(self):
        self.pedir("/api/pedir", {"texto": "Jarvis, pasa tres canciones"})
        m = self.esperar()
        self.assertEqual(m[-1]["texto"], "Paso 3 canciones.")
        self.assertEqual(self.spotify.llamadas, [("saltar", 3, False)])
        self.assertFalse(self.registro.exists())   # no pasó por jarvis.sh

    def test_pon_musica_suena_y_deja_boton(self):
        self.pedir("/api/pedir", {"texto": "pon algo de queen"})
        m = self.esperar()
        self.assertEqual(m[-1]["abrir"], "spotify:playlist:37i9dQZF1DX")
        self.assertEqual(self.spotify.llamadas, [("reproducir", "spotify:playlist:37i9dQZF1DX", "Smartphone")])
        self.assertFalse((self.dir / "reproducir.txt").exists())

    def test_pc_pone_la_musica_en_su_spotify(self):
        self.pedir("/api/pedir", {"texto": "pon algo de queen", "origen": "pc"})
        m = self.esperar()
        self.assertEqual(m[0]["origen"], "pc")
        self.assertEqual(m[-1]["abrir"], "spotify:playlist:37i9dQZF1DX")
        self.assertEqual(self.spotify.llamadas, [])   # el servidor no la pone en el celular

    def test_largo_negativo_no_cuelga(self):
        import socket
        with socket.create_connection(self.srv.server_address, timeout=5) as s:
            s.sendall(b"POST /api/pedir HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + b"t" * 30 +
                      b"\r\nContent-Length: -1\r\n\r\n")
            self.assertIn(b" 413 ", s.recv(200))

    def test_el_pc_pregunta_al_servidor(self):
        sys.path.insert(0, str(api.RAIZ / "voz"))
        import servidor_remoto
        os.environ.update(JARVIS_SERVIDOR=self.base + "/app/", JARVIS_API_TOKEN="t" * 30)
        try:
            self.assertTrue(servidor_remoto.va_al_servidor("prueba la seguridad del servidor"))
            self.assertFalse(servidor_remoto.va_al_servidor("busca el PDF en Descargas"))
            self.assertEqual(servidor_remoto.preguntar("plan de hoy"), ("Hecho: plan de hoy", None))
            self.assertEqual(servidor_remoto.preguntar("pon algo de queen")[1], "spotify:playlist:37i9dQZF1DX")
            # Un pedido del celular que termina mientras tanto no se mezcla con la respuesta del PC.
            self.pedir("/api/pedir", {"texto": "esto tarda"})
            self.assertEqual(servidor_remoto.preguntar("plan de hoy"), ("Hecho: plan de hoy", None))
            os.environ["JARVIS_API_TOKEN"] = "x" * 30
            with self.assertRaises(ConnectionError):
                servidor_remoto.preguntar("plan de hoy")
        finally:
            for k in ("JARVIS_SERVIDOR", "JARVIS_API_TOKEN"):
                os.environ.pop(k, None)

    def voz(self, audio):
        req = urllib.request.Request(self.base + "/api/voz", data=audio,
                                     headers={"Authorization": "Bearer " + "t" * 30, "Content-Type": "audio/wav"})
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())

    def test_voz_transcribe_y_pide(self):
        self.assertEqual(self.voz("qué tengo hoy".encode()), (202, {"texto": "qué tengo hoy", "n": 1}))
        m = self.esperar()
        self.assertEqual(m[0]["texto"], "qué tengo hoy")
        self.assertEqual(m[1]["texto"], "Hecho: qué tengo hoy")
        self.assertEqual(list((self.dir / "voz").iterdir()), [])   # el audio no se queda guardado
        # Lo que no se entiende no se pide, ni las frases que Whisper inventa con ruido.
        self.assertEqual(self.voz(b"ruido"), (200, {"texto": ""}))
        self.assertEqual(self.voz("¡Gracias por ver!".encode()), (200, {"texto": ""}))
        self.assertEqual(self.voz("Subtítulos realizados por la comunidad de Amara.org".encode()), (200, {"texto": ""}))
        self.assertEqual(len(self.esperar()), 2)

    def test_es_pedido(self):
        self.assertTrue(api.es_pedido("pon música de Queen"))
        self.assertTrue(api.es_pedido("gracias, apaga la música"))
        self.assertFalse(api.es_pedido("Gracias."))
        self.assertFalse(api.es_pedido("..."))

    def test_spotify_prefiere_el_celular(self):
        real = api.cargar_modulo("spotify_real", api.RAIZ / "voz" / "spotify.py")
        web = {"id": "web", "type": "Computer", "is_active": True}
        cel = {"id": "cel", "type": "Smartphone", "is_active": False}
        real._api = lambda *a, **k: {"devices": [web, cel]}
        self.assertEqual(real._dispositivo("Smartphone")["id"], "cel")
        self.assertEqual(real._dispositivo()["id"], "web")      # la voz del PC sigue con el que suena
        real._api = lambda *a, **k: {"devices": [web]}
        self.assertEqual(real._dispositivo("Smartphone")["id"], "web")   # celular cerrado: el que haya

    def test_es_si(self):
        self.assertTrue(api.es_si("Sí, envíalo"))
        self.assertFalse(api.es_si("sí pero mejor mañana"))
        self.assertFalse(api.es_si("silencio"))


if __name__ == "__main__":
    unittest.main()
