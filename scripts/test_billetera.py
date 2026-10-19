"""Pruebas de la billetera simulada (sin internet: precios e IAs falsos). python3 -m unittest scripts/test_billetera.py"""
import json
import os
import sys
import tempfile
import time
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
        billetera.precios = lambda activos: PRECIOS
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

    def test_modo_real_no_existe(self):
        billetera.terminar(None)
        self.assertEqual(billetera.iniciar(type("A", (), {"saldo": 10.0, "dias": 14, "modo": "real"})), 2)


if __name__ == "__main__":
    unittest.main()
