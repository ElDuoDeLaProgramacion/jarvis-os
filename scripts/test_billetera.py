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
        os.environ["BILLETERA_QUORUM"] = "1"
        self.votos = []
        billetera.votar = lambda estado, p, aj: [(f"ia-{i}", billetera.leer_voto(t, aj["activos"], aj["tope"]), t)
                                                 for i, t in enumerate(self.votos)]
        billetera.iniciar(type("A", (), {"saldo": 1000.0, "dias": 14, "modo": "simulado"}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_una_sola_ia_no_decide(self):
        os.environ["BILLETERA_QUORUM"] = "2"
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":10}']   # las demás no respondieron
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertEqual(e["efectivo"], 1000.0)
        self.assertIn("solo votaron 1 IAs", e["historial"][-1]["resumen"])
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":10}'] * 2
        billetera.ronda(None)
        self.assertLess(billetera.leer_estado()["efectivo"], 1000.0)

    def test_vigilante_convoca_ronda_de_emergencia(self):
        self.votos = ['{"accion":"mantener"}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        e["ultima_ronda"]["hora"] -= 3600
        billetera.guardar_estado(e)
        self.assertEqual(billetera.vigilar(None), 0)               # nada se movió: no hay ronda
        self.assertEqual(len(billetera.leer_estado()["historial"]), 1)
        movido = dict(PRECIOS, SOL=dict(PRECIOS["SOL"], precio=180.0))   # SOL bajó 10 %
        billetera.precios = lambda activos, moneda="USD": movido
        preguntas = []
        billetera.votar = lambda estado, p, aj: preguntas.append(billetera.pregunta_de(estado, p, aj)) or [
            ("ia-0", billetera.leer_voto('{"accion":"mantener"}', aj["activos"], aj["tope"]), "")]
        billetera.vigilar(None)
        h = billetera.leer_estado()["historial"]
        self.assertEqual(len(h), 2)
        self.assertIn("SOL bajó 10.0 %", h[-1]["emergencia"])
        self.assertIn("RONDA DE EMERGENCIA", preguntas[0])
        billetera.vigilar(None)                                    # recién votaron: no repite
        self.assertEqual(len(billetera.leer_estado()["historial"]), 2)

    def test_voto_por_moneda_sin_precio_no_opera(self):
        self.votos = ['{"accion":"comprar","activo":"XRP","porcentaje":10}']   # CoinGecko no dio XRP
        billetera.ronda(None)
        self.assertEqual(billetera.leer_estado()["efectivo"], 1000.0)

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
        lineas = [json.loads(x) for x in (billetera.CARPETA / "decisiones.jsonl").read_text().splitlines()]
        self.assertEqual([x["tipo"] for x in lineas], ["inicio", "ronda"])
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

    def test_pausa_durante_la_votacion_frena_la_orden(self):
        def votar(estado, p, aj):
            billetera.pausar(None)                     # David pausa mientras las IAs piensan
            return [("ia-0", billetera.leer_voto('{"accion":"comprar","activo":"BTC","porcentaje":10}',
                                                 aj["activos"], aj["tope"]), "")]
        billetera.votar = votar
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertEqual(e["efectivo"], 1000.0)
        self.assertIn("pausó durante la ronda", e["historial"][-1]["resumen"])

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
    DOLAR = 4000.0                                     # un dólar en pesos, para el libro usd_cop

    def __init__(self, cop, libros=("btc_cop", "eth_cop", "usd_cop")):   # SOL no tiene libro en COP
        self.saldo = {"cop": cop, "usd": 0.0, "btc": 0.0, "eth": 0.0, "sol": 0.0}
        self.libros = set(libros)
        self.ordenes = []

    def modulo(self):
        m = types.ModuleType("bitso")
        m.configurado = lambda: True
        m.libros = lambda: set(self.libros)
        m.ultimo = lambda libro: self.precio(libro.split("_")[0])
        m.Rechazo = type("Rechazo", (RuntimeError,), {})
        m.saldos = lambda: dict(self.saldo)
        m.comprar = self.comprar
        m.vender = self.vender
        return m

    def precio(self, s):
        return self.DOLAR if s == "usd" else PRECIOS[s.upper()]["precio"]

    def comprar(self, libro, gastar):
        s, m = libro.split("_")
        cantidad = gastar / self.precio(s)
        self.saldo[m] -= gastar
        self.saldo[s] = self.saldo.get(s, 0) + cantidad * 0.995
        self.ordenes.append(("buy", libro, gastar))
        return {"oid": "1", "mayor": cantidad, "menor": gastar, "comision": cantidad * 0.005, "moneda_comision": s}

    def vender(self, libro, cantidad):
        s, m = libro.split("_")
        cobro = cantidad * self.precio(s)
        self.saldo[s] -= cantidad
        self.saldo[m] += cobro * 0.995
        self.ordenes.append(("sell", libro, cantidad))
        return {"oid": "2", "mayor": cantidad, "menor": cobro, "comision": cobro * 0.005, "moneda_comision": m}


class Real(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        billetera.CARPETA = Path(self.tmp.name) / "billetera"
        billetera.precios = lambda activos, moneda="USD": PRECIOS
        os.environ["BILLETERA_QUORUM"] = "1"
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
        return billetera.iniciar(type("A", (), {"saldo": 0, "dias": 14, "modo": "real", "moneda": "COP",
                                                "confirmo": confirmo}))

    def test_sin_confirmar_el_monto_no_arranca(self):
        self.assertEqual(self.iniciar(), 2)
        self.assertEqual(self.iniciar("1999 COP"), 2)
        self.assertIsNone(billetera.leer_estado())

    def test_sin_porcentaje_en_env_no_arranca(self):
        os.environ.pop("BILLETERA_PORCENTAJE_REAL")
        self.assertEqual(self.iniciar("2000.00 COP"), 2)

    def test_compra_y_vende_en_bitso(self):
        self.assertEqual(self.iniciar("2000.00 COP"), 0)
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":20}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertEqual(self.bitso.ordenes, [("buy", "btc_cop", 400.0)])
        self.assertAlmostEqual(e["efectivo"], 1600.0)
        self.assertAlmostEqual(e["posiciones"]["BTC"], self.bitso.saldo["btc"])
        self.votos = ['{"accion":"vender","activo":"BTC","porcentaje":25}']
        billetera.ronda(None)
        self.assertEqual(self.bitso.ordenes[-1][0], "sell")
        self.assertAlmostEqual(billetera.leer_estado()["posiciones"]["BTC"], self.bitso.saldo["btc"])

    def test_deposito_de_david_se_suma(self):
        self.iniciar("2000.00 COP")
        self.bitso.saldo["cop"] += 500
        self.votos = ['{"accion":"mantener"}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertAlmostEqual(e["efectivo"], 2500.0)
        self.assertAlmostEqual(e["saldo_inicial"], 2500.0)

    def test_freno_por_perdida(self):
        self.iniciar("2000.00 COP")
        self.bitso.saldo["cop"] = 1000.0               # la cuenta perdió la mitad
        self.votos = ['{"accion":"mantener"}']
        billetera.ronda(None)
        self.assertTrue(billetera.pausada())

    def test_solo_monedas_con_libro_en_cop(self):
        self.iniciar("2000.00 COP")
        e = billetera.leer_estado()
        self.assertEqual((e["moneda"], e["activos"]), ("COP", ["BTC", "ETH"]))
        self.votos = ['{"accion":"comprar","activo":"SOL","porcentaje":10}']
        billetera.ronda(None)
        self.assertEqual(self.bitso.ordenes, [])

    def test_bitso_falla_y_no_toca_la_cartera(self):
        self.iniciar("2000.00 COP")
        def falla(*a):
            raise RuntimeError("caído")
        sys.modules["bitso"].comprar = falla
        self.votos = ['{"accion":"comprar","activo":"ETH","porcentaje":10}']
        self.assertEqual(billetera.ronda(None), 0)
        e = billetera.leer_estado()
        self.assertEqual(e["efectivo"], 2000.0)
        self.assertIn("Bitso falló", e["historial"][-1]["resumen"])


    def test_orden_sin_respuesta_cuenta_y_se_cuadra_con_bitso(self):
        """Bitso no contestó pero la orden se llenó: la cripto vuelve a la cartera y cuenta para el tope del día."""
        self.iniciar("2000.00 COP")
        comprar = self.bitso.comprar
        def tarde(*a):
            comprar(*a)
            raise RuntimeError("no pude hablar con Bitso: timed out")
        sys.modules["bitso"].comprar = tarde
        self.votos = ['{"accion":"comprar","activo":"ETH","porcentaje":10}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertTrue(e["historial"][-1]["incierta"])
        self.assertAlmostEqual(e["posiciones"]["ETH"], self.bitso.saldo["eth"])
        self.assertAlmostEqual(e["efectivo"], self.bitso.saldo["cop"])
        self.assertEqual(billetera.operaciones_de_hoy(e), 1)

    def test_rechazo_de_bitso_no_cuenta(self):
        self.iniciar("2000.00 COP")
        def no(*a):
            raise sys.modules["bitso"].Rechazo("Bitso respondió 400: saldo insuficiente")
        sys.modules["bitso"].comprar = no
        self.votos = ['{"accion":"comprar","activo":"ETH","porcentaje":10}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertNotIn("incierta", e["historial"][-1])
        self.assertEqual(billetera.operaciones_de_hoy(e), 0)

    def test_precio_de_bitso_muy_distinto_no_opera(self):
        self.iniciar("2000.00 COP")
        sys.modules["bitso"].ultimo = lambda libro: PRECIOS["BTC"]["precio"] * 1.05
        self.votos = ['{"accion":"comprar","activo":"BTC","porcentaje":10}']
        billetera.ronda(None)
        self.assertEqual(self.bitso.ordenes, [])
        self.assertIn("se aleja", billetera.leer_estado()["historial"][-1]["resumen"])


class PuenteDolares(unittest.TestCase):
    """La cuenta de David en Colombia: solo hay usd_cop, y las criptos se compran en dólares."""
    def setUp(self):
        Real.setUp(self)
        self.bitso = BitsoFalso(35000.0, ("usd_cop", "usdt_cop", "btc_usd", "eth_usd", "sol_usd", "btc_mxn"))
        sys.modules["bitso"] = self.bitso.modulo()
        def precios(activos, moneda="USD"):
            if moneda != "USD":
                raise RuntimeError("HTTP Error 400: Bad Request")    # CoinGecko no tiene COP
            return PRECIOS
        billetera.precios = precios

    tearDown = Real.tearDown
    iniciar = Real.iniciar

    def test_cambia_los_pesos_a_dolares_y_opera_en_usd(self):
        self.assertEqual(self.iniciar(), 2)            # el monto se confirma en pesos
        self.assertEqual(self.bitso.ordenes, [])
        self.assertEqual(self.iniciar("35000.00 COP"), 0)
        e = billetera.leer_estado()
        self.assertEqual(self.bitso.ordenes, [("buy", "usd_cop", 35000.0)])
        self.assertEqual((e["moneda"], e["puente"], e["activos"]), ("USD", "usd_cop", ["BTC", "ETH", "SOL"]))
        self.assertAlmostEqual(e["efectivo"], 8.71, places=2)      # 35000 / 4000 menos 0,5 %
        self.votos = ['{"accion":"comprar","activo":"SOL","porcentaje":20}']
        billetera.ronda(None)
        self.assertEqual(self.bitso.ordenes[-1][:2], ("buy", "sol_usd"))
        self.assertAlmostEqual(billetera.leer_estado()["posiciones"]["SOL"], self.bitso.saldo["sol"])

    def test_solo_monedas_con_libro_en_usd_y_las_nuevas_entran_solas(self):
        self.iniciar("35000.00 COP")
        self.assertEqual(billetera.leer_estado()["activos"], ["BTC", "ETH", "SOL"])   # ADA, XRP... sin libro
        self.bitso.libros.add("xrp_usd")
        PRECIOS["XRP"] = {"precio": 2.0, "cambio_24h": 0, "cambio_7d": 0}
        try:
            self.votos = ['{"accion":"comprar","activo":"XRP","porcentaje":20}']
            billetera.ronda(None)
        finally:
            PRECIOS.pop("XRP")
        self.assertEqual(self.bitso.ordenes[-1][:2], ("buy", "xrp_usd"))
        self.assertIn("XRP", billetera.leer_estado()["activos"])

    def test_deposito_en_pesos_se_cambia_a_dolares(self):
        self.iniciar("35000.00 COP")
        self.bitso.saldo["cop"] += 40000
        self.votos = ['{"accion":"mantener"}']
        billetera.ronda(None)
        e = billetera.leer_estado()
        self.assertEqual(self.bitso.ordenes[-1], ("buy", "usd_cop", 40000.0))
        self.assertAlmostEqual(e["efectivo"], 8.71 + 9.95, places=1)
        self.assertFalse(billetera.pausada())


if __name__ == "__main__":
    unittest.main()


class OrdenesBitso(unittest.TestCase):
    """scripts/bitso.py: si el POST de la orden se queda sin respuesta, se busca por origin_id."""
    def setUp(self):
        sys.modules.pop("bitso", None)
        import bitso
        self.bitso = bitso
        self.dormir, bitso.time.sleep = bitso.time.sleep, lambda s: None
        self.llamadas = []

    def tearDown(self):
        self.bitso.time.sleep = self.dormir
        sys.modules.pop("bitso", None)

    def falso(self, post_falla):
        def pedir(metodo, ruta, cuerpo=None):
            self.llamadas.append((metodo, ruta, cuerpo))
            if metodo == "POST":
                if post_falla:
                    raise post_falla
                return {"oid": "abc"}
            if ruta.startswith("/v3/orders/?origin_ids="):
                return [{"oid": "abc"}]
            return [{"major": "0.001", "minor": "-100", "fees_amount": "0.5", "fees_currency": "usd"}]
        self.bitso.pedir = pedir

    def test_manda_origin_id(self):
        self.falso(None)
        o = self.bitso.comprar("btc_usd", 100)
        self.assertEqual(o["oid"], "abc")
        self.assertRegex(self.llamadas[0][2]["origin_id"], r"^[A-Za-z0-9_-]{1,40}$")

    def test_sin_respuesta_la_busca_por_origin_id(self):
        self.falso(RuntimeError("no pude hablar con Bitso: timed out"))
        o = self.bitso.comprar("btc_usd", 100)
        self.assertEqual((o["oid"], o["mayor"]), ("abc", 0.001))
        origen = self.llamadas[0][2]["origin_id"]
        self.assertIn(("GET", f"/v3/orders/?origin_ids={origen}", None), self.llamadas)

    def test_rechazo_no_busca(self):
        self.falso(self.bitso.Rechazo("Bitso respondió 400: no"))
        with self.assertRaises(self.bitso.Rechazo):
            self.bitso.comprar("btc_usd", 100)
        self.assertEqual(len(self.llamadas), 1)
