"""Pruebas de la sala de Orión Equipo (sin Claude: un orion-equipo.sh falso).
python3 -m unittest equipo/test_servidor.py"""
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
import servidor  # noqa: E402

FALSO = """#!/usr/bin/env bash
echo "$*" >> "$REGISTRO"
echo "SESION=s1" >&2
echo "Hola, ${@: -1}"
"""
ANA, LUIS = "a" * 30, "b" * 30


class SalaWeb(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        guion = self.dir / "orion.sh"
        guion.write_text(FALSO)
        guion.chmod(0o755)
        os.environ["REGISTRO"] = str(self.dir / "registro")
        (self.dir / "personas").write_text(f"ana {ANA}\nluis {LUIS}\n# pepe {'c' * 30}\nmal corta\n")
        servidor.PERSONAS = self.dir / "personas"
        servidor.Manejador.sala = servidor.Sala(self.dir / "sala.json", guion=str(guion), limite_dia=3)
        servidor.Manejador.fallos = servidor.Fallos()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.http.server_address[1]}"

    def tearDown(self):
        self.http.shutdown()

    def pedir(self, ruta, clave=None, datos=None):
        r = urllib.request.Request(self.base + ruta, data=json.dumps(datos).encode() if datos is not None else None)
        if clave:
            r.add_header("Authorization", "Bearer " + clave)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def esperar(self, clave, cuantos):
        for _ in range(100):
            _, d = self.pedir("/api/sala?desde=0", ANA)
            if len(d["mensajes"]) >= cuantos and not d["ocupado"]:
                return d["mensajes"]
            time.sleep(0.05)
        self.fail("Orión no contestó")

    def test_clave_identifica_a_cada_persona(self):
        self.assertEqual(self.pedir("/api/yo", ANA), (200, {"nombre": "ana"}))
        self.assertEqual(self.pedir("/api/yo", LUIS)[1]["nombre"], "luis")
        self.assertEqual(self.pedir("/api/yo", "c" * 30)[0], 401)   # comentada: no entra
        self.assertEqual(self.pedir("/api/yo")[0], 401)

    def test_sala_compartida_con_nombre(self):
        self.assertEqual(self.pedir("/api/pedir", ANA, {"texto": "qué es HSTS"})[0], 202)
        mensajes = self.esperar(ANA, 2)
        self.assertEqual(mensajes[0]["de"], "ana")
        self.assertEqual(mensajes[1]["de"], "orion")
        self.assertIn("ana: qué es HSTS", mensajes[1]["texto"])
        # Luis ve lo mismo y su pedido sigue la misma conversación.
        self.pedir("/api/pedir", LUIS, {"texto": "y CSP?"})
        self.esperar(LUIS, 4)
        registro = (self.dir / "registro").read_text().splitlines()
        self.assertEqual(registro[1], "--reanudar s1 -- luis: y CSP?")

    def test_tope_diario_por_persona(self):
        for _ in range(3):
            self.assertEqual(self.pedir("/api/pedir", ANA, {"texto": "hola"})[0], 202)
        self.assertEqual(self.pedir("/api/pedir", ANA, {"texto": "hola"})[0], 429)
        self.assertEqual(self.pedir("/api/pedir", LUIS, {"texto": "hola"})[0], 202)

    def test_bloquea_tras_claves_malas(self):
        for _ in range(5):
            self.pedir("/api/yo", "x" * 30)
        self.assertEqual(self.pedir("/api/yo", ANA)[0], 429)

    def test_sin_rutas_del_orion_de_david(self):
        for ruta in ("/api/billetera/resumen", "/api/conversacion", "/app/", "/api/ia"):
            self.assertEqual(self.pedir(ruta, ANA)[0], 404)
        self.assertEqual(self.pedir("/api/sitios/publicar", ANA, {})[0], 404)


if __name__ == "__main__":
    unittest.main()
