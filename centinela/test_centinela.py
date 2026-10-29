"""Pruebas del centinela:  python3 -m unittest centinela/test_centinela.py
Las de nftables solo corren como root con nft instalado (en un contenedor o una máquina de pruebas)."""
import importlib.util
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

DIR = tempfile.mkdtemp()
os.environ.update(CENTINELA_DATOS=DIR, CENTINELA_REGISTRO=f"{DIR}/registro.jsonl", CENTINELA_CONF=f"{DIR}/conf")
# Se carga por ruta: desde la raíz del repo, "import centinela" encontraría la carpeta, no el script.
_spec = importlib.util.spec_from_file_location("centinela_script", Path(__file__).with_name("centinela.py"))
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

SSHD = """\
Failed password for invalid user admin from 45.10.20.30 port 51234 ssh2
Failed password for root from 45.10.20.30 port 51235 ssh2
Invalid user oracle from 2001:db8::7 port 4040
Connection closed by authenticating user root 45.10.20.31 port 22 [preauth]
pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=45.10.20.32  user=root
Did not receive identification string from 45.10.20.33 port 5000
Accepted publickey for david from 181.50.1.2 port 60000 ssh2: ED25519 SHA256:abc
Server listening on 0.0.0.0 port 22.
"""

SS = """\
ESTAB 0 0 10.0.0.5:22 181.50.1.2:60000 users:(("sshd",pid=10,fd=4))
\t cubic wscale:7,7 rto:204 bytes_sent:5000 bytes_acked:4800 bytes_received:900 segs_out:20
SYN-RECV 0 0 [::ffff:10.0.0.5]:443 [::ffff:45.1.1.1]:3333
ESTAB 0 0 10.0.0.5:44000 45.77.8.9:443 users:(("python3",pid=99,fd=7))
\t cubic bytes_acked:350000000 bytes_received:10
LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1,fd=3))
"""

SS_L = """\
tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1,fd=3))
tcp LISTEN 0 128 127.0.0.1:7788 0.0.0.0:* users:(("python3",pid=2,fd=3))
tcp LISTEN 0 128 [::]:443 [::]:* users:(("caddy",pid=3,fd=3))
udp UNCONN 0 0 *:22000 *:* users:(("syncthing",pid=4,fd=3))
"""


class Lectura(unittest.TestCase):
    def test_ssh(self):
        ev = c.eventos_ssh(SSHD.splitlines())
        fallos = [e for e in ev if e[0] == "fallo"]
        self.assertEqual(len(fallos), 6)
        self.assertIn(("fallo", "45.10.20.30", "admin"), fallos)
        self.assertIn(("fallo", "2001:db8::7", "oracle"), fallos)
        self.assertIn(("fallo", "45.10.20.32", ""), fallos)
        self.assertIn(("entrada", "181.50.1.2", "david", "publickey"), ev)

    def test_conexiones(self):
        cs = c.conexiones(SS)
        self.assertEqual(len(cs), 4)
        self.assertEqual(cs[0]["bytes_acked"], 4800)
        self.assertEqual(cs[0]["proc"], "sshd")
        self.assertEqual(str(cs[1]["remoto"]), "45.1.1.1")   # ::ffff: se lee como IPv4
        self.assertEqual(cs[1]["lport"], 443)
        self.assertEqual(cs[2]["bytes_acked"], 350000000)
        self.assertIsNone(cs[3]["remoto"])

    def test_escuchando_sin_loopback(self):
        self.assertEqual(c.escuchando(SS_L), {"tcp:22": "sshd", "tcp:443": "caddy", "udp:22000": "syncthing"})

    def test_contadores(self):
        dev = ("Inter-|   Receive |  Transmit\n face |bytes packets errs drop fifo frame compressed multicast|bytes\n"
               "    lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0\n"
               "  eth0: 1000 10 0 0 0 0 0 0 5000 20 0 0 0 0 0 0\n")
        self.assertEqual(c.contadores_red(dev), (1000, 10, 5000))

    def test_normal(self):
        n = c.Normal()
        for _ in range(2000):
            n.sumar(1e5)
        self.assertFalse(n.raro(2e5, 8e6))          # bajo el piso: nunca raro
        self.assertTrue(n.raro(9e6, 8e6))
        nuevo = c.Normal()
        self.assertFalse(nuevo.raro(9e6, 8e6))      # aprendiendo: solo 3 veces el piso
        self.assertTrue(nuevo.raro(3e7, 8e6))

    def test_diferencias(self):
        d = c.diferencias("a\nb\n", "a\nb\nssh-ed25519 AAAA intruso\n")
        self.assertEqual(d, ["+ssh-ed25519 AAAA intruso"])

    def test_ip_valida(self):
        self.assertEqual(str(c.ip_valida("[::ffff:1.2.3.4]")), "1.2.3.4")
        self.assertIsNone(c.ip_valida("1.2.3.4; rm -rf /"))


