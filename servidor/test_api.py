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
  *) echo "Hecho: $pedido" ;;
esac
"""


class PruebaApi(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        guion = self.dir / "jarvis.sh"
        guion.write_text(FALSO)
        guion.chmod(0o755)
        self.registro = self.dir / "registro.txt"
        os.environ.update(JARVIS_SCRIPT=str(guion), REGISTRO=str(self.registro))
        api.Manejador.token = "t" * 30
        api.Manejador.conversacion = api.Conversacion(self.dir / "conversacion.json")
        api.Manejador.modulo_hud = api.hud()
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

    def test_es_si(self):
        self.assertTrue(api.es_si("Sí, envíalo"))
        self.assertFalse(api.es_si("sí pero mejor mañana"))
        self.assertFalse(api.es_si("silencio"))


if __name__ == "__main__":
    unittest.main()
