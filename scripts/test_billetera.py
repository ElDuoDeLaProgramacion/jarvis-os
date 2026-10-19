"""Pruebas de la billetera, simulada y real (sin internet: precios, IAs y Bitso falsos). python3 -m unittest scripts/test_billetera.py"""
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import billetera  # noqa: E402

PRECIOS = {"BTC": {"precio": 100000.0, "cambio_24h": 1.0, "cambio_7d": 3.0},
           "ETH": {"precio": 4000.0, "cambio_24h": -2.0, "cambio_7d": 1.0},
           "SOL": {"precio": 200.0, "cambio_24h": 0.5, "cambio_7d": -4.0}}


class Billetera(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        billetera.CARPETA = Path(self.tmp.name) / "billetera"
        billetera.precios = lambda activos, moneda="USD": PRECIOS
        self.votos = []
        billetera.votar = lambda estado, p, aj: [(f"ia-{i}", billetera.leer_voto(t, aj["activos"], aj["tope"]), t)
                                                 for i, t in enumerate(self.votos)]
        billetera.iniciar(type("A", (), {"saldo": 1000.0, "dias": 14, "modo": "simulado"}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_leer_voto(self):
        v = billetera.leer_voto('Claro: {"accion":"comprar","activo":"btc","porcentaje":80,"razon":"sube"}',
                                {"BTC": "bitcoin"}, 25)
        self.assertEqual((v["accion"], v["activo"], v["porcentaje"]), ("comprar", "BTC", 25))
        self.assertEqual(billetera.leer_voto("no sé", {"BTC": "bitcoin"}, 25)["accion"], "mantener")
        self.assertEqual(billetera.leer_voto('{"accion":"comprar","activo":"DOGE","porcentaje":5}',
                                             {"BTC": "bitcoin"}, 25)["accion"], "mantener")

    def test_mayoria_compra_con_tope_y_comision(self):
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":10,"razon":"a"}',
                      '{"accion":"comprar","activo":"BTC","porcentaje":20,"razon":"b"}',
                      '{"accion":"mantener","activo":null,"porcentaje":0,"razon":"c"}']
        self.assertEqual(billetera.ronda(None), 0)
        e = billetera.leer_estado()
        self.assertAlmostEqual(e["efectivo"], 850.0)                       # mediana 15 % de 1000
        self.assertAlmostEqual(e["posiciones"]["BTC"], 150 * 0.995 / 100000)
        self.assertEqual(len((billetera.CARPETA / "decisiones.jsonl").read_text().splitlines()), 1)
        self.assertIn("ia-1", next((billetera.CARPETA / "diario").glob("*.md")).read_text())

    def test_empate_mantiene(self):
        self.votos = ['{"accion":"comprar","activo":"ETH","porcentaje":10}', '{"accion":"mantener"}']
        billetera.ronda(None)
        self.assertEqual(billetera.leer_estado()["efectivo"], 1000.0)

    def test_maximo_de_operaciones_al_dia(self):
        self.votos = ['{"accion":"comprar","activo":"SOL","porcentaje":5}']
        for _ in range(5):
            billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertEqual(sum(1 for h in e["historial"] if h["operacion"]), 3)
        self.assertIn("operaciones hoy", e["historial"][-1]["resumen"])

    def test_vender_sin_tener(self):
        self.votos = ['{"accion":"vender","activo":"BTC","porcentaje":10}']
        billetera.ronda(None)
        self.assertEqual(billetera.leer_estado()["efectivo"], 1000.0)

    def test_pausa(self):
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":10}']
        billetera.pausar(None)
        billetera.ronda(None)
        self.assertEqual(billetera.leer_estado()["historial"], [])
        billetera.reanudar(None)
        billetera.ronda(None)
        self.assertEqual(len(billetera.leer_estado()["historial"]), 1)

    def test_termina_solo_y_deja_informe(self):
        e = billetera.leer_estado()
        e["fin"] = time.time() - 1
        billetera.guardar_estado(e)
        billetera.ronda(None)
        self.assertTrue(billetera.leer_estado()["terminado"])
        self.assertTrue((billetera.CARPETA / "informe-final.md").exists())
        self.assertEqual(billetera.ronda(None), 0)                          # después ya no hace nada



class BitsoFalso:
    """Una cuenta de Bitso en memoria: compra y vende al precio de PRECIOS con 0,5 % de comisión."""
    def __init__(self, mxn):
        self.saldo = {"mxn": mxn, "btc": 0.0, "eth": 0.0, "sol": 0.0}
        self.ordenes = []

    def modulo(self):
        m = types.ModuleType("bitso")
        m.configurado = lambda: True
        m.saldos = lambda: dict(self.saldo)
        m.comprar = self.comprar
        m.vender = self.vender
        return m

    def comprar(self, libro, gastar):
        s = libro.split("_")[0]
        cantidad = gastar / PRECIOS[s.upper()]["precio"]
        self.saldo["mxn"] -= gastar
        self.saldo[s] += cantidad * 0.995
        self.ordenes.append(("buy", libro, gastar))
        return {"oid": "1", "mayor": cantidad, "menor": gastar, "comision": cantidad * 0.005, "moneda_comision": s}

    def vender(self, libro, cantidad):
        s = libro.split("_")[0]
        cobro = cantidad * PRECIOS[s.upper()]["precio"]
        self.saldo[s] -= cantidad
        self.saldo["mxn"] += cobro * 0.995
        self.ordenes.append(("sell", libro, cantidad))
        return {"oid": "2", "mayor": cantidad, "menor": cobro, "comision": cobro * 0.005, "moneda_comision": "mxn"}


class Real(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        billetera.CARPETA = Path(self.tmp.name) / "billetera"
        billetera.precios = lambda activos, moneda="USD": PRECIOS
        self.bitso = BitsoFalso(2000.0)
        sys.modules["bitso"] = self.bitso.modulo()
        os.environ["BILLETERA_PORCENTAJE_REAL"] = "100"
        self.votos = []
        billetera.votar = lambda estado, p, aj: [(f"ia-{i}", billetera.leer_voto(t, aj["activos"], aj["tope"]), t)
                                                 for i, t in enumerate(self.votos)]

    def tearDown(self):
        os.environ.pop("BILLETERA_PORCENTAJE_REAL", None)
        sys.modules.pop("bitso", None)
        self.tmp.cleanup()

    def iniciar(self, confirmo=None):
        return billetera.iniciar(type("A", (), {"saldo": 0, "dias": 14, "modo": "real", "moneda": "MXN",
                                                "confirmo": confirmo}))

    def test_sin_confirmar_el_monto_no_arranca(self):
        self.assertEqual(self.iniciar(), 2)
        self.assertEqual(self.iniciar("1999 MXN"), 2)
        self.assertIsNone(billetera.leer_estado())

    def test_sin_porcentaje_en_env_no_arranca(self):
        os.environ.pop("BILLETERA_PORCENTAJE_REAL")
        self.assertEqual(self.iniciar("2000.00 MXN"), 2)

    def test_compra_y_vende_en_bitso(self):
        self.assertEqual(self.iniciar("2000.00 MXN"), 0)
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":20}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertEqual(self.bitso.ordenes, [("buy", "btc_mxn", 400.0)])
        self.assertAlmostEqual(e["efectivo"], 1600.0)
        self.assertAlmostEqual(e["posiciones"]["BTC"], self.bitso.saldo["btc"])
        self.votos = ['{"accion":"vender","activo":"BTC","porcentaje":25}']
        billetera.ronda(None)
        self.assertEqual(self.bitso.ordenes[-1][0], "sell")
        self.assertAlmostEqual(billetera.leer_estado()["posiciones"]["BTC"], self.bitso.saldo["btc"])

    def test_deposito_de_david_se_suma(self):
        self.iniciar("2000.00 MXN")
        self.bitso.saldo["mxn"] += 500
        self.votos = ['{"accion":"mantener"}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertAlmostEqual(e["efectivo"], 2500.0)
        self.assertAlmostEqual(e["saldo_inicial"], 2500.0)

    def test_freno_por_perdida(self):
        self.iniciar("2000.00 MXN")
        self.bitso.saldo["mxn"] = 1000.0               # la cuenta perdió la mitad
        self.votos = ['{"accion":"mantener"}']
        billetera.ronda(None)
        self.assertTrue(billetera.pausada())

    def test_bitso_falla_y_no_toca_la_cartera(self):
        self.iniciar("2000.00 MXN")
        def falla(*a):
            raise RuntimeError("caído")
        sys.modules["bitso"].comprar = falla
        self.votos = ['{"accion":"comprar","activo":"ETH","porcentaje":10}']
        self.assertEqual(billetera.ronda(None), 0)
        e = billetera.leer_estado()
        self.assertEqual(e["efectivo"], 2000.0)
        self.assertIn("Bitso falló", e["historial"][-1]["resumen"])


if __name__ == "__main__":
    unittest.main()