class Decisiones(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.correr_real = c.correr
        c.BASE, c.AVISOS = self.dir, self.dir / "avisos"
        c.REGISTRO = self.dir / "registro.jsonl"
        conf = dict(c.AJUSTES, PERMITIDOS="190.1.2.0/24", MODO="actuar")
        self.cen = c.Centinela(conf, self.dir / "estado.json")
        self.cen.primera_vez = False
        self.cen.e["inicio"] = time.time()
        self.bloqueadas = []
        self.cen.tabla_viva = lambda: True
        self.cen._elemento = lambda accion, conjunto, ip, s=None: (self.bloqueadas.append((accion, conjunto, str(ip))), (0, "", ""))[1]

    def tearDown(self):
        c.correr = self.correr_real
        shutil.rmtree(self.dir, ignore_errors=True)

    def avisos(self):
        return [p.read_text() for p in sorted(c.AVISOS.glob("*.txt"))]

    def test_nunca_bloquea_a_david_ni_cloudflare(self):
        for ip in ("190.1.2.50", "104.16.1.1", "10.0.0.8", "127.0.0.1", "100.100.1.1", "2606:4700::1"):
            self.assertIn("No la bloqueé", self.cen.bloquear(ip, 60, "prueba"))
        self.cen.confiar("181.50.1.2", 3)
        self.assertIn("No la bloqueé", self.cen.bloquear("181.50.1.2", 60, "prueba"))
        self.assertFalse([b for b in self.bloqueadas if b[1] == "bloqueados" and b[0] == "add"])

    def test_bloqueo_y_reincidente(self):
        self.assertIn("1 h", self.cen.bloquear("45.10.20.30", 60, "prueba"))
        self.cen.desbloquear("45.10.20.30")
        self.assertIn("24 h", self.cen.bloquear("45.10.20.30", 60, "otra vez"))

    def test_modo_avisar_no_bloquea(self):
        self.cen.c["MODO"] = "avisar"
        self.assertIn("solo avisar", self.cen.bloquear("45.10.20.30", 60, "prueba"))
        self.assertIn("Bloqueé", self.cen.bloquear("45.10.20.30", 60, "a mano", a_mano=True))

    def test_fuerza_bruta_ssh(self):
        lineas = [f"Failed password for root from 45.10.20.40 port {i} ssh2" for i in range(9)]
        c.correr = lambda *a, **k: (0, "\n".join(lineas), "")
        self.cen.revisar_ssh()
        self.assertIn("45.10.20.40", self.cen.e["bloqueos"])
        self.assertTrue(any("intentos de entrar por SSH" in a for a in self.avisos()))

    def test_entrada_ssh_nueva_avisa_y_confia(self):
        c.correr = lambda *a, **k: (0, "Accepted publickey for david from 181.60.7.8 port 1 ssh2", "")
        self.cen.revisar_ssh()
        self.assertTrue(self.cen.protegida("181.60.7.8"))
        self.assertTrue(any("IP nueva" in a for a in self.avisos()))

    def test_dos_por_conexiones(self):
        conns = [{"estado": "ESTAB", "remoto": c.ip_valida("45.9.9.9"), "lport": 443, "local": None, "rport": i,
                  "proc": "caddy", "bytes_acked": 0, "bytes_received": 0} for i in range(200)]
        self.cen.revisar_conexiones(conns, {"tcp:443": "caddy"})
        self.assertIn("45.9.9.9", self.cen.e["bloqueos"])

    def test_fuga_desconocida_bloquea_conocida_solo_avisa(self):
        def con(ip, proc, b):
            return {"estado": "ESTAB", "remoto": c.ip_valida(ip), "lport": 44000, "local": c.ip_valida("10.0.0.5"),
                    "rport": 443, "proc": proc, "bytes_acked": b, "bytes_received": 0}
        self.cen.revisar_salida([con("45.77.8.9", "python3", 0), con("34.120.5.6", "syncthing", 0)], {}, 60)
        self.cen.revisar_salida([con("45.77.8.9", "python3", 400e6), con("34.120.5.6", "syncthing", 400e6)], {}, 60)
        self.assertIn("45.77.8.9", self.cen.e["bloqueos"])
        self.assertNotIn("34.120.5.6", self.cen.e["bloqueos"])
        self.assertTrue(any("fuga de datos" in a for a in self.avisos()))

    def test_exceso_de_nftables_se_bloquea(self):
        js = json.dumps({"nftables": [{"metainfo": {}}, {"set": {"name": "exceso_web4", "elem": [
            {"elem": {"val": "45.10.0.2", "expires": 299}}, {"elem": {"val": "104.16.1.1", "expires": 100}}]}}]})
        self.cen._nft = lambda *a, **k: (0, js if a[-1] == "exceso_web4" else "", "")
        self.cen.revisar_excesos()
        self.assertIn("45.10.0.2", self.cen.e["bloqueos"])
        self.assertNotIn("104.16.1.1", self.cen.e["bloqueos"])       # Cloudflare: nunca
        self.assertTrue(any("50 conexiones nuevas por segundo" in a for a in self.avisos()))

    def test_aviso_no_se_repite(self):
        self.cen.avisar("x", "media", "hola")
        self.cen.avisar("x", "media", "hola")
        self.assertEqual(len(self.avisos()), 1)

    def test_puerto_nuevo(self):
        self.cen.revisar_puertos({"tcp:22": "sshd"})
        self.cen.revisar_puertos({"tcp:22": "sshd", "tcp:4444": "nc"})
        self.assertTrue(any("4444" in a for a in self.avisos()))


@unittest.skipUnless(os.geteuid() == 0 and shutil.which("nft") and os.environ.get("CENTINELA_PROBAR_NFT"),
                     "CENTINELA_PROBAR_NFT=1 y root para probar nftables de verdad")
class Nftables(unittest.TestCase):
    def test_reglas_reales(self):
        d = Path(tempfile.mkdtemp())
        c.BASE, c.AVISOS, c.REGISTRO = d, d / "avisos", d / "r.jsonl"
        cen = c.Centinela(dict(c.AJUSTES, PERMITIDOS="190.1.2.0/24"), d / "e.json")
        try:
            cen.encender()
            self.assertTrue(cen.tabla_viva())
            self.assertIn("Bloqueé", cen.bloquear("45.10.20.30", 5, "prueba"))
            _, out, _ = c.correr("nft", "-j", "list", "set", "inet", "orion_centinela", "bloqueados4")
            self.assertIn("45.10.20.30", out)
            _, out, _ = c.correr("nft", "list", "set", "inet", "orion_centinela", "permitidos4")
            self.assertIn("190.1.2.0/24", out)
            cen.desbloquear("45.10.20.30")
            _, out, _ = c.correr("nft", "-j", "list", "set", "inet", "orion_centinela", "bloqueados4")
            self.assertNotIn("45.10.20.30", json.dumps(json.loads(out)))
            cen.apagar()
            self.assertFalse(cen.tabla_viva())
        finally:
            c.correr("nft", "delete", "table", "inet", "orion_centinela")


if __name__ == "__main__":
    unittest.main()
