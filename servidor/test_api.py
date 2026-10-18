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
        api.FALLOS = api.Fallos()
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
        api.Manejador.modulo_ia = api.ia_externa()
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

    def test_muchas_claves_malas_bloquean_la_ip(self):
        api.FALLOS = api.Fallos()
        codigos = []
        for _ in range(6):
            try:
                self.pedir("/api/conversacion", token="otro")
            except urllib.error.HTTPError as e:
                codigos.append(e.code)
        self.assertEqual(codigos, [401] * 5 + [429])
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.pedir("/api/conversacion")   # ni con la buena, hasta que pase el castigo
        self.assertEqual(e.exception.code, 429)
        api.FALLOS = api.Fallos()
        self.assertEqual(self.pedir("/api/conversacion")[0], 200)

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
        h.SALIDAS = self.dir
        h.PANELES = self.dir / "panel"
        carpeta = h.PANELES / "2026-10-04-landing"
        carpeta.mkdir(parents=True)
        (carpeta / "panel-marketing.json").write_text(json.dumps(
            {"rol": "marketing", "pregunta": "p", "respuestas": [{"modelo": "m", "texto": "```html\n<b>x</b>\n```"}]}))
        (h.PANELES / "2026-10-04-landing.md").write_text("# Conclusión")
        (self.dir / "seguridad").mkdir()
        (self.dir / "seguridad" / "2026-10-03-servidor.md").write_text("# Auditoría")
        _, d = self.pedir("/api/propuestas")
        panel = next(p for p in d["propuestas"] if p["tipo"] == "panel")
        self.assertEqual(panel["roles"], ["marketing"])
        self.assertTrue(panel["conclusion"])
        # Las auditorías y demás informes también salen; la conclusión del panel no se repite como informe.
        self.assertEqual([p["id"] for p in d["propuestas"] if p["tipo"] != "panel"],
                         ["informe/seguridad/2026-10-03-servidor.md"])
        _, d = self.pedir("/api/propuestas/informe%2Fseguridad%2F2026-10-03-servidor.md")
        self.assertEqual(d["informe"]["texto"], "# Auditoría")
        _, d = self.pedir("/api/propuestas/2026-10-04-landing")
        self.assertEqual(d["conclusion"], "# Conclusión")
        self.assertEqual(d["paneles"][0]["respuestas"][0]["modelo"], "m")
        for ruta in ("/api/propuestas/..", "/api/propuestas/..%2F..%2Fservidor", "/api/propuestas/nada",
                     "/api/propuestas/informe%2F..%2Fconversacion.json", "/api/propuestas/informe%2F..%2F..%2Fx.md"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.pedir(ruta)
            self.assertEqual(e.exception.code, 404)
        # Eliminar: va a la papelera de la bóveda, con su ruta, y no sale de outputs/.
        h.PAPELERA = self.dir / ".papelera"
        fuera = self.dir.parent / (self.dir.name + "-fuera.md")
        fuera.write_text("no es de outputs")
        self.addCleanup(fuera.unlink, missing_ok=True)
        (self.dir / "nota.txt").write_text("no es un informe")
        _, d = self.pedir("/api/propuestas/borrar", {"ids": [
            "2026-10-04-landing", "informe/seguridad/2026-10-03-servidor.md",
            f"informe/../{fuera.name}", "informe/nota.txt", "../x"]})
        self.assertEqual(d["borradas"], 2)
        self.assertFalse(carpeta.exists())
        dia = next(h.PAPELERA.iterdir())
        self.assertTrue((dia / "panel" / "2026-10-04-landing" / "panel-marketing.json").exists())
        self.assertTrue((dia / "panel" / "2026-10-04-landing.md").exists())
        self.assertTrue((dia / "seguridad" / "2026-10-03-servidor.md").exists())
        self.assertTrue(fuera.exists() and (self.dir / "nota.txt").exists())
        self.assertEqual(self.pedir("/api/propuestas")[1]["propuestas"], [])
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

    def test_el_pc_usa_las_ias_del_servidor(self):
        """El PC no tiene claves: ia_externa.py pasa por /api/ia y el servidor llama con las suyas."""
        import types
        llamadas = []
        falso = types.SimpleNamespace(
            PROVEEDORES={"gemini": {"clave": "CLAVE_SRV_PRUEBA"}, "openrouter": {"clave": "OTRA_SRV_PRUEBA"}},
            cargar_env=lambda: None)

        def llamar(proveedor, ruta, cuerpo=None):
            llamadas.append((proveedor, ruta))
            if ruta == "/models":
                return {"data": [{"id": "models/gemini-9-flash"}]}
            return {"model": "gemini-9-flash", "choices": [{"message": {"content": "hola desde el servidor"}}]}
        falso.llamar = llamar
        api.Manejador.modulo_ia = falso
        os.environ["CLAVE_SRV_PRUEBA"] = "x"
        self.addCleanup(os.environ.pop, "CLAVE_SRV_PRUEBA", None)
        # Lo que no es /models ni /chat/completions no pasa.
        req = urllib.request.Request(self.base + "/api/ia", data=json.dumps(
            {"proveedor": "gemini", "ruta": "/files", "cuerpo": None}).encode(),
            headers={"Authorization": "Bearer " + "t" * 30})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 400)

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import ia_externa
        antes = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_MODELO")}
        os.environ.update(JARVIS_SERVIDOR=self.base + "/app/", JARVIS_API_TOKEN="t" * 30)

        def restaurar():
            for k in ("JARVIS_SERVIDOR", "JARVIS_API_TOKEN"):
                os.environ.pop(k, None)
            os.environ.update({k: v for k, v in antes.items() if v is not None})
        self.addCleanup(restaurar)
        ia_externa._remotas = None
        self.assertEqual(ia_externa.configuradas(), ["gemini"])
        usado, texto = ia_externa.preguntar("gemini", "hola")
        self.assertEqual(texto, "hola desde el servidor")
        self.assertEqual(llamadas, [("gemini", "/models"), ("gemini", "/chat/completions")])
        with self.assertRaises(RuntimeError):   # el servidor no tiene clave de OpenRouter
            ia_externa.llamar("openrouter", "/models")

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
