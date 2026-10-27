"""Pruebas de la sala y el panel de Orión Equipo (sin Claude: un orion-equipo.sh falso).
python3 -m unittest equipo/test_servidor.py"""
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

os.environ["ORION_EQUIPO_INSEGURO"] = "1"   # pruebas por HTTP: cookies sin Secure
os.environ["ORION_EQUIPO_SECRETO"] = "prueba"
import servidor  # noqa: E402
import seguridad  # noqa: E402

FALSO = """#!/usr/bin/env bash
echo "SESION=s1" >&2
echo "Hola ${ORION_EQUIPO_PERSONA:-nadie}, ${@: -1}"
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        guion = self.dir / "orion.sh"
        guion.write_text(FALSO)
        guion.chmod(0o755)
        for attr, val in (("PERSONAS", self.dir / "personas"), ("ADMIN", self.dir / "admin.json"),
                          ("SESIONES", self.dir / "sesiones.json"), ("AUTOR", self.dir / "autorizaciones"),
                          ("ALERTAS", self.dir / "alertas.jsonl"), ("INFORMES", self.dir / "informes"),
                          ("PAUSA", self.dir / "PAUSA")):
            setattr(servidor, attr, val)
        servidor.PERSONAS.write_text("ana\t" + seguridad.cifrar_clave("clave-de-ana") + "\n"
                                     "luis\t" + seguridad.cifrar_clave("clave-de-luis") + "\n")
        servidor.ADMIN.write_text(json.dumps({"clave": seguridad.cifrar_clave("clave-del-panel"), "totp": ""}))
        servidor.Manejador.sala = servidor.Sala(self.dir / "sala.json", guion=str(guion), limite_dia=3)
        servidor.Manejador.sesiones = servidor.Sesiones(self.dir / "sesiones.json")
        servidor.Manejador.fallos = servidor.Fallos()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.puerto = self.http.server_address[1]

    def tearDown(self):
        self.http.shutdown()

    def pedir(self, metodo, ruta, datos=None, cookie=None, csrf=True):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        cab = {"Content-Type": "application/json"}
        if cookie:
            cab["Cookie"] = cookie
        if csrf:
            cab["X-OE"] = "1"
        c.request(metodo, ruta, json.dumps(datos) if datos is not None else None, cab)
        r = c.getresponse()
        galleta = r.getheader("Set-Cookie")
        cuerpo = r.read()
        c.close()
        return r.status, json.loads(cuerpo or b"{}"), galleta

    def entrar_persona(self, usuario, clave):
        _, _, galleta = self.pedir("POST", "/api/entrar", {"usuario": usuario, "clave": clave})
        return galleta.split(";")[0] if galleta else None

    def entrar_panel(self, clave="clave-del-panel"):
        _, _, galleta = self.pedir("POST", "/panel/api/entrar", {"clave": clave})
        return galleta.split(";")[0] if galleta else None


class Sala(Base):
    def test_login_usuario_contrasena(self):
        self.assertEqual(self.pedir("GET", "/api/yo")[0], 401)
        st, _, g = self.pedir("POST", "/api/entrar", {"usuario": "ana", "clave": "mala"})
        self.assertEqual(st, 401)
        self.assertIsNone(g)
        ck = self.entrar_persona("ana", "clave-de-ana")
        self.assertIsNotNone(ck)
        self.assertEqual(self.pedir("GET", "/api/yo", cookie=ck)[1]["nombre"], "ana")

    def test_pedir_pasa_el_nombre_a_orion(self):
        ck = self.entrar_persona("ana", "clave-de-ana")
        st, d, _ = self.pedir("POST", "/api/pedir", {"texto": "qué es XSS"}, cookie=ck)
        self.assertEqual(st, 202)
        import time
        for _ in range(100):
            _, sala, _ = self.pedir("GET", "/api/sala?desde=0", cookie=ck)
            if len(sala["mensajes"]) >= 2 and not sala["ocupado"]:
                break
            time.sleep(0.05)
        self.assertEqual(sala["mensajes"][1]["de"], "orion")
        self.assertIn("Hola ana", sala["mensajes"][1]["texto"])

    def test_csrf_y_tope(self):
        ck = self.entrar_persona("ana", "clave-de-ana")
        self.assertEqual(self.pedir("POST", "/api/pedir", {"texto": "x"}, cookie=ck, csrf=False)[0], 403)
        for _ in range(3):
            self.assertEqual(self.pedir("POST", "/api/pedir", {"texto": "x"}, cookie=ck)[0], 202)
        self.assertEqual(self.pedir("POST", "/api/pedir", {"texto": "x"}, cookie=ck)[0], 429)

    def test_informe(self):
        ck = self.entrar_persona("ana", "clave-de-ana")
        self.assertEqual(self.pedir("POST", "/api/informe", {"texto": "Encontré que falta HSTS en el login."}, cookie=ck)[0], 200)
        self.assertTrue(any(f.name.endswith("-ana.md") for f in servidor.INFORMES.glob("*.md")))


class Panel(Base):
    def test_panel_pide_clave(self):
        self.assertEqual(self.pedir("GET", "/panel/api/estado")[0], 401)
        self.assertEqual(self.pedir("POST", "/panel/api/entrar", {"clave": "mala"})[0], 401)
        ck = self.entrar_panel()
        self.assertIsNotNone(ck)
        self.assertEqual(self.pedir("GET", "/panel/api/estado", cookie=ck)[0], 200)

    def test_persona_no_entra_al_panel(self):
        ck = self.entrar_persona("ana", "clave-de-ana")
        self.assertEqual(self.pedir("GET", "/panel/api/estado", cookie=ck)[0], 401)

    def test_aprobar_autorizacion(self):
        # simula lo que deja pentest.sh
        pend = servidor.AUTOR / "pendientes"
        pend.mkdir(parents=True)
        (pend / "abc.json").write_text(json.dumps({"id": "abc", "persona": "ana", "herramienta": "nikto",
                                                    "objetivo": "https://api.ubuntulabs.co", "tipo": "activa",
                                                    "clave": "https___api.ubuntulabs.co__nikto", "args": ""}))
        ck = self.entrar_panel()
        self.assertEqual(self.pedir("GET", "/panel/api/autorizaciones", cookie=ck)[1]["pendientes"][0]["herramienta"], "nikto")
        self.assertTrue(self.pedir("POST", "/panel/api/autorizar", {"id": "abc", "horas": 2}, cookie=ck)[1]["ok"])
        self.assertTrue((servidor.AUTOR / "aprobadas" / "https___api.ubuntulabs.co__nikto.json").exists())
        self.assertFalse((pend / "abc.json").exists())

    def test_pausa_y_quitar(self):
        ck = self.entrar_panel()
        self.assertTrue(self.pedir("POST", "/panel/api/pausa", {"activar": True}, cookie=ck)[1]["pausa"])
        self.assertTrue(servidor.PAUSA.exists())
        ap = self.entrar_persona("ana", "clave-de-ana")
        self.assertEqual(self.pedir("POST", "/api/pedir", {"texto": "x"}, cookie=ap)[0], 409)
        self.assertTrue(self.pedir("POST", "/panel/api/quitar", {"nombre": "luis"}, cookie=ck)[1]["ok"])
        self.assertNotIn("luis", servidor.leer_personas())


if __name__ == "__main__":
    unittest.main()
